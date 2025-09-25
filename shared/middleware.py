"""
Middleware personnalisé pour la gestion des tokens JWT
"""
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import logging

logger = logging.getLogger(__name__)


class JWTCookieMiddleware(MiddlewareMixin):
    """
    Middleware pour gérer automatiquement le rafraîchissement des tokens JWT
    """
    
    def process_response(self, request, response):
        # Vérifier si une nouvelle access_token a été générée
        if hasattr(request, '_new_access_token'):
            response.set_cookie(
                'access_token',
                request._new_access_token,
                max_age=60 * 60,  # 1 heure
                httponly=True,
                secure=False,  # True en production avec HTTPS
                samesite='Lax',
                path='/'
            )
        
        return response
