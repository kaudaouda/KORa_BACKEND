"""
Handler personnalisé pour les exceptions Django REST Framework.
Toutes les erreurs non gérées passent par ici et respectent le format canonique :
  {'success': False, 'error': <message>, 'code': <code>}
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled, ValidationError, NotAuthenticated, AuthenticationFailed, PermissionDenied, NotFound
from rest_framework import status
from django.conf import settings
from shared.responses import err
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    view_name = context.get('view').__class__.__name__ if context.get('view') else 'unknown'

    # Throttling
    if isinstance(exc, Throttled):
        wait = int(exc.wait) if exc.wait else None
        msg = (
            f'Trop de requêtes. Réessayez dans {wait} seconde{"s" if wait != 1 else ""}.'
            if wait else
            'Trop de requêtes. Réessayez dans quelques instants.'
        )
        return err(msg, code='RATE_LIMITED', http_status=status.HTTP_429_TOO_MANY_REQUESTS, retry_after=wait)

    # Erreurs DRF standard — on normalise le format de réponse
    response = exception_handler(exc, context)

    if response is not None:
        # DRF retourne {'detail': '...'} ou {'field': ['error']} — on normalise
        data = response.data
        if isinstance(data, dict) and 'detail' in data and len(data) == 1:
            code_map = {
                NotAuthenticated:    'NOT_AUTHENTICATED',
                AuthenticationFailed: 'AUTHENTICATION_FAILED',
                PermissionDenied:    'PERMISSION_DENIED',
                NotFound:            'NOT_FOUND',
            }
            code = code_map.get(type(exc), 'ERROR')
            return err(str(data['detail']), code=code, http_status=response.status_code)
        # ValidationError avec champs → garder la structure mais ajouter success
        if isinstance(exc, ValidationError):
            return err(
                'Données invalides.',
                code='VALIDATION_ERROR',
                http_status=response.status_code,
                fields=data,
            )
        # Autre réponse DRF — s'assurer que success: False est présent
        if isinstance(data, dict) and 'success' not in data:
            data['success'] = False
        return response

    # Exception non gérée par DRF
    logger.error(
        "Unhandled exception in %s: %s", view_name, exc,
        exc_info=True,
    )
    kwargs = {}
    if settings.DEBUG:
        kwargs['detail'] = str(exc)
        kwargs['type'] = type(exc).__name__
    return err(
        'Une erreur interne est survenue.',
        code='INTERNAL_ERROR',
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        **kwargs,
    )
