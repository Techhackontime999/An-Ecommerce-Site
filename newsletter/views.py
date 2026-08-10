import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core import signing
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from notifications.models import Notification
from notifications.services import notify
from core.security import safe_next_url
from core.throttle import throttle
from .models import Subscriber

logger = logging.getLogger(__name__)

UNSUBSCRIBE_SALT = 'newsletter.unsubscribe'
UNSUBSCRIBE_MAX_AGE = 60 * 60 * 24 * 30

CONFIRM_SALT = 'newsletter.confirm'
CONFIRM_MAX_AGE = 60 * 60 * 24 * 7


def _signed_token(email, salt):
    return signing.dumps(email, salt=salt)


def _unsubscribe_token(email):
    return _signed_token(email, UNSUBSCRIBE_SALT)


def unsubscribe_link(email):
    """Absolute, signed unsubscribe URL for a subscriber email."""
    url = reverse('newsletter:unsubscribe', args=[_unsubscribe_token(email)])
    return f'{settings.SITE_URL}{url}'


def _confirm_token(email):
    return _signed_token(email, CONFIRM_SALT)


def confirm_link(email):
    """Absolute, signed confirmation URL (double opt-in)."""
    url = reverse('newsletter:confirm', args=[_confirm_token(email)])
    return f'{settings.SITE_URL}{url}'


def _welcome_email(email):
    subject = 'Welcome to Shop-Seed — you are subscribed!'
    html = render_to_string('newsletter/welcome_email.html', {
        'email': email,
        'unsubscribe_url': unsubscribe_link(email),
    })
    try:
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html,
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning('Newsletter welcome email failed for %s: %s', email, exc)


def _confirmation_email(email):
    """Double opt-in email: the subscriber must click to confirm consent."""
    subject = 'Please confirm your Shop-Seed subscription'
    html = render_to_string('newsletter/confirm_email.html', {
        'email': email,
        'confirm_url': confirm_link(email),
        'unsubscribe_url': unsubscribe_link(email),
    })
    try:
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html,
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning('Newsletter confirmation email failed for %s: %s', email, exc)


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


@require_POST
@throttle('newsletter', max_requests=10, window_seconds=3600)
def subscribe(request):
    email = (request.POST.get('email') or '').strip().lower()

    if not email or '@' not in email or email.count('@') != 1:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': 'Please enter a valid email address.'}, status=400)
        messages.error(request, 'Please enter a valid email address.')
        return redirect(safe_next_url(request) or '/')

    subscriber, created = Subscriber.objects.get_or_create(
        email=email,
        defaults={'is_active': False, 'is_confirmed': False},
    )

    if not created and subscriber.is_confirmed:
        subscriber.is_active = True
        subscriber.save(update_fields=['is_active'])
        message = 'You are already subscribed to the Shop-Seed newsletter.'
    else:
        subscriber.is_active = False
        subscriber.is_confirmed = False
        subscriber.save(update_fields=['is_active', 'is_confirmed'])
        _confirmation_email(email)
        message = "Almost there! Check your inbox and click the link to confirm your subscription."

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is not None:
        notify(
            user,
            Notification.Category.PROMO,
            'Confirm your Shop-Seed subscription',
            'We sent you a confirmation link — click it to start receiving exclusive deals.',
            link=confirm_link(email) if not (subscriber.is_confirmed and subscriber.is_active) else '/',
            icon='bell',
        )

    if _is_ajax(request):
        return JsonResponse({'ok': True, 'message': message})
    messages.success(request, message)
    return redirect(safe_next_url(request) or '/')


@require_GET
def confirm(request, token):
    """Double opt-in confirmation: activates the subscriber and sends the
    welcome email. This is the only place ``is_confirmed`` is set to True by a
    user action."""
    try:
        email = signing.loads(token, salt=CONFIRM_SALT, max_age=CONFIRM_MAX_AGE)
    except signing.BadSignature:
        return render(request, 'newsletter/confirmed.html', {
            'error': True,
            'title': 'Invalid confirmation link',
            'message': 'This confirmation link is invalid or has expired. '
                       'Enter your email again to receive a fresh link.',
        }, status=400)

    confirmed = Subscriber.objects.filter(
        email=email, is_confirmed=False,
    ).update(is_confirmed=True, is_active=True, confirmed_at=timezone.now())

    if confirmed:
        _welcome_email(email)
        return render(request, 'newsletter/confirmed.html', {
            'email': email,
            'title': 'You are subscribed!',
            'message': f'{email} is now subscribed to the Shop-Seed newsletter. '
                       'Check your inbox for a welcome email.',
        })

    return render(request, 'newsletter/confirmed.html', {
        'email': email,
        'title': 'Already subscribed',
        'message': f'{email} is already confirmed on the Shop-Seed newsletter.',
    })


@require_GET
def unsubscribe(request, token):
    """Confirm a subscriber opt-out via a signed token from an email link."""
    try:
        email = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=UNSUBSCRIBE_MAX_AGE)
    except signing.BadSignature:
        return render(request, 'newsletter/unsubscribed.html', {
            'error': True,
            'title': 'Invalid link',
            'message': 'This unsubscribe link is invalid or has expired. '
                       'Please use the link from a recent email, or contact support.',
        }, status=400)

    updated = Subscriber.objects.filter(email=email, is_active=True).update(is_active=False)
    return render(request, 'newsletter/unsubscribed.html', {
        'email': email,
        'unsubscribed': updated > 0,
        'title': 'You are unsubscribed',
        'message': (
            f'{email} has been removed from our newsletter list. '
            'You will no longer receive marketing emails from Shop-Seed.'
            if updated else
            f'{email} is not currently subscribed to the Shop-Seed newsletter.'
        ),
    })
