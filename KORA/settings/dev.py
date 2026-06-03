"""
Django settings — DÉVELOPPEMENT
"""
from .base import *
import os

DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

_APP_LOG_LEVEL = 'DEBUG' if DEBUG else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'shared.authentication': {'handlers': ['console'], 'level': _APP_LOG_LEVEL, 'propagate': True},
        'pac.views':             {'handlers': ['console'], 'level': _APP_LOG_LEVEL, 'propagate': True},
        'parametre.scheduler':   {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'apscheduler':           {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
