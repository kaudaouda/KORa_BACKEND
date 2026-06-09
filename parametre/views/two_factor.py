from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging

from ..models import TwoFactorConfig
from ..serializers import TwoFactorConfigSerializer
from .utils import log_activity, get_client_ip

logger = logging.getLogger(__name__)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def two_factor_admin_config(request):
    """
    GET  — Lecture de la configuration 2FA (super-admin).
    PATCH — Mise à jour partielle (super-admin).
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    config = TwoFactorConfig.get_config()

    if request.method == 'GET':
        return Response(TwoFactorConfigSerializer(config).data, status=status.HTTP_200_OK)

    # PATCH
    serializer = TwoFactorConfigSerializer(config, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    config.refresh_from_db()

    logger.info(
        "TwoFactorConfig mis à jour par %s : is_enabled=%s otp_lifetime=%ss",
        request.user.username,
        config.is_enabled,
        config.otp_lifetime_seconds,
    )

    try:
        log_activity(
            user=request.user,
            action='update',
            entity_type='two_factor_config',
            entity_id=str(config.pk),
            entity_name='TwoFactorConfig',
            description=(
                f"{request.user.username} a modifié la configuration 2FA "
                f"(is_enabled={config.is_enabled}, "
                f"otp_lifetime={config.otp_lifetime_seconds}s, "
                f"max_attempts={config.max_attempts})"
            ),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT'),
        )
    except Exception as exc:
        logger.error("log_activity two_factor_admin_config: %s", exc)

    return Response(TwoFactorConfigSerializer(config).data, status=status.HTTP_200_OK)
