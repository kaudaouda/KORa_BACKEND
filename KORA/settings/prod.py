"""
Django settings — PRODUCTION
"""
from .base import *
import os

DEBUG = False

_allowed_hosts_env = os.getenv('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]

# ── Cookies & HTTPS ───────────────────────────────────────────────────────────
# Security by Design — configurable via env, pas hardcodé à True : tant que ce
# déploiement tourne en HTTP simple (pas de certificat TLS), un cookie "Secure"
# est silencieusement rejeté par tout navigateur conforme. Django authentifie
# bien l'utilisateur (302 sur le POST /login/) mais le cookie de session n'atteint
# jamais le navigateur, qui revient donc aussitôt sur la page de connexion sans
# aucun message d'erreur. Repasser à True (valeur par défaut) dès que le HTTPS
# est activé — voir SECURE_SSL_REDIRECT, qui suit le même pattern.
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True') == 'True'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True') == 'True'
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True') == 'True'
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
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
