"""
Django settings — BASE (commun à tous les environnements)
"""
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security by Design — Fail Secure :
# Le serveur refuse de démarrer si les clés cryptographiques sont absentes ou trop courtes.
# Un démarrage silencieux avec SECRET_KEY=None produit des JWT non signés ou non vérifiables.
_SECRET_KEY = os.getenv('SECRET_KEY', '')
if not _SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY est absente. Définissez SECRET_KEY dans le fichier .env. "
        "Générez-en une avec : python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    )
if len(_SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        f"SECRET_KEY est trop courte ({len(_SECRET_KEY)} caractères, minimum 50). "
        "Une clé trop courte est cryptographiquement faible."
    )
SECRET_KEY = _SECRET_KEY

_JWT_SIGNING_KEY = os.getenv('JWT_SIGNING_KEY', SECRET_KEY)
if not _JWT_SIGNING_KEY:
    raise ImproperlyConfigured(
        "JWT_SIGNING_KEY est absente et SECRET_KEY ne peut pas servir de fallback. "
        "Définissez JWT_SIGNING_KEY dans le fichier .env."
    )
JWT_SIGNING_KEY = _JWT_SIGNING_KEY

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_apscheduler',
    'pac',
    'activite_periodique',
    'documentation',
    'parametre',
    'dashboard',
    'cartographie_risque',
    'permissions',
    'analyse_tableau',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'shared.middleware.AdminLoginRateLimitMiddleware',
    'shared.cors_middleware.CORSContentTypeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'shared.middleware.ContentSecurityPolicyMiddleware',
    'shared.middleware.MediaFrameOptionsMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'shared.middleware.JWTCookieMiddleware',
    'middleware.application_maintenance.ApplicationMaintenanceMiddleware',
]

ROOT_URLCONF = 'KORA.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'KORA.wsgi.application'

DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite').lower()
if DB_ENGINE == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'kora'),
            'USER': os.getenv('DB_USER', 'kora'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True

# Nombre de proxies de confiance devant Django (0 = dev sans proxy, 1 = 1 nginx, etc.)
# Utilisé par shared.middleware._get_ip() et shared.throttles._get_ip() pour lire le bon XFF index.
TRUSTED_PROXY_COUNT = int(os.getenv('TRUSTED_PROXY_COUNT', '0'))

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/medias/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'medias')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://kora.anac.ci",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

X_FRAME_OPTIONS = 'DENY'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'shared.authentication.CookieJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'shared.parsers.PlainTextAsJSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'EXCEPTION_HANDLER': 'shared.exception_handler.custom_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'shared.throttles.KoraAnonThrottle',
        'shared.throttles.KoraUserThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon':      '100/min',
        'user':      '600/min',
        'sensitive': '5/min',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=2),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': JWT_SIGNING_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

RECAPTCHA_SECRET_KEY = os.getenv('RECAPTCHA_SECRET_KEY', None)
RECAPTCHA_SITE_KEY = os.getenv('RECAPTCHA_SITE_KEY', None)
RECAPTCHA_MIN_SCORE = float(os.getenv('RECAPTCHA_MIN_SCORE', '0.5'))
if not RECAPTCHA_SECRET_KEY or not RECAPTCHA_SITE_KEY:
    RECAPTCHA_SECRET_KEY = None
    RECAPTCHA_SITE_KEY = None

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'false').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'KORA Notifications <noreply@kora.local>')
PASSWORD_RESET_TIMEOUT = int(os.getenv('PASSWORD_RESET_TIMEOUT', '14400'))
INVITATION_TOKEN_TIMEOUT = int(os.getenv('INVITATION_TOKEN_TIMEOUT', '604800'))
FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', 'http://localhost:5173')
EMAIL_ENCRYPTION_KEY = os.getenv('EMAIL_ENCRYPTION_KEY', None)

if not EMAIL_ENCRYPTION_KEY:
    import logging
    logging.getLogger(__name__).warning("EMAIL_ENCRYPTION_KEY non définie dans .env")
