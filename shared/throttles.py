"""
Throttles DRF — protection anti-DDoS applicative (L7).

Taux configurables depuis Django admin via ThrottleConfig (singleton).
Les modifications prennent effet en < 60s (TTL cache).

  - KoraAnonThrottle       : IPs anonymes         (défaut : 100/min)
  - KoraUserThrottle       : users authentifiés   (défaut : 600/min)
  - KoraSensitiveThrottle  : login/reset/invitation (défaut : 10/min)

Remarque production : DRF utilise le cache Django pour les compteurs.
Avec plusieurs workers gunicorn, configurer Redis :
    CACHES = {'default': {'BACKEND': 'django_redis.cache.RedisCache', ...}}
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, SimpleRateThrottle


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_ip(request):
    # Security by Design — même logique que shared.middleware._get_ip() :
    # on lit TRUSTED_PROXY_COUNT pour éviter que le client contrôle son IP
    # en forgeant X-Forwarded-For (bypass du rate-limiting sinon possible).
    from django.conf import settings
    trusted = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    if trusted > 0:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ips = [ip.strip() for ip in xff.split(',') if ip.strip()]
        if ips:
            idx = max(0, len(ips) - trusted)
            return ips[idx]
    return request.META.get('REMOTE_ADDR', '')


def _get_throttle_config():
    """Lit ThrottleConfig depuis le cache (60s TTL). Fallback sur les valeurs par défaut."""
    from django.core.cache import cache
    cached = cache.get('throttle_config')
    if cached is not None:
        return cached
    try:
        from parametre.models import ThrottleConfig
        cfg = ThrottleConfig.get_config()
        result = {
            'enabled':        cfg.enabled,
            'anon_rate':      cfg.anon_rate,
            'user_rate':      cfg.user_rate,
            'sensitive_rate': cfg.sensitive_rate,
        }
    except Exception:
        result = {
            'enabled':        True,
            'anon_rate':      '100/min',
            'user_rate':      '600/min',
            'sensitive_rate': '5/min',
        }
    cache.set('throttle_config', result, 60)
    return result


# ── Classes de throttle ────────────────────────────────────────────────────────

class KoraAnonThrottle(AnonRateThrottle):
    """Limite les requêtes non authentifiées par IP."""

    def get_rate(self):
        cfg = _get_throttle_config()
        return cfg['anon_rate'] if cfg['enabled'] else None

    def get_ident(self, request):
        return _get_ip(request)


class KoraUserThrottle(UserRateThrottle):
    """Limite les requêtes authentifiées par user."""

    def get_rate(self):
        cfg = _get_throttle_config()
        return cfg['user_rate'] if cfg['enabled'] else None


class KoraSensitiveThrottle(SimpleRateThrottle):
    """
    Endpoints sensibles : login, reset password, invitation.
    Limite par IP indépendamment de l'authentification.
    """
    scope = 'sensitive'

    def get_rate(self):
        cfg = _get_throttle_config()
        return cfg['sensitive_rate'] if cfg['enabled'] else None

    def get_ident(self, request):
        return _get_ip(request)

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': ident}
