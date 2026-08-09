import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _order_track_url(order):
    """Absolute URL for the customer to follow their order.

    Signed-in customers go to their order list. Guests (no account) get a
    signed, expiring link to the tracking page so the button in the email works
    even from a different browser than the one used to check out.
    """
    from django.urls import reverse
    if order.user_id:
        return '{}{}'.format(settings.SITE_URL, reverse('order:my_orders'))
    from order.access import make_guest_access_token
    token = make_guest_access_token(order)
    return '{}{}?token={}'.format(
        settings.SITE_URL,
        reverse('shipping:order_tracking', args=[order.id]),
        token,
    )


def send_html_email(subject, template_name, context, to_emails, from_email=None):
    """Render an HTML template and send it as a multi-part email.

    The plain-text body is the rendered template with HTML tags stripped so
    the email still works in clients that block HTML. Sending is best-effort:
    a mail failure must never break checkout, payment, or shipping flows.
    """
    if not to_emails:
        return False
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    context.setdefault('site_name', 'Shop-Seed')
    context.setdefault('site_url', getattr(settings, 'SITE_URL', ''))
    try:
        html = render_to_string(template_name, context)
        text = _strip_html(html)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=to_emails,
        )
        email.attach_alternative(html, 'text/html')
        email.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.warning('Email send failed (%s): %s', template_name, exc, exc_info=True)
        return False


def _strip_html(html):
    import re
    text = re.sub(r'<style.*?</style>', ' ', html, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def send_order_confirmation(order):
    """Send the order confirmation email for a newly created order."""
    return send_html_email(
        subject=f'Order Confirmed — {order.order_number}',
        template_name='emails/order_confirmation.html',
        context={'order': order, 'track_url': _order_track_url(order)},
        to_emails=order.email,
    )


def send_payment_confirmation(order, payment):
    """Send the payment-received email after a successful capture."""
    return send_html_email(
        subject=f'Payment Received — {order.order_number}',
        template_name='emails/payment_confirmation.html',
        context={'order': order, 'payment': payment, 'track_url': _order_track_url(order)},
        to_emails=order.email,
    )


def send_shipping_confirmation(order, shipment):
    """Send the shipped email when a shipment is created for an order."""
    return send_html_email(
        subject=f'Your Order is on its Way — {order.order_number}',
        template_name='emails/shipping_confirmation.html',
        context={'order': order, 'shipment': shipment, 'track_url': _order_track_url(order)},
        to_emails=order.email,
    )


def send_notification_digest(user, notifications):
    """Send a single digest email summarising a user's unread notifications.

    Returns True when an email was sent.
    """
    notifications = [n for n in notifications if n is not None]
    if not notifications:
        return False
    if not user.email:
        return False
    return send_html_email(
        subject=f'{len(notifications)} new update{"" if len(notifications) == 1 else "s"} from Shop-Seed',
        template_name='emails/notification_digest.html',
        context={'notifications': notifications},
        to_emails=user.email,
    )
