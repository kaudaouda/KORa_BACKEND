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
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
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
            'sensitive_rate': '10/min',
        }
    cache.set('throttle_config', result, 60)
    return result


def _is_whitelisted(ip):
    """Vérifie la liste blanche LoginSecurityConfig (partagée avec IPBlockMiddleware)."""
    from django.core.cache import cache
    config = cache.get('ip_block_config')
    if config is None:
        try:
            from parametre.models import LoginSecurityConfig
            cfg = LoginSecurityConfig.get_config()
            config = {'enabled': cfg.enabled, 'whitelist': cfg.get_whitelist()}
        except Exception:
            config = {'enabled': False, 'whitelist': []}
        cache.set('ip_block_config', config, 60)
    return ip in config.get('whitelist', [])


# ── Classes de throttle ────────────────────────────────────────────────────────

class KoraAnonThrottle(AnonRateThrottle):
    """Limite les requêtes non authentifiées par IP."""

    def get_rate(self):
        cfg = _get_throttle_config()
        return cfg['anon_rate'] if cfg['enabled'] else None

    def get_ident(self, request):
        return _get_ip(request)

    def allow_request(self, request, view):
        if _is_whitelisted(_get_ip(request)):
            return True
        return super().allow_request(request, view)


class KoraUserThrottle(UserRateThrottle):
    """Limite les requêtes authentifiées par user."""

    def get_rate(self):
        cfg = _get_throttle_config()
        return cfg['user_rate'] if cfg['enabled'] else None

    def allow_request(self, request, view):
        if _is_whitelisted(_get_ip(request)):
            return True
        return super().allow_request(request, view)


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

    def allow_request(self, request, view):
        if _is_whitelisted(_get_ip(request)):
            return True
        return super().allow_request(request, view)
