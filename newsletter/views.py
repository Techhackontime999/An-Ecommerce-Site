import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from notifications.models import Notification
from notifications.services import notify
from .models import Subscriber

logger = logging.getLogger(__name__)


def _welcome_email(email):
    subject = 'Welcome to Shop-Seed — you are subscribed!'
    html = render_to_string('newsletter/welcome_email.html', {'email': email})
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


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


@require_POST
def subscribe(request):
    email = (request.POST.get('email') or '').strip().lower()

    if not email or '@' not in email or email.count('@') != 1:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': 'Please enter a valid email address.'}, status=400)
        messages.error(request, 'Please enter a valid email address.')
        return redirect(request.META.get('HTTP_REFERER') or '/')

    subscriber, created = Subscriber.objects.get_or_create(
        email=email,
        defaults={'is_active': True},
    )
    if not created and not subscriber.is_active:
        subscriber.is_active = True
        subscriber.save(update_fields=['is_active'])

    _welcome_email(email)

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is not None:
        notify(
            user,
            Notification.Category.PROMO,
            'Subscribed to Shop-Seed news',
            "You'll now receive exclusive deals, launches and updates in your inbox.",
            link='/preferences/settings/',
            icon='bell',
        )

    message = "You're subscribed! Check your inbox for a welcome email."
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'message': message})
    messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER') or '/')
