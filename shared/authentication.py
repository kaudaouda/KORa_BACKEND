"""
Services d'authentification partagés
"""
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.exceptions import AuthenticationFailed
import logging

logger = logging.getLogger(__name__)


class CookieJWTAuthentication(JWTAuthentication):
    """
    Authentification JWT personnalisée qui lit les tokens depuis les cookies
    """
    
    def authenticate(self, request):
        # Essayer d'abord l'authentification par cookie
        access_token = request.COOKIES.get('access_token')

        if access_token:
            try:
                validated_token = self.get_validated_token(access_token)
                user = self.get_user(validated_token)
                return (user, validated_token)
            except (InvalidToken, TokenError, AuthenticationFailed):
                # Access token expiré ou invalide — tenter un refresh silencieux
                refresh_token = request.COOKIES.get('refresh_token')
                if refresh_token:
                    try:
                        refresh = RefreshToken(refresh_token)
                        new_access_token = refresh.access_token
                        # Le middleware JWTCookieMiddleware.process_response() posera
                        # le nouveau cookie sur la réponse
                        request._new_access_token = str(new_access_token)
                        validated_token = self.get_validated_token(str(new_access_token))
                        user = self.get_user(validated_token)
                        return (user, validated_token)
                    except (InvalidToken, TokenError, AuthenticationFailed):
                        pass

        # Fallback sur l'authentification par header Authorization
        return super().authenticate(request)


class AuthService:
    """Service d'authentification partagé"""
    
    @staticmethod
    def create_tokens(user):
        """
        Créer les tokens JWT pour un utilisateur
        
        Args:
            user: Instance de User Django
            
        Returns:
            tuple: (access_token, refresh_token)
        """
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        return str(access_token), str(refresh)
    
    @staticmethod
    def set_auth_cookies(response, access_token, refresh_token):
        """
        Définir les cookies d'authentification
        
        Args:
            response: Response Django
            access_token: Token d'accès
            refresh_token: Token de rafraîchissement
            
        Returns:
            Response: Response avec cookies définis
        """
        response.set_cookie(
            'access_token',
            access_token,
            max_age=30 * 60,  # 30 minutes — aligné sur ACCESS_TOKEN_LIFETIME
            httponly=True,
            secure=False,  # True en production avec HTTPS
            samesite='Lax',
            path='/'
        )
        response.set_cookie(
            'refresh_token',
            refresh_token,
            max_age=8 * 60 * 60,  # 8 heures — aligné sur REFRESH_TOKEN_LIFETIME
            httponly=True,
            secure=False,  # True en production avec HTTPS
            samesite='Lax',
            path='/'
        )
        return response
    
    @staticmethod
    def clear_auth_cookies(response):
        """
        Supprimer les cookies d'authentification
        
        Args:
            response: Response Django
            
        Returns:
            Response: Response avec cookies supprimés
        """
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response