"""
Django settings — PRODUCTION
"""
from .base import *
import os

DEBUG = False

_allowed_hosts_env = os.getenv('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'shared.authentication': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
        'pac.views':             {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
        'parametre.scheduler':   {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'apscheduler':           {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
