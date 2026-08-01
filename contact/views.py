
# Create your views here.
import os

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import ContactForm


def contact_view(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to send us a message.")
            return redirect(reverse('accounts:login') + f'?next={request.path}')
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            notify_owner(contact)
            messages.success(request, "Your message has been sent successfully!")
            return redirect('contact:contact')
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
            }
        form = ContactForm(initial=initial)
    return render(request, 'contact/contact.html', {'form': form})


def notify_owner(contact):
    """Email the contact message to the owner's address from .env."""
    recipient = (
        os.getenv('DJANGO_SUPERUSER_EMAIL')
        or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    )
    if not recipient:
        return
    subject = f"New contact message: {contact.subject}"
    body = (
        f"Name: {contact.name}\n"
        f"Email: {contact.email}\n"
        f"Subject: {contact.subject}\n\n"
        f"Message:\n{contact.message}\n"
    )
    try:
        send_mail(
            subject,
            body,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'Shop-Seed <no-reply@shop-seed.com>'),
            [recipient],
            reply_to=[contact.email],
            fail_silently=True,
        )
    except Exception:
        pass

