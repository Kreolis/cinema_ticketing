"""
Django settings for cinema_tickets project.

Generated by 'django-admin startproject' using Django 4.2.16.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
from decouple import config
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

if config('ALLOWED_HOSTS', default=None):
    ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'payments',     # payment handling
    'bootstrap5',   # bootstrap5 support
    'rosetta',      # translation management
    'captcha',      # captcha support
    
    # custom apps
    'branding',     # branding management
    'events',       # events management
    'accounting',   # payment and order management
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.locale.LocaleMiddleware', # translation support
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cinema_tickets.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cinema_tickets.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

if config('USE_POSTGRES', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('POSTGRES_DB'),
            'USER': config('POSTGRES_USER'),
            'PASSWORD': config('POSTGRES_PASSWORD'),
            'HOST': config('POSTGRES_HOST'),
            'PORT': config('POSTGRES_PORT'),
        }
    }

else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en'

TIME_ZONE = 'UTC'

# Activate internationalization
USE_I18N = True
USE_L10N = True

USE_TZ = True

# Automatically compile .po files to .mo files
ROSETTA_AUTO_COMPILE=True

from django.utils.translation import gettext_lazy as _

LANGUAGES = (
    ('en', _('English')),
    ('de', _('German')),
)

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# Session settings
# Use database-backed sessions to persist session data between requests
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Secure session cookies
SESSION_COOKIE_SECURE = True  # Ensures cookies are only sent over HTTPS
SESSION_COOKIE_HTTPONLY = True  # Prevents JavaScript access to the cookie
SESSION_COOKIE_SAMESITE = 'Strict'  # Blocks cookies from being sent with cross-site requests (prevents CSRF)

# Session timeout settings
SESSION_COOKIE_AGE = 1800  # in sec, 30 minutes of inactivity before expiration
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Session survives browser close, allows users to continue orders

# Save session on every user request
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session expiration on activity

# Media files settings
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

## DJANGO-PAYMENTS SETTINGS

# define default CURRENCY
# see a list of available currencies here: https://django-money.readthedocs.io/en/latest/
CURRENCIES = ('EUR')
CURRENCY_CHOICES = [('EUR', 'EUR €')]
DEFAULT_CURRENCY = 'EUR'

# Set this to True to be able to delete paid orders.
# in DEBUG mode this is always True.
if DEBUG:
    CONFIRM_DELETE_PAID_ORDER = True
else:
    CONFIRM_DELETE_PAID_ORDER = False

# Mail settings
# Email backend configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587)  # Typically 587 for TLS, 465 for SSL
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)  # Use TLS (True) or SSL (False)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='your-email@example.com')  # Replace with your email address
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='your-email-password')  # Replace with your email password
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='your-email@example.com')  # Replace with your default from email address

# This can be a string or callable, and should return a base host that
# will be used when receiving callbacks and notifications from payment
# providers.
#
# Keep in mind that if you use `localhost`, external servers won't be
# able to reach you for webhook notifications.
PAYMENT_HOST = 'localhost:8000'
#PAYMENT_PROTOCOL = 'https'

# Whether to use TLS (HTTPS). If false, will use plain-text HTTP.
# Defaults to ``not settings.DEBUG``.
PAYMENT_USES_SSL = False

# A dotted path to the Payment class.
PAYMENT_MODEL = 'accounting.Order'

# Stripe credentials
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY')
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY')

# Named configuration for your payment provider(s).
PAYMENT_VARIANTS = {}

if config('USE_STRIPE', default=False, cast=bool):
    PAYMENT_VARIANTS['stripe'] = (
        'payments.stripe.StripeProviderV3',
        {
            'api_key': STRIPE_SECRET_KEY,
            'use_token': True,
            'secure_endpoint': True,
            'endpoint_secret': config('STRIPE_WEBHOOK_SECRET', default='whsec_test_secret'),
        }
    )

if config('USE_PAYPAL', default=False, cast=bool):
    PAYMENT_VARIANTS['paypal'] = (
        'payments.paypal.PaypalProvider',
        {
            'client_id': config('PAYPAL_CLIENT_ID'),
            'secret': config('PAYPAL_SECRET'),
            'endpoint': 'https://api.paypal.com', # for production
            'capture': False,
        }
    )
if config('USE_ADVANCE_PAYMENT', default=False, cast=bool):
    PAYMENT_VARIANTS['advance_payment'] = (
        'accounting.custom_advance_payment_provider.AdvancePaymentProvider',
        {
            'capture': True,
        }
    )

if DEBUG:
    if config('USE_STRIPE', default=False, cast=bool):
        # enable test mode for Stripe and use insecure endpoint
        PAYMENT_VARIANTS['stripe'][1]['secure_endpoint'] = False
    
    if config('USE_PAYPAL', default=False, cast=bool):
        # use sandbox endpoint for testing
        PAYMENT_VARIANTS['paypal'][1]['endpoint'] = 'https://api.sandbox.paypal.com'

    # add dummy payment provider for testing
    PAYMENT_VARIANTS['dummy'] = ('payments.dummy.DummyProvider', {'capture': False})

DEFAULT_PAYMENT_VARIANT = config('DEFAULT_GATEWAY')
if DEFAULT_PAYMENT_VARIANT not in PAYMENT_VARIANTS:
    print(f"Default payment variant {DEFAULT_PAYMENT_VARIANT} not found in PAYMENT_VARIANTS")
    print("Available payment variants:")
    for key in PAYMENT_VARIANTS:
        print(f"  {key}")

HUMANIZED_PAYMENT_VARIANT = {
    'stripe': _('Stripe (Credit Card)'),
    'paypal': _('Paypal'),
    'advance_payment': _('Advance Payment'),
    'dummy': _('Dummy Payment'),
}
