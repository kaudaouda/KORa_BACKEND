from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class JWTCookieMiddleware(MiddlewareMixin):
    """
    Middleware pour gérer les tokens JWT dans les cookies
    Lit le JWT depuis les cookies et authentifie l'utilisateur
    """
    
    def process_request(self, request):
        """
        Lire le JWT depuis les cookies et authentifier l'utilisateur
        """
        # Récupérer le token depuis les cookies
        access_token = request.COOKIES.get('access_token')
        
        if access_token and not request.user.is_authenticated:
            try:
                # Valider et décoder le token
                token = AccessToken(access_token)
                user_id = token.get('user_id')
                
                # Récupérer l'utilisateur
                user = User.objects.get(id=user_id)
                
                # Attacher l'utilisateur à la requête
                request.user = user
                logger.debug(f"Utilisateur authentifié depuis JWT cookie: {user.username}")
                
            except (InvalidToken, TokenError, User.DoesNotExist) as e:
                logger.debug(f"Erreur authentification JWT cookie: {e}")
                pass  # Laisser request.user tel quel (AnonymousUser)
    
    def process_response(self, request, response):
        # Si une nouvelle access token a été générée, l'ajouter au cookie
        if hasattr(request, '_new_access_token'):
            response.set_cookie(
                'access_token',
                request._new_access_token,
                max_age=3600,  # 1 heure
                httponly=True,
                samesite='Lax',
                secure=False  # True en production avec HTTPS
            )
            logger.debug("Nouveau access token ajouté au cookie")
        
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