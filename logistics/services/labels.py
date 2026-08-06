"""Printable document generation for the LMS.

Renders PDF documents that every logistics operation needs:

- Shipping label (with Code128 AWB barcode + QR code)
- Commercial invoice (GST-style, line items + totals)
- Courier manifest / packet list (bulk pickup sheet)
- Pickup sheet

ReportLab is used directly (not weasyprint) so documents are fast, robust and
do not depend on network CSS. DejaVu Sans is registered for full Unicode
support (including the rupee sign and Devanagari address blocks).
"""

import io
import os
from datetime import date, datetime

import qrcode
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics.shapes import Drawing, Image as GraphicsImage

from django.utils import timezone

_FONT = 'LmsSans'
_FONT_B = 'LmsSansBold'

_DEJAVU_PATHS = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/mnt/c/Windows/Fonts/arial.ttf',
    'C:\\Windows\\Fonts\\arial.ttf',
)
_DEJAVU_BOLD_PATHS = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/mnt/c/Windows/Fonts/arialbd.ttf',
    'C:\\Windows\\Fonts\\arialbd.ttf',
)

_LOADED = False


def _ensure_fonts():
    global _LOADED
    if _LOADED:
        return
    regular = next((p for p in _DEJAVU_PATHS if os.path.exists(p)), None)
    bold = next((p for p in _DEJAVU_BOLD_PATHS if os.path.exists(p)), None)
    if regular:
        pdfmetrics.registerFont(TTFont(_FONT, regular))
    if bold:
        pdfmetrics.registerFont(TTFont(_FONT_B, bold))
    _LOADED = True


def _font():
    _ensure_fonts()
    return _FONT if _FONT in pdfmetrics.getRegisteredFontNames() else 'Helvetica'


def _font_b():
    _ensure_fonts()
    return _FONT_B if _FONT_B in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'


def _styles():
    _ensure_fonts()
    f, fb = _font(), _font_b()
    base = getSampleStyleSheet()
    styles = {
        'title': ParagraphStyle('title', parent=base['Title'], fontName=fb, fontSize=18, leading=22),
        'h2': ParagraphStyle('h2', parent=base['Heading2'], fontName=fb, fontSize=12, leading=16),
        'body': ParagraphStyle('body', parent=base['BodyText'], fontName=f, fontSize=9, leading=12),
        'small': ParagraphStyle('small', parent=base['BodyText'], fontName=f, fontSize=7.5, leading=10),
        'barcode_text': ParagraphStyle('barcode_text', parent=base['BodyText'], fontName=fb, fontSize=11, leading=14, alignment=TA_CENTER),
        'mono': ParagraphStyle('mono', parent=base['BodyText'], fontName='Courier', fontSize=9, leading=12),
    }
    return styles


def _money(amount, currency='INR'):
    try:
        return f'{float(amount or 0):,.2f} {currency}'
    except (TypeError, ValueError):
        return f'{amount} {currency}'


def _delivery_block(shipment):
    order = shipment.order
    lines = [
        order.first_name + ' ' + (order.last_name or ''),
        order.address,
    ]
    if getattr(order, 'city', ''):
        lines.append(f'{order.city} - {shipment.destination_pincode or order.postal_code}')
    phone = getattr(order, 'phone', '')
    if phone:
        lines.append(f'Phone: {phone}')
    return '\n'.join(filter(None, lines))


def _origin_block(shipment):
    if shipment.warehouse:
        w = shipment.warehouse
        return '\n'.join(filter(None, [
            w.name,
            w.address_line1,
            (w.address_line2 or '') if w.address_line2 else '',
            f'{w.city}, {w.state} - {w.pincode}',
            f'Contact: {w.contact_name} {w.contact_phone}'.strip(),
        ]))
    if shipment.seller:
        return shipment.seller.address
    return 'Shop-Seed Fulfilment'


def _barcode_drawing(value, width=120 * mm, height=30 * mm):
    """Code128 barcode drawing sized to the requested width."""
    drawing = createBarcodeDrawing(
        'Code128', value=str(value or 'NOAWB'),
        barHeight=height * 0.8,
        barWidth=0.35 * mm,
        humanReadable=False,
    )
    scale = width / max(drawing.width, 1)
    drawing.width = width
    drawing.height = height
    drawing.scale(scale, 1)
    return drawing


def _qr_drawing(value, size=30 * mm):
    img = qrcode.make(value or '')
    img = img.convert('RGB')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    drawing = Drawing(size, size)
    drawing.add(GraphicsImage(0, 0, size, size, buffer.read()))
    return drawing


