"""Order-level services: customer invoice generation and cancellation."""

import io
import logging
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse

from .models import Order, Refund
from .state import set_order_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def cancel_order(order, actor=None, reason=''):
    """Cancel an order on the customer side.

    Only orders that haven't shipped can be cancelled. If the order was paid,
    stock is restored and the captured payment is refunded through the gateway.

    The order row is locked with ``select_for_update`` so this serialises with
    ``finalize_payment``: either the capture wins (payment marked paid, then the
    cancellation refunds it) or the cancellation wins (the late capture is
    rejected and refunded by the payment service).

    Returns (ok, detail). ``detail`` is a human-readable status message.
    """
    from order.stock import release_stock
    from payments.models import Payment
    from payments.services import refund_payment

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if not order.cancelable:
            return False, f'Order {order.order_number} cannot be cancelled at its current status.'

        ok, _ = set_order_status(
            order, order.Status.CANCELLED, actor=actor,
            note='Customer cancellation' + (f': {reason}' if reason else ''),
        )
        if not ok:
            return False, f'Order {order.order_number} cannot be cancelled at its current status.'

        payment = Payment.objects.select_for_update().filter(order=order).first()
        refunded = False
        if payment is not None and payment.status == 'captured':
            release_stock(order)
            try:
                refund_payment(
                    payment,
                    note=f'Customer cancellation of {order.order_number}' + (f' ({reason})' if reason else ''),
                    actor=actor,
                )
                refunded = True
            except Exception as exc:
                logger.error('Refund failed during cancellation of order %s: %s', order.id, exc, exc_info=True)

    _notify_cancelled(order, actor, refunded)
    return True, 'cancelled' if not refunded else 'cancelled_and_refunded'


def _notify_cancelled(order, actor, refunded):
    from notifications.models import Notification
    from notifications.services import notify

    user = actor if (actor and actor.pk == order.user_id) else order.user
    refund_text = ' Your payment has been refunded.' if refunded else \
        ' If you had paid, a refund will be processed.'
    notify(
        user,
        Notification.Category.ORDER,
        f'Order {order.order_number} cancelled',
        f'Your order has been cancelled.{refund_text}',
        link=reverse('order:my_orders'),
        icon='ban',
    )
    seller_users = set()
    for item in order.items.select_related('product__seller'):
        seller = item.product.seller
        if seller and seller.user_id:
            seller_users.add(seller.user)
    for seller_user in seller_users:
        notify(
            seller_user,
            Notification.Category.ORDER,
            f'Order {order.order_number} cancelled by customer',
            f'A customer cancelled order {order.order_number}. Check your dashboard for details.',
            link=reverse('seller:orders'),
            icon='ban',
        )


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------

def create_refund(order, *, amount, method=Refund.Method.ORIGINAL_PAYMENT,
                  reason='', actor=None, return_request=None):
    """Create a refund with over-refund protection, atomically.

    Serialises on the captured payment row (``select_for_update``) so two
    concurrent admin actions can never together refund more than was actually
    captured, then runs the same validation as ``Refund.clean()``. Unlike a raw
    bulk ``queryset.update()`` in the admin, this path cannot be bypassed.

    Returns the created ``Refund``. Raises ``django.core.exceptions.ValidationError``
    for a non-positive amount or an over-refund.
    """
    from django.core.exceptions import ValidationError
    from payments.models import Payment

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().filter(order=order).first()
        # Pin the locked payment on the order instance so ``total_paid()`` (used
        # by ``Refund.clean``) reflects the state we serialised on.
        order.payment = payment

        refund = Refund(
            order=order, amount=amount, method=method, reason=reason,
            initiated_by=actor, return_request=return_request,
        )
        try:
            refund.full_clean()
        except ValidationError:
            raise
        refund.save()
        return refund


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

def invoice_number(order):
    return f'INV-{order.order_number}'


def invoice_totals(order):
    subtotal = order.get_subtotal()
    taxable = order.get_taxable_amount()
    tax = order.get_tax_amount()
    discount = order.discount
    shipping = order.shipping_cost
    total = order.get_total_cost()
    return {
        'subtotal': subtotal,
        'shipping': shipping,
        'discount': discount,
        'taxable': taxable,
        'tax': tax,
        'tax_rate': order.tax_rate,
        'total': total,
    }


