"""
Handler personnalisé pour les exceptions Django REST Framework
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    # Throttling → réponse cohérente avec le reste de l'API
    if isinstance(exc, Throttled):
        wait = int(exc.wait) if exc.wait else None
        msg = (
            f'Trop de requêtes. Réessayez dans {wait} seconde{"s" if wait != 1 else ""}.'
            if wait else
            'Trop de requêtes. Réessayez dans quelques instants.'
        )
        return Response(
            {'error': msg, 'code': 'RATE_LIMITED', 'retry_after': wait},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    response = exception_handler(exc, context)

    if response is None:
        return Response({
            'success': False,
            'error': str(exc),
            'type': type(exc).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
