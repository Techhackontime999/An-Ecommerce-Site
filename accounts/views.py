from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
import hashlib
import hmac
import logging
import secrets

from core.security import client_ip, safe_next_url
from core.throttle import throttle
from .forms import SellerRegisterForm, CustomerRegisterForm, SellerProfileForm, CustomerProfileForm
from .models import SellerProfile, CustomerProfile
from .security import is_locked, record_failure, reset
from notifications.services import notify
from notifications.models import Notification


logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = 300  # 5 minutes
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = 60  # seconds between resend requests
OTP_MAX_RESENDS = 3


def _hash_otp(otp):
    return hashlib.sha256(f'{settings.SECRET_KEY}:{otp}'.encode()).hexdigest()


def get_profile_for_user(user):
    try:
        return user.sellerprofile, 'seller'
    except SellerProfile.DoesNotExist:
        try:
            return user.customerprofile, 'customer'
        except CustomerProfile.DoesNotExist:
            return None, None


def pending_user(request):
    uid = request.session.get('pending_verify_user_id')
    if uid:
        return User.objects.filter(id=uid).first()
    return None


def is_fully_verified(profile):
    return bool(profile.is_email_verified and profile.is_phone_verified)


def send_email_verification(request, user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = request.build_absolute_uri(reverse('accounts:verify_email', args=[uid, token]))
    try:
        send_mail(
            subject='Verify your email — Shop-Seed',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=render_to_string(
                'accounts/verify_email_email.html',
                {'username': user.username, 'verify_link': link},
            ),
        )
    except Exception:
        logger.exception('Failed to send verification email to %s', user.email)


def send_phone_otp(request, user):
    # Cryptographically random OTP, stored only as a salted hash in the session
    # so a leaked session dump never exposes the code.
    otp = f'{secrets.randbelow(1_000_000):06d}'
    request.session['phone_otp_hash'] = _hash_otp(otp)
    request.session['phone_otp_expiry'] = timezone.now().timestamp() + OTP_EXPIRY_SECONDS
    request.session['phone_otp_attempts'] = 0
    request.session['phone_otp_last_sent'] = timezone.now().timestamp()
    request.session['phone_otp_resend_count'] = request.session.get('phone_otp_resend_count', 0) + 1
    request.session.modified = True
    try:
        send_mail(
            subject='Your phone verification code — Shop-Seed',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=render_to_string(
                'accounts/phone_otp_email.html',
                {'username': user.username, 'otp': otp, 'expiry_minutes': OTP_EXPIRY_SECONDS // 60},
            ),
        )
    except Exception:
        logger.exception('Failed to send phone OTP to %s', user.email)


@throttle('signup', max_requests=5, window_seconds=3600)
def signup(request):
    if request.method == 'POST':
        form = CustomerRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            customers_group, created = Group.objects.get_or_create(name='customers')
            customers_group.user_set.add(user)
            CustomerProfile.objects.create(
                user=user,
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
                profile_picture=form.cleaned_data.get('profile_picture'),
            )
            request.session['pending_verify_user_id'] = user.id
            send_email_verification(request, user)
            send_phone_otp(request, user)
            notify(
                user,
                Notification.Category.ACCOUNT,
                'Welcome to Shop-Seed!',
                'Your customer account was created. Complete email and phone verification to unlock everything.',
                link=reverse('accounts:verify'),
                icon='user-plus',
            )
            return redirect('accounts:verify')
    else:
        form = CustomerRegisterForm()

    return render(request, 'registration/signup.html', {'form': form})


def login_view(request):
    ip = client_ip(request)
    username = (request.POST.get('username') or '').strip()

    if username and is_locked('login-username', username):
        messages.error(request, 'Too many failed attempts. Please try again in 15 minutes.')
        return render(request, 'registration/login.html', {
            'form': AuthenticationForm(request),
            'next': request.GET.get('next', ''),
            'news_ticker_items': [],
        })
    if is_locked('login-ip', ip):
        messages.error(request, 'Too many failed attempts from this network. Please try again later.')
        return render(request, 'registration/login.html', {
            'form': AuthenticationForm(request),
            'next': request.GET.get('next', ''),
            'news_ticker_items': [],
        })

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            profile, kind = get_profile_for_user(user)

            if not (user.is_superuser or user.is_staff) and profile and not is_fully_verified(profile):
                request.session['pending_verify_user_id'] = user.id
                return redirect('accounts:verify')

            reset('login-username', user.username)
            reset('login-ip', ip)
            login(request, user)

            next_url = safe_next_url(request)
            if next_url:
                return redirect(next_url)

            if hasattr(user, 'sellerprofile'):
                return redirect('seller:seller_dashboard')
            elif hasattr(user, 'customerprofile'):
                return redirect('shop:product_list')

            return redirect('shop:product_list')
        else:
            # Wrong credentials — count the attempt for lockout purposes.
            if username:
                record_failure('login-username', username)
            record_failure('login-ip', ip)
            messages.error(request, 'Invalid username or password.')

    return render(request, 'registration/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
        'news_ticker_items': [],
    })


def logout_view(request):
    logout(request)
    return redirect('shop:product_list')


@throttle('seller-signup', max_requests=5, window_seconds=3600)
def seller_register(request):
    if request.method == 'POST':
        form = SellerRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            seller_group, created = Group.objects.get_or_create(name='sellers')
            seller_group.user_set.add(user)
            SellerProfile.objects.create(
                user=user,
                shop_name=form.cleaned_data['shop_name'] or user.username,
                gst_number=form.cleaned_data['gst_number'],
                bank_account=form.cleaned_data['bank_account'],
                account_holder_name=form.cleaned_data['account_holder_name'],
                ifsc_code=form.cleaned_data['ifsc_code'],
                bank_name=form.cleaned_data.get('bank_name'),
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
                profile_picture=form.cleaned_data.get('profile_picture'),
            )
            request.session['pending_verify_user_id'] = user.id
            send_email_verification(request, user)
            send_phone_otp(request, user)
            notify(
                user,
                Notification.Category.ACCOUNT,
                'Welcome to Shop-Seed sellers!',
                'Your seller account was created. Complete verification to start selling on Shop-Seed.',
                link=reverse('accounts:verify'),
                icon='store',
            )
            return redirect('accounts:verify')
    else:
        form = SellerRegisterForm()
    return render(request, 'registration/seller_register.html', {'form': form})


@login_required
def become_seller(request):
    try:
        seller_profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        seller_profile = None

    if seller_profile is not None:
        return redirect('seller:seller_dashboard')

    if request.method == 'POST':
        form = SellerProfileForm(request.POST, request.FILES)
        if form.is_valid():
            seller_profile = form.save(commit=False)
            seller_profile.user = request.user
            seller_profile.save()
            seller_group, created = Group.objects.get_or_create(name='sellers')
            seller_group.user_set.add(request.user)

            try:
                customer_profile = request.user.customerprofile
                seller_profile.is_email_verified = customer_profile.is_email_verified
                seller_profile.is_phone_verified = customer_profile.is_phone_verified
                seller_profile.save(update_fields=['is_email_verified', 'is_phone_verified'])
            except CustomerProfile.DoesNotExist:
                pass

            if request.user.is_superuser or request.user.is_staff:
                seller_profile.is_email_verified = True
                seller_profile.is_phone_verified = True
                seller_profile.save(update_fields=['is_email_verified', 'is_phone_verified'])
            elif not is_fully_verified(seller_profile):
                request.session['pending_verify_user_id'] = request.user.id
                send_email_verification(request, request.user)
                send_phone_otp(request, request.user)

            notify(
                request.user,
                Notification.Category.ACCOUNT,
                'Welcome to the seller family!',
                'Your shop is live. Complete verification and start selling on Shop-Seed.',
                link=reverse('seller:seller_dashboard'),
                icon='store',
            )
            return redirect('seller:seller_dashboard')
    else:
        form = SellerProfileForm()

    return render(request, 'accounts/become_seller.html', {'form': form})


@login_required
def profile_view(request):
    try:
        profile = request.user.sellerprofile
        form_class = SellerProfileForm
    except SellerProfile.DoesNotExist:
        try:
            profile = request.user.customerprofile
            form_class = CustomerProfileForm
        except CustomerProfile.DoesNotExist:
            profile = CustomerProfile.objects.create(
                user=request.user, phone='', address=''
            )
            form_class = CustomerProfileForm

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('accounts:profile')
    else:
        form = form_class(instance=profile)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
    })


