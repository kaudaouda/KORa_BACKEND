"""
Django settings — PRODUCTION
"""
from .base import *
import os

DEBUG = False

_allowed_hosts_env = os.getenv('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]

# ── Cookies & HTTPS ───────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Referrer Policy (NEW-H) ───────────────────────────────────────────────────
# Empêche les tokens/uid présents dans les URLs d'invitation/reset de fuiter
# dans l'en-tête Referer lors du chargement de ressources externes.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ── CORS — uniquement les origines de production (NEW-F) ─────────────────────
# base.py inclut localhost pour le développement ; on écrase ici pour la prod.
_cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]

# ── Content-Security-Policy (NEW-G) ──────────────────────────────────────────
# Posé par ContentSecurityPolicyMiddleware (shared/middleware.py).
# Défense en profondeur contre XSS et exfiltration — adapte connect-src
# si des services tiers sont appelés depuis le frontend.
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)

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
