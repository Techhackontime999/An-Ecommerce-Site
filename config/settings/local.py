"""Django settings for config project - Local Development."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-development-only")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_xxxxxxxxxxxx")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "your_test_secret")

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
    'search',
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
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
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
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('hi', 'हिन्दी'),
    ('es', 'Español'),
    ('fr', 'Français'),
    ('de', 'Deutsch'),
    ('pt', 'Português'),
    ('it', 'Italiano'),
    ('ja', '日本語'),
    ('ko', '한국어'),
    ('zh-hans', '简体中文'),
    ('ar', 'العربية'),
    ('ru', 'Русский'),
    ('tr', 'Türkçe'),
    ('nl', 'Nederlands'),
    ('pl', 'Polski'),
    ('bn', 'বাংলা'),
    ('ta', 'தமிழ்'),
    ('te', 'తెలుగు'),
    ('mr', 'मराठी'),
]

LOCALE_PATHS = [
    os.path.join(PROJECT_DIR, 'locale'),
]

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

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

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

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
