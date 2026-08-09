"""Django settings for config project - Local Development."""

import os

from .languages import available_languages

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-development-only")

# Fernet key for encrypting sensitive fields (courier API credentials).
# Dev-only default; production must set FIELD_ENCRYPTION_KEY.
FIELD_ENCRYPTION_KEY = os.getenv(
    "FIELD_ENCRYPTION_KEY",
    "uT9L_EUKJz9r2H8J6_eXuP9Lb83uUO6MXVFC2b8EYcM=",
)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_xxxxxxxxxxxx")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "your_test_secret")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
PAYMENTS_CURRENCY = os.getenv("PAYMENTS_CURRENCY", "INR")

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'shop-seed.onrender.com']

CSRF_TRUSTED_ORIGINS = ['https://shop-seed.onrender.com','https://localhost']

INSTALLED_APPS = [
    'core',
    'platform_studio.apps.PlatformStudioConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    'crispy_forms',
    'ckeditor',
    'django_extensions',

    'shop.apps.ShopConfig',
    'blogs.apps.BlogsConfig',
    'cart.apps.CartConfig',
    'wishlist.apps.WishlistConfig',
    'order.apps.OrderConfig',
    'coupons.apps.CouponsConfig',
    'accounts',
    'about',
    'contact',
    'services',
    'deals',
    'documentation',
    'faq',
    'seller',
    'reviews',
    'payments.apps.PaymentsConfig',
    'shipping.apps.ShippingConfig',
    'logistics.apps.LogisticsConfig',
    'preferences.apps.PreferencesConfig',
    'news.apps.NewsConfig',
    'legal.apps.LegalConfig',
    'notifications.apps.NotificationsConfig',
    'newsletter.apps.NewsletterConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'builtins': ['core.templatetags.core_security'],
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                'wishlist.context_processors.wishlist',
                'shop.context_processors.search_action_context',
                'platform_studio.context_processors.platform_settings_context',
                'seller.context_processors.seller_context',
                'logistics.context_processors.logistics_admin_context',
                'blogs.context_processors.blog_nav',
                'preferences.context_processors.user_preferences',
                'news.context_processors.news_ticker',
                'notifications.context_processors.notifications_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LANGUAGES = available_languages()

LOCALE_PATHS = [
    os.path.join(PROJECT_DIR, 'locale'),
]

# Language selection is persisted by LocaleMiddleware in a cookie (and in the
# session key of the same name for signed-in users whose preference is saved
# to UserPreference).
LANGUAGE_COOKIE_NAME = 'shopseed_language'
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365  # 1 year
LANGUAGE_COOKIE_PATH = '/'

# Live currency conversion — fetched from a free exchange-rate API and cached.
EXCHANGE_RATE_API_URL = os.getenv(
    'EXCHANGE_RATE_API_URL', 'https://open.er-api.com/v6/latest/{base}'
)
EXCHANGE_RATE_API_KEY = os.getenv('EXCHANGE_RATE_API_KEY', '')
EXCHANGE_RATE_CACHE_HOURS = int(os.getenv('EXCHANGE_RATE_CACHE_HOURS', '12'))

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'shopseed',
    },
}

STATIC_ROOT = os.path.join(PROJECT_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_DIRS = (os.path.join(PROJECT_DIR, 'static'),)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CART_SESSION_ID = 'cart'

# Order tax rate (decimal fraction, e.g. 0.18 = 18% GST) applied to items + shipping.
ORDER_TAX_RATE = os.getenv('ORDER_TAX_RATE', '0.18')

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Mount Django admin under an unusual path in production to reduce exposure to
# scanner-visible /admin/. Dev keeps a memorable default.
ADMIN_URL = os.getenv('ADMIN_URL', 'admin/')

# ---------------------------------------------------------------------------
# Logistics Management System (LMS)
# ---------------------------------------------------------------------------
LOGISTICS_AWB_PREFIX = os.getenv('LOGISTICS_AWB_PREFIX', 'SSD')
LOGISTICS_DEFAULT_CURRENCY = os.getenv('LOGISTICS_DEFAULT_CURRENCY', 'INR')
LOGISTICS_COURIER_TIMEOUT_SECONDS = int(os.getenv('LOGISTICS_COURIER_TIMEOUT_SECONDS', '30'))
LOGISTICS_COURIER_MAX_RETRIES = int(os.getenv('LOGISTICS_COURIER_MAX_RETRIES', '3'))
LOGISTICS_COURIER_RETRY_BACKOFF = int(os.getenv('LOGISTICS_COURIER_RETRY_BACKOFF', '2'))
LOGISTICS_SHIPMENT_FALLBACK_ATTEMPTS = int(os.getenv('LOGISTICS_SHIPMENT_FALLBACK_ATTEMPTS', '3'))
LOGISTICS_PICKUP_AUTOSCHEDULE = os.getenv('LOGISTICS_PICKUP_AUTOSCHEDULE', 'True') == 'True'
LOGISTICS_TRACKING_BASE_URL = os.getenv('LOGISTICS_TRACKING_BASE_URL', '')
# Per-courier webhook signing secrets, e.g. {"mock": "secret1", "delhivery": "secret2"}
LOGISTICS_WEBHOOK_SECRETS = {}
for _key in ('MOCK_COURIER_WEBHOOK_SECRET', 'MOCKEXPRESS_COURIER_WEBHOOK_SECRET', 'DELHIVERY_WEBHOOK_SECRET'):
    _secret = os.getenv(_key)
    if _secret:
        _code = _key.split('_WEBHOOK_SECRET')[0].replace('MOCKEXPRESS', 'mockexpress').replace('MOCK_COURIER', 'mock').replace('DELHIVERY', 'delhivery').lower()
        LOGISTICS_WEBHOOK_SECRETS[_code] = _secret



# Email — SMTP only when fully configured (host + user + password),
# otherwise console backend prints messages to the terminal
_EMAIL_SMTP_CONFIGURED = all(
    os.getenv(key)
    for key in ('EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD')
)
EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
    if _EMAIL_SMTP_CONFIGURED
    else 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Shop-Seed <no-reply@shop-seed.com>')
SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = 'DENY'

# ---------------------------------------------------------------------------
# Content-Security-Policy / Permissions-Policy (enforced by core.middleware)
# ---------------------------------------------------------------------------
# Inline styles/scripts are allowed because the templates use them heavily;
# the policy still blocks injected *external* scripts, plugins, frames and
# data-exfiltration endpoints. The |richtext| sanitizer remains the primary
# stored-XSS defence.
SECURITY_CSP = '; '.join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://www.googletagmanager.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com",
    "img-src 'self' data: https:",
    "connect-src 'self' https://api.razorpay.com https://*.razorpay.com https://www.google-analytics.com https://*.google-analytics.com https://*.googletagmanager.com https://stats.g.doubleclick.net",
    "media-src 'self' https: data:",
    "frame-src https://checkout.razorpay.com https://api.razorpay.com https://www.youtube-nocookie.com https://player.vimeo.com",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])
SECURITY_PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), battery=(), usb=(), interest-cohort=()'

# Upload safety: reject oversized POST bodies early (before they hit memory).
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