def verify_view(request):
    user = pending_user(request)
    if not user:
        return redirect('accounts:login')
    profile, kind = get_profile_for_user(user)
    if profile is None:
        return redirect('accounts:login')
    return render(request, 'accounts/verify.html', {
        'user': user,
        'profile': profile,
        'email_verified': profile.is_email_verified,
        'phone_verified': profile.is_phone_verified,
        'both_verified': is_fully_verified(profile),
        'kind': kind,
    })


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        profile, kind = get_profile_for_user(user)
        if profile and not profile.is_email_verified:
            profile.is_email_verified = True
            profile.save(update_fields=['is_email_verified'])
            notify(
                user,
                Notification.Category.ACCOUNT,
                'Email verified',
                'Your email address has been successfully verified.',
                link=reverse('accounts:profile'),
                icon='envelope-circle-check',
            )
        request.session['pending_verify_user_id'] = user.id
        return render(request, 'accounts/verify_email_success.html', {'user': user})

    return render(request, 'accounts/verify_email_invalid.html', {})


def resend_verification_email(request):
    user = pending_user(request)
    if not user:
        return redirect('accounts:login')
    profile, kind = get_profile_for_user(user)
    if profile and not profile.is_email_verified:
        send_email_verification(request, user)
    return redirect('accounts:verify')


def verify_phone(request):
    user = pending_user(request)
    if not user:
        return redirect('accounts:login')
    profile, kind = get_profile_for_user(user)
    if profile is None:
        return redirect('accounts:login')

    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()
        expected_hash = request.session.get('phone_otp_hash')
        expiry = request.session.get('phone_otp_expiry')
        attempts = request.session.get('phone_otp_attempts', 0)
        expired = expiry is None or timezone.now().timestamp() > expiry

        if (
            expected_hash
            and not expired
            and attempts < OTP_MAX_ATTEMPTS
            and hmac.compare_digest(_hash_otp(entered), expected_hash)
        ):
            profile.is_phone_verified = True
            profile.save(update_fields=['is_phone_verified'])
            for key in ('phone_otp_hash', 'phone_otp_expiry', 'phone_otp_attempts'):
                request.session.pop(key, None)
            request.session.modified = True
            return redirect('accounts:verify')

        if expected_hash and not expired:
            request.session['phone_otp_attempts'] = attempts + 1
            request.session.modified = True
            if attempts + 1 >= OTP_MAX_ATTEMPTS:
                request.session.pop('phone_otp_hash', None)
                return render(request, 'accounts/verify_phone.html', {
                    'user': user,
                    'profile': profile,
                    'error': 'Too many incorrect codes. Request a new code and try again.',
                })

        return render(request, 'accounts/verify_phone.html', {
            'user': user,
            'profile': profile,
            'error': 'Invalid or expired code. Please try again.',
        })

    return render(request, 'accounts/verify_phone.html', {
        'user': user,
        'profile': profile,
    })


def resend_otp(request):
    user = pending_user(request)
    if not user:
        return redirect('accounts:login')
    profile, kind = get_profile_for_user(user)
    if profile is None or profile.is_phone_verified:
        return redirect('accounts:verify')

    last_sent = request.session.get('phone_otp_last_sent')
    if last_sent and timezone.now().timestamp() - last_sent < OTP_RESEND_COOLDOWN:
        messages.error(request, 'Please wait a moment before requesting a new code.')
        return redirect('accounts:verify_phone')

    resends = request.session.get('phone_otp_resend_count', 0)
    if resends >= OTP_MAX_RESENDS:
        messages.error(request, 'Too many code requests. Please try again later.')
        return redirect('accounts:verify_phone')

    send_phone_otp(request, user)
    messages.success(request, 'A new verification code has been sent.')
    return redirect('accounts:verify_phone')
