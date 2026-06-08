from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import logging

from shared.throttles import KoraAnonThrottle, KoraSensitiveThrottle
from ..models import RecaptchaConfig
from ..serializers import RecaptchaConfigPublicSerializer, RecaptchaConfigAdminSerializer
from parametre.services.recaptcha_service import recaptcha_service
from .utils import log_activity, get_client_ip

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([KoraAnonThrottle])
def recaptcha_config_public(request):
    """
    Retourne la configuration reCAPTCHA destinée au frontend.
    Aucune clé secrète n'est exposée.
    """
    try:
        return Response(recaptcha_service.get_public_config(), status=status.HTTP_200_OK)
    except Exception as exc:
        logger.error("recaptcha_config_public: %s", exc)
        return Response(
            {'error': 'Configuration de sécurité indisponible'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def recaptcha_admin_config(request):
    """
    GET  — Lecture de la configuration complète (super-admin).
    PATCH — Mise à jour partielle (super-admin).
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    config = RecaptchaConfig.get_config()

    if request.method == 'GET':
        serializer = RecaptchaConfigAdminSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # PATCH
    serializer = RecaptchaConfigAdminSerializer(config, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()

    # Re-lire depuis la DB et sérialiser fresh — garantit qu'aucune donnée
    # du payload d'entrée ne transite directement vers la réponse.
    config.refresh_from_db()
    logger.info(
        "RecaptchaConfig mis à jour par %s: is_enabled=%s min_score=%s",
        request.user.username,
        config.is_enabled,
        config.min_score,
    )
    try:
        log_activity(
            user=request.user,
            action='update',
            entity_type='recaptcha_config',
            entity_id=str(config.pk),
            entity_name='RecaptchaConfig',
            description=(
                f"{request.user.username} a modifié la configuration reCAPTCHA "
                f"(is_enabled={config.is_enabled}, min_score={config.min_score})"
            ),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT'),
        )
    except Exception as exc:
        logger.error("log_activity recaptcha_admin_config: %s", exc)

    return Response(
        RecaptchaConfigAdminSerializer(config).data,
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([KoraSensitiveThrottle])
def recaptcha_admin_test(request):
    """
    Teste un token reCAPTCHA depuis l'interface admin.
    Body: { "token": "<recaptcha_token>" }
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    token = request.data.get('token')
    if not token:
        return Response({'error': 'Le champ "token" est requis.'}, status=status.HTTP_400_BAD_REQUEST)

    expected_action = request.data.get('expected_action') or None

    try:
        remote_ip = request.META.get('REMOTE_ADDR')
        is_valid, data = recaptcha_service.verify_token(token, remote_ip, expected_action=expected_action)
        return Response({
            'success': is_valid,
            'details': data,
            'config': recaptcha_service.get_public_config(),
        }, status=status.HTTP_200_OK)
    except Exception as exc:
        logger.error("recaptcha_admin_test: %s", exc)
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
