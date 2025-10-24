"""
Handler personnalisé pour les exceptions Django REST Framework
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Handler personnalisé pour capturer toutes les exceptions
    """
    # Appeler le handler par défaut
    response = exception_handler(exc, context)
    
    if response is None:
        # Si le handler par défaut ne retourne rien, on crée une réponse personnalisée
        return Response({
            'success': False,
            'error': str(exc),
            'type': type(exc).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response
