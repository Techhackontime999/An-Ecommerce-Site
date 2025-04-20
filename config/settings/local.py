"""Django settings for config project."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = '5yo93-8a^%idwkzxz@6gq67p2ml#sraf4=7#pqg+28mv)koo@m'

DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    #third-party apps
    'crispy_forms',
    'ckeditor',
    'django_extensions', #remove this if you not want to generate database gui visualization
    'shop.apps.ShopConfig',
    'cart.apps.CartConfig',
    'order.apps.OrderConfig',
    'coupons.apps.CouponsConfig',
    # 'reviews.apps.ReviewsConfig',





    'accounts',
    'about',
    'contact',
    'services',
      'deals',
      'core',
      'documentation',
        'faq',
        'seller',
        'search',
        'reviews',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField' #remove this if you not want to generate database visualization
#for linux first install required system dependency not project 

#1. sudo apt-get install graphviz graphviz-dev pkg-config libgraphviz-dev
#2. pip install django-extensions

# 3. pip install pygraphviz  this cmd build project dependency for database gui

#4.  python manage.py graph_models -a -o db_structure.png     use this cmd to generate database gui visualization

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                 'shop.context_processors.search_action_context',

                #  'config.context_processors.page_context',  # global
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = '/media/'


#Crispy templates for form rendering
CRISPY_TEMPLATE_PACK = 'bootstrap4'

CART_SESSION_ID = 'cart'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'  # Not /cart/
LOGOUT_REDIRECT_URL = '/'


# LOGIN_URL = 'login'
# LOGIN_REDIRECT_URL = 'shop:product_list'  # or your homepage
# LOGOUT_REDIRECT_URL = 'login'