def generate_label_pdf(shipment):
    """Render a full A4 shipping label as PDF bytes.

    Mirrors what real couriers expect: to/from addresses, AWB barcode, QR code
    pointing at the public tracking page, package weights and COD information.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    st = _styles()
    story = []

    # Header
    header = Table(
        [[Paragraph('SHOP-SEED', st['title']), Paragraph('Shipping Label', st['h2'])]],
        colWidths=[90 * mm, 96 * mm],
    )
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#14532d')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header)
    story.append(Spacer(1, 4 * mm))

    meta = Table(
        [[
            Paragraph(f'<b>AWB / Tracking:</b><br/>{shipment.tracking_number or "—"}', st['body']),
            Paragraph(f'<b>Shipment:</b><br/>{shipment.shipment_number}', st['body']),
            Paragraph(f'<b>Courier:</b><br/>{shipment.courier.name if shipment.courier else "—"}', st['body']),
            Paragraph(f'<b>Service:</b><br/>{shipment.service.name if shipment.service else "Standard"}', st['body']),
        ]],
        colWidths=[56 * mm, 50 * mm, 46 * mm, 34 * mm],
    )
    meta.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(meta)
    story.append(Spacer(1, 4 * mm))

    # Addresses
    origin = Paragraph(f'<b>FROM (Pickup / Return)</b><br/><br/>{_origin_block(shipment).replace(chr(10), "<br/>")}', st['body'])
    dest = Paragraph(f'<b>TO (Deliver To)</b><br/><br/>{_delivery_block(shipment).replace(chr(10), "<br/>")}', st['body'])
    addr = Table([[origin, dest]], colWidths=[93 * mm, 93 * mm])
    addr.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(addr)
    story.append(Spacer(1, 5 * mm))

    # Package + payment summary
    facts = [
        f'Weight: {float(shipment.weight_g or 0):.0f} g',
        f'Volumetric: {float(shipment.volumetric_weight_g or 0):.0f} g',
        f'Chargeable: {float(shipment.chargeable_weight_g or 0):.0f} g',
        f'Dimensions: {shipment.length_cm} x {shipment.width_cm} x {shipment.height_cm} cm',
        f'Payment: {"COD" if shipment.is_cod else "Prepaid"}',
        f'COD Amount: {_money(shipment.cod_amount, shipment.currency)}' if shipment.is_cod else 'Declared Value: ' + _money(shipment.declared_value, shipment.currency),
        f'ETA: {shipment.estimated_delivery_date or "—"}',
        f'Hazardous: {"YES" if shipment.is_hazardous else "No"}',
    ]
    facts_table = Table(
        [[Paragraph('<b>Package & Payment</b>', st['body']),
          Paragraph('<br/>'.join(facts), st['body'])]],
        colWidths=[40 * mm, 146 * mm],
    )
    facts_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(facts_table)
    story.append(Spacer(1, 5 * mm))

    # Barcode + QR
    barcode = _barcode_drawing(shipment.tracking_number or shipment.shipment_number)
    qr = _qr_drawing(shipment.tracking_url or f'{shipment.shipment_number}')
    code_row = Table(
        [[barcode, Paragraph(shipment.tracking_number or shipment.shipment_number, st['barcode_text'])], [qr, Paragraph('Scan to track', st['small'])]],
        colWidths=[150 * mm, 36 * mm],
    )
    code_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(code_row)
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        'This is a system generated label. Sign off: ' + timezone.localtime().strftime('%Y-%m-%d %H:%M'),
        st['small'],
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def generate_invoice_pdf(shipment):
    """Render a commercial invoice with line items and totals as PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )
    st = _styles()
    story = []

    order = shipment.order
    header = Table(
        [[Paragraph('SHOP-SEED', st['title']), Paragraph('Tax Invoice', st['h2'])]],
        colWidths=[95 * mm, 90 * mm],
    )
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#14532d')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header)
    story.append(Spacer(1, 6 * mm))

    bill = Table(
        [[
            Paragraph(
                f'<b>Invoice No:</b> INV-{shipment.shipment_number}<br/>'
                f'<b>Date:</b> {timezone.localdate():%d %b %Y}<br/>'
                f'<b>Order:</b> #{order.pk}<br/>'
                f'<b>Shipment:</b> {shipment.shipment_number}<br/>'
                f'<b>Payment:</b> {"COD" if shipment.is_cod else "Prepaid"}', st['body']),
            Paragraph(
                f'<b>Bill To</b><br/>{(order.first_name + " " + (order.last_name or "")).strip()}<br/>'
                + order.address.replace(chr(10), '<br/>') + f'<br/>{order.city} - {shipment.destination_pincode or order.postal_code}', st['body']),
            Paragraph(f'<b>Ship From</b><br/>' + _origin_block(shipment).replace(chr(10), '<br/>'), st['body']),
        ]],
        colWidths=[60 * mm, 63 * mm, 63 * mm],
    )
    bill.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(bill)
    story.append(Spacer(1, 6 * mm))

    items = shipment.items.all()
    rows = [[
        Paragraph('<b>#</b>', st['small']),
        Paragraph('<b>Item / HSN</b>', st['small']),
        Paragraph('<b>SKU</b>', st['small']),
        Paragraph('<b>Qty</b>', st['small']),
        Paragraph('<b>Unit Price</b>', st['small']),
        Paragraph('<b>Amount</b>', st['small']),
    ]]
    for i, item in enumerate(items, start=1):
        hsn = item.hsn_code or '—'
        rows.append([
            Paragraph(str(i), st['small']),
            Paragraph(f'{item.product_name}<br/><font size="6">HSN: {hsn}</font>', st['small']),
            Paragraph(item.sku or '—', st['small']),
            Paragraph(str(item.quantity), st['small']),
            Paragraph(_money(item.unit_price, shipment.currency), st['small']),
            Paragraph(_money(item.unit_price * item.quantity, shipment.currency), st['small']),
        ])

    if not items:
        rows.append([Paragraph('1', st['small']), Paragraph(shipment.shipment_number, st['small']),
                     Paragraph('—', st['small']), Paragraph('1', st['small']),
                     Paragraph(_money(shipment.declared_value, shipment.currency), st['small']),
                     Paragraph(_money(shipment.declared_value, shipment.currency), st['small'])])

    items_table = Table(rows, colWidths=[10 * mm, 70 * mm, 40 * mm, 15 * mm, 28 * mm, 23 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2ff')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    subtotal = sum((float(i.unit_price) * i.quantity for i in items), 0.0) or float(shipment.declared_value or 0)
    total = subtotal + float(shipment.shipping_charge or 0)

    totals = Table(
        [[
            Paragraph(
                f'<b>Subtotal:</b> {_money(subtotal, shipment.currency)}<br/>'
                f'<b>Shipping:</b> {_money(shipment.shipping_charge, shipment.currency)}<br/>'
                f'<b>TOTAL:</b> {_money(total, shipment.currency)}', st['body']),
            Paragraph(f'<b>COD to collect:</b> {_money(shipment.cod_amount, shipment.currency)}' if shipment.is_cod else '',
                      st['body']),
        ]],
        colWidths=[120 * mm, 66 * mm],
    )
    totals.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(totals)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph('Goods once sold are not returnable unless damaged in transit. This is a computer generated invoice.', st['small']))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def generate_manifest_pdf(shipment_ids):
    """Render a courier manifest / packet list for a set of shipments."""
    from logistics.models import Shipment

    qs = Shipment.objects.filter(pk__in=shipment_ids).select_related('courier', 'order', 'warehouse')
    return _shipments_list_pdf(qs, 'Courier Manifest')


def generate_pickup_sheet_pdf(shipments):
    """Render a pickup sheet (pick list) for a set of shipments."""
    return _shipments_list_pdf(shipments, 'Pickup Sheet')


def _shipments_list_pdf(shipments, title):
    shipments = list(shipments)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )
    st = _styles()
    story = []
    story.append(Paragraph(f'SHOP-SEED — {title}', st['title']))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f'Generated {timezone.localtime():%d %b %Y %H:%M} • {len(shipments)} shipment(s)',
        st['small'],
    ))
    story.append(Spacer(1, 5 * mm))

    rows = [[
        Paragraph('<b>#</b>', st['small']),
        Paragraph('<b>Shipment</b>', st['small']),
        Paragraph('<b>AWB</b>', st['small']),
        Paragraph('<b>Courier</b>', st['small']),
        Paragraph('<b>To</b>', st['small']),
        Paragraph('<b>Weight (g)</b>', st['small']),
        Paragraph('<b>Payment</b>', st['small']),
    ]]
    for i, s in enumerate(shipments, start=1):
        destination = ', '.join(filter(None, [
            s.order.first_name + ' ' + (s.order.last_name or ''),
            s.order.city,
        ]))
        rows.append([
            Paragraph(str(i), st['small']),
            Paragraph(s.shipment_number, st['small']),
            Paragraph(s.tracking_number or '—', st['small']),
            Paragraph(s.courier.name if s.courier else '—', st['small']),
            Paragraph(destination, st['small']),
            Paragraph(str(int(s.weight_g or 0)), st['small']),
            Paragraph('COD' if s.is_cod else 'Prepaid', st['small']),
        ])

    table = Table(rows, colWidths=[8 * mm, 45 * mm, 40 * mm, 28 * mm, 42 * mm, 16 * mm, 16 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2ff')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def attach_label(shipment, overwrite=True):
    """Generate the label PDF and store it on the shipment's label FileField.

    Returns the saved Django file path (or '' if the label could not be
    attached, e.g. during tests without storage)."""
    from django.core.files.base import ContentFile
    from logistics.models import AuditLog

    try:
        data = generate_label_pdf(shipment)
    except Exception as exc:  # pragma: no cover - defensive
        AuditLog.log(AuditLog.ACTION_LABEL, 'shipment', shipment.shipment_number,
                     {'error': str(exc)})
        return ''

    if overwrite or not shipment.label:
        filename = f'{shipment.shipment_number}.pdf'
        shipment.label.save(filename, ContentFile(data), save=True)
    AuditLog.log(AuditLog.ACTION_LABEL, 'shipment', shipment.shipment_number,
                 {'bytes': len(data)})
    return shipment.label.name
