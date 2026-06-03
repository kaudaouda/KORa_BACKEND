"""
Handler personnalisé pour les exceptions Django REST Framework
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
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
        logger.error(
            "Unhandled exception: %s: %s", type(exc).__name__, exc,
            exc_info=True,
            extra={'view': context.get('view').__class__.__name__ if context.get('view') else None},
        )
        body = {'success': False, 'error': 'Une erreur interne est survenue.'}
        if settings.DEBUG:
            body['detail'] = str(exc)
            body['type'] = type(exc).__name__
        return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
