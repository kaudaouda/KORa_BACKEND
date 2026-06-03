"""
Helpers pour construire des réponses API cohérentes.

Format canonique :
  Succès  → {'success': True,  'data': <payload>,  'message': <str|None>}
  Erreur  → {'success': False, 'error': <str>,     'code': <str|None>}

Utilisation :
    from shared.responses import ok, err

    return ok(data=serializer.data, message='Créé avec succès')
    return err('Processus introuvable.', code='NOT_FOUND', http_status=404)

Les champs supplémentaires sont toujours acceptés via **kwargs :
    return ok(data=items, count=len(items))
    return err('Champs manquants.', code='VALIDATION_ERROR', fields=errors)
"""
from rest_framework.response import Response
from rest_framework import status as http_status_module


def ok(data=None, message=None, http_status=http_status_module.HTTP_200_OK, **kwargs):
    """Réponse de succès normalisée."""
    body = {'success': True}
    if data is not None:
        body['data'] = data
    if message is not None:
        body['message'] = message
    body.update(kwargs)
    return Response(body, status=http_status)


def created(data=None, message=None, **kwargs):
    """Raccourci pour HTTP 201."""
    return ok(data=data, message=message, http_status=http_status_module.HTTP_201_CREATED, **kwargs)


def err(error, code=None, http_status=http_status_module.HTTP_400_BAD_REQUEST, **kwargs):
    """Réponse d'erreur normalisée."""
    body = {'success': False, 'error': error}
    if code is not None:
        body['code'] = code
    body.update(kwargs)
    return Response(body, status=http_status)


def not_found(error='Ressource introuvable.', code='NOT_FOUND'):
    return err(error, code=code, http_status=http_status_module.HTTP_404_NOT_FOUND)


def forbidden(error='Accès refusé.', code='FORBIDDEN'):
    return err(error, code=code, http_status=http_status_module.HTTP_403_FORBIDDEN)


def server_error(error='Une erreur interne est survenue.', code='INTERNAL_ERROR'):
    return err(error, code=code, http_status=http_status_module.HTTP_500_INTERNAL_SERVER_ERROR)