def generate_invoice_pdf(order):
    """Render a customer-facing tax invoice for an order as PDF bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm)

    styles = getSampleStyleSheet()
    title = ParagraphStyle('title', parent=styles['Title'], fontSize=20, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontSize=12, spaceAfter=2)
    small = ParagraphStyle('small', parent=styles['BodyText'], fontSize=8.5, textColor=colors.grey)
    cell = ParagraphStyle('cell', parent=styles['BodyText'], fontSize=9)
    cellb = ParagraphStyle('cellb', parent=cell, fontName='Helvetica-Bold')
    th = ParagraphStyle('th', parent=cell, fontName='Helvetica-Bold', textColor=colors.white)

    totals = invoice_totals(order)
    story = [
        Paragraph('SHOP-SEED', title),
        Paragraph('Tax Invoice', h2),
        Paragraph('support@shop-seed.com · {0}'.format(getattr(settings, 'SITE_URL', 'shop-seed.com')), small),
        Spacer(1, 6 * mm),
    ]

    # Billing block
    billing = Table(
        [
            [Paragraph('BILL TO', h2), Paragraph('INVOICE', h2)],
            [Paragraph(f"{order.first_name} {order.last_name}<br/>"
                       f"{order.address}<br/>{order.city} — {order.postal_code}<br/>"
                       f"{order.state} · {order.country}<br/>{order.phone or ''}", cell),
             Paragraph(f"<b>Invoice No:</b> {invoice_number(order)}<br/>"
                       f"<b>Order No:</b> {order.order_number}<br/>"
                       f"<b>Date:</b> {order.created:%d %b %Y}<br/>"
                       f"<b>Status:</b> {'Paid' if order.paid else order.get_status_display()}", cell)],
        ],
        colWidths=[92 * mm, 82 * mm],
    )
    billing.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.grey),
    ]))
    story.append(billing)
    story.append(Spacer(1, 6 * mm))

    # Line items
    header = [Paragraph(h, th) for h in ('Item', 'Variant', 'Qty', 'Price', 'Amount')]
    rows = [header]
    for item in order.items.select_related('product', 'variant'):
        rows.append([
            Paragraph(item.product.name, cell),
            Paragraph(item.variant_name or '—', cell),
            Paragraph(str(item.quantity), cell),
            Paragraph(f'₹{item.price:.2f}', cell),
            Paragraph(f'₹{item.get_cost():.2f}', cell),
        ])
    table = Table(rows, colWidths=[60 * mm, 40 * mm, 18 * mm, 28 * mm, 28 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))

    # Totals
    total_rows = [
        [Paragraph('Subtotal', cell), Paragraph(f'₹{totals["subtotal"]:.2f}', cell)],
        [Paragraph('Shipping', cell), Paragraph(f'₹{totals["shipping"]:.2f}', cell)],
    ]
    if totals['discount']:
        total_rows.append([Paragraph('Discount', cell), Paragraph(f'- ₹{totals["discount"]:.2f}', cell)])
    total_rows.append([Paragraph('Tax (GST {:.0f}%)'.format(totals['tax_rate'] * 100), cell),
                       Paragraph(f'₹{totals["tax"]:.2f}', cell)])
    total_rows.append([Paragraph('Grand Total', cellb), Paragraph(f'₹{totals["total"]:.2f}', cellb)])
    totals_table = Table(total_rows, colWidths=[120 * mm, 54 * mm])
    totals_table.setStyle(TableStyle([
        ('LINEABOVE', (0, -2), (-1, -2), 0.4, colors.grey),
        ('LINEABOVE', (0, -1), (-1, -1), 0.8, colors.HexColor('#0f172a')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        'Thank you for shopping with Shop-Seed! This is a computer-generated invoice and does not '
        'require a signature. For returns or questions, visit your order page.', small))

    doc.build(story)
    return buf.getvalue()
