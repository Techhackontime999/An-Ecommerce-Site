"""Django settings for config project - Production."""

import os
import dotenv
import dj_database_url

from core.sentry import init_sentry
from .languages import available_languages

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)

dotenv_file = os.path.join(PROJECT_DIR, ".env")
if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

# Error tracking (no-op unless SENTRY_DSN is set).
init_sentry(environment='production')

SECRET_KEY = os.getenv("SECRET_KEY")

# Fernet key for encrypting sensitive fields (courier API credentials).
# Required in production, exactly like SECRET_KEY.
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")

DEBUG = False

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()
if RENDER_EXTERNAL_URL:
    RENDER_HOST = RENDER_EXTERNAL_URL.replace("https://", "").split("/")[0]
    ALLOWED_HOSTS = [RENDER_HOST, 'localhost', '127.0.0.1']
    CSRF_TRUSTED_ORIGINS = [f'https://{RENDER_HOST}']
else:
    ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
    ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]

    CSRF_TRUSTED_ENV = os.getenv("CSRF_TRUSTED_ORIGINS", "")
    if CSRF_TRUSTED_ENV:
        CSRF_TRUSTED_ORIGINS = [o.strip() for o in CSRF_TRUSTED_ENV.split(",") if o.strip()]
    else:
        CSRF_TRUSTED_ORIGINS = []

SITE_URL = os.getenv("SITE_URL", RENDER_EXTERNAL_URL or "")

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

    'shop.apps.ShopConfig',
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
    'blogs.apps.BlogsConfig',
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
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
PAYMENTS_CURRENCY = os.getenv("PAYMENTS_CURRENCY", "INR")

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
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
LANGUAGE_COOKIE_SECURE = True  # site is served over HTTPS

# Live currency conversion — fetched from a free exchange-rate API and cached.
EXCHANGE_RATE_API_URL = os.getenv(
    'EXCHANGE_RATE_API_URL', 'https://open.er-api.com/v6/latest/{base}'
)
EXCHANGE_RATE_API_KEY = os.getenv('EXCHANGE_RATE_API_KEY', '')
EXCHANGE_RATE_CACHE_HOURS = int(os.getenv('EXCHANGE_RATE_CACHE_HOURS', '12'))

REDIS_URL = os.getenv("REDIS_URL", "").strip()

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'db': int(os.getenv("REDIS_DB", "0")),
            },
        },
    }
    # cached_db reads sessions from Redis and falls back to the DB, so a Redis
    # restart never logs anyone out.
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'shopseed_cache',
            'OPTIONS': {
                'MAX_ENTRIES': int(os.getenv("CACHE_MAX_ENTRIES", "1000")),
                'CULL_FREQUENCY': int(os.getenv("CACHE_CULL_FREQUENCY", "3")),
            },
        },
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'
USE_TZ = True

STATIC_ROOT = os.path.join(PROJECT_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_DIRS = (os.path.join(PROJECT_DIR, 'static'),)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# Media files (product/blog/review images, courier labels, CKEditor uploads)
# ---------------------------------------------------------------------------
# Render's disk is ephemeral: uploaded files disappear on every redeploy and
# are never served in production. Point AWS_STORAGE_BUCKET_NAME at an S3 bucket
# (boto3 + django-storages are already in requirements.txt) so media is
# persistent and served from S3. Without a bucket, media stays local-only.
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "").strip()
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", os.getenv("AWS_SES_REGION", "us-east-1"))
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

if AWS_STORAGE_BUCKET_NAME:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    }
    MEDIA_URL = (
        f"https://s3.{AWS_S3_REGION_NAME}.amazonaws.com/"
        f"{AWS_STORAGE_BUCKET_NAME}/"
    )
else:
    MEDIA_URL = '/media/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CART_SESSION_ID = 'cart'

# Order tax rate (decimal fraction, e.g. 0.18 = 18% GST) applied to items + shipping.
ORDER_TAX_RATE = os.getenv('ORDER_TAX_RATE', '0.18')

# Email — SMTP/SES via env (EMAIL_BACKEND override for SES)
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Shop-Seed <no-reply@shop-seed.com>')

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Mount Django admin under an unusual path in production to reduce exposure to
# scanner-visible /admin/. Set ADMIN_URL (e.g. a random segment) in .env.
ADMIN_URL = os.getenv("ADMIN_URL", "admin/")

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True") == "True"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True") == "True"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True") == "True"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "True") == "True"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

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

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
