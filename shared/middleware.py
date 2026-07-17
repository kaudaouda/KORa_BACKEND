from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
import logging
import os

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_ip(request):
    # Security by Design — lit TRUSTED_PROXY_COUNT pour éviter que le client
    # contrôle son IP en forgeant X-Forwarded-For.
    trusted_proxy_count = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    if trusted_proxy_count > 0:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ips = [ip.strip() for ip in xff.split(',') if ip.strip()]
        if ips:
            idx = max(0, len(ips) - trusted_proxy_count)
            return ips[idx]
    return request.META.get('REMOTE_ADDR')


class JWTCookieMiddleware(MiddlewareMixin):
    """
    Middleware pour gérer les tokens JWT dans les cookies
    Lit le JWT depuis les cookies et authentifie l'utilisateur
    """
    
    _USER_CACHE_TTL = 60 * 5  # 5 minutes

    def process_request(self, request):
        """
        Lire le JWT depuis les cookies et authentifier l'utilisateur
        """
        access_token = request.COOKIES.get('access_token')

        # Security by Design — ne jamais authentifier via cookie JWT sur l'admin
        # Django : le cookie access_token est posé avec domain=.anac.ci (voir
        # shared/authentication.py), donc visible depuis n'importe quel sous-domaine.
        # Sans cette exclusion, un login sur le frontend (kora.anac.ci) donnait
        # automatiquement accès à l'admin Django (backend-kora.anac.ci) sans jamais
        # passer par son propre formulaire de connexion ni créer de session —
        # has_permission() de l'admin se contente de lire request.user.is_staff,
        # peu importe comment il a été posé.
        admin_prefix = f"/{os.getenv('DJANGO_ADMIN_URL', 'admin/')}"
        if request.path.startswith(admin_prefix):
            return

        if access_token and not request.user.is_authenticated:
            try:
                token = AccessToken(access_token)
                user_id = token.get('user_id')

                cache_key = f'jwt_user:{user_id}'
                user = cache.get(cache_key)
                if user is None:
                    user = User.objects.get(id=user_id)
                    cache.set(cache_key, user, self._USER_CACHE_TTL)

                # Un compte peut être désactivé après que le cache l'a mémorisé.
                if not user.is_active:
                    logger.debug("JWT cookie refusé — compte inactif (id=%s)", user_id)
                    return

                request.user = user
                logger.debug("Utilisateur authentifié depuis JWT cookie: id=%s", user_id)

            except (InvalidToken, TokenError, User.DoesNotExist) as e:
                logger.debug("Erreur authentification JWT cookie: %s", type(e).__name__)
                pass
    
    def process_response(self, request, response):
        # Si une nouvelle access token a été générée, l'ajouter au cookie
        if hasattr(request, '_new_access_token'):
            response.set_cookie(
                'access_token',
                request._new_access_token,
                max_age=30 * 60,
                httponly=True,
                samesite='Lax',
                secure=not settings.DEBUG,
            )
            logger.debug("Nouveau access token ajouté au cookie")
        
        return response


class AdminLoginRateLimitMiddleware(MiddlewareMixin):
    """
    Rate limit sur le formulaire de login Django admin.
    5 tentatives POST par IP sur 60 secondes.
    """
    MAX_ATTEMPTS = 5
    WINDOW = 60  # secondes

    def process_request(self, request):
        admin_url = f"/{os.getenv('DJANGO_ADMIN_URL', 'admin/')}login/"
        if request.method == 'POST' and request.path == admin_url:
            ip = _get_ip(request)
            key = f'admin_login_ratelimit:{ip}'
            # Security by Design — incrément atomique (cache.add + cache.incr) :
            # évite le TOCTOU du pattern read-check-write non atomique.
            cache.add(key, 0, self.WINDOW)
            attempts = cache.incr(key)
            if attempts > self.MAX_ATTEMPTS:
                logger.warning("Admin login rate limit atteint pour IP %s", ip)
                return HttpResponseForbidden('Trop de tentatives. Réessayez dans quelques minutes.')
        return None


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Pose le header Content-Security-Policy depuis settings.CONTENT_SECURITY_POLICY.
    Security by Design — défense en profondeur : limite les sources autorisées
    pour scripts, styles, images et connexions, réduisant la surface XSS/exfiltration.
    Actif uniquement si CONTENT_SECURITY_POLICY est défini (prod.py).
    """

    def process_response(self, request, response):
        csp = getattr(settings, 'CONTENT_SECURITY_POLICY', None)
        if csp and 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = csp
        return response


class MediaFrameOptionsMiddleware(MiddlewareMixin):
    """
    Middleware personnalisé pour permettre l'affichage en iframe des fichiers média
    tout en gardant la protection X-Frame-Options pour le reste de l'application
    """
    
    def process_response(self, request, response):
        # Autoriser explicitement l'affichage des fichiers médias en iframe
        # depuis le front Vite en dev (localhost/127.0.0.1:5173).
        if request.path.startswith('/medias/'):
            # Retirer l'en-tête X-Frame-Options (déconseillé et trop restrictif)
            if 'X-Frame-Options' in response:
                del response['X-Frame-Options']

            # Définir une politique CSP qui autorise les ancêtres spécifiés
            # Note: frame-ancestors contrôle QUI peut encapsuler cette ressource.
            allowed_ancestors = [
                "'self'",
                'http://localhost:5173',
                'http://127.0.0.1:5173',
            ]

            csp_value = f"frame-ancestors {' '.join(allowed_ancestors)}"

            # Conserver d'autres directives CSP existantes si présentes et remplacer/ajouter frame-ancestors
            existing_csp = response.get('Content-Security-Policy')
            if existing_csp:
                # Si une directive frame-ancestors existe déjà, on la remplace.
                directives = []
                replaced = False
                for directive in existing_csp.split(';'):
                    d = directive.strip()
                    if d.lower().startswith('frame-ancestors'):
                        directives.append(csp_value)
                        replaced = True
                    elif d:
                        directives.append(d)
                if not replaced:
                    directives.append(csp_value)
                response['Content-Security-Policy'] = '; '.join(directives)
            else:
                response['Content-Security-Policy'] = csp_value
        else:
            # Pour le reste de l'application, laisser X-Frame-Options géré par le middleware Django
            # et ne pas modifier la CSP ici.
            pass

        return response