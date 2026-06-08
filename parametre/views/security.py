from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import json
import time
import hashlib
import logging
from datetime import timedelta
from django.http import StreamingHttpResponse
from django.db.models import Max, Subquery, OuterRef

from ..media_paths import validate_uploaded_file
from ..models import (
    Nature, Categorie, Source, ActionType, Statut,
    EtatMiseEnOeuvre, Appreciation, Media, Direction,
    SousDirection, Service, Processus, Preuve, ActivityLog, StatutActionCDR,
    NotificationSettings, DashboardNotificationSettings, EmailSettings, DysfonctionnementRecommandation, Frequence,
    FrequenceRisque, GraviteRisque, CriticiteRisque, Risque, Mois, TypeDocument,
    Role, UserProcessus, UserProcessusRole, Notification, NotificationPolicy,
    ReminderEmailLog, FailedLoginAttempt, LoginSecurityConfig, LoginBlock,
)
from ..utils.notification_policy import should_notify_pac
from ..serializers import (
    AppreciationSerializer, CategorieSerializer, DirectionSerializer,
    SousDirectionSerializer, ActionTypeSerializer, NotificationSettingsSerializer,
    DashboardNotificationSettingsSerializer, EmailSettingsSerializer, FrequenceSerializer,
    RisqueSerializer, StatutActionCDRSerializer,
    RoleSerializer, UserProcessusSerializer, UserProcessusRoleSerializer,
    UserSerializer, UserCreateSerializer, UserInviteSerializer,
    CriticiteRisqueSerializer, DysfonctionnementRecommandationSerializer,
    NatureSerializer, ProcessusSerializer, ServiceSerializer,
    MoisSerializer, FrequenceRisqueSerializer, GraviteRisqueSerializer,
    TypeDocumentSerializer,
)
from ..utils.email_security import EmailValidator, EmailContentSanitizer, EmailRateLimiter, SecureEmailLogger
from ..utils.email_config import load_email_settings_into_django
from permissions.permissions import (
    DashboardPreuveUpdatePermission,
    DashboardMediaUpdatePermission,
    DashboardMediaCreatePermission,
)

logger = logging.getLogger(__name__)

from .utils import (
    ServerSentEventRenderer, get_client_ip, _parse_user_agent,
    log_activity, get_model_list_data,
)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_security(request):
    """
    Tableau de bord sécurité : tentatives de connexion échouées, IPs suspectes.
    Réservé aux super-administrateurs.
    """
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django.utils import timezone
    from django.db.models import Count

    now   = timezone.now()
    t24h  = now - timedelta(hours=24)
    t7d   = now - timedelta(days=7)
    t30d  = now - timedelta(days=30)

    base   = FailedLoginAttempt.objects.all()
    today  = base.filter(created_at__gte=t24h)
    week   = base.filter(created_at__gte=t7d)
    month  = base.filter(created_at__gte=t30d)

    # ── Résumé ────────────────────────────────────────────────────────────────
    summary = {
        'failed_today':         today.count(),
        'failed_7d':            week.count(),
        'failed_30d':           month.count(),
        'unique_ips_today':     today.exclude(ip_address=None).values('ip_address').distinct().count(),
        'unique_targets_today': today.values('email_attempted').distinct().count(),
    }

    # ── 20 dernières tentatives ────────────────────────────────────────────────
    recent_qs = base.select_related('user').order_by('-created_at')[:20]
    recent = [
        {
            'id':             str(a.pk),
            'email_attempted': a.email_attempted,
            'ip_address':     a.ip_address,
            'reason':         a.reason,
            'reason_label':   a.get_reason_display(),
            'device_type':    a.device_type,
            'browser':        a.browser,
            'os_name':        a.os_name,
            'created_at':     a.created_at.isoformat(),
            'username':       a.user.username if a.user else None,
        }
        for a in recent_qs
    ]

    # ── Top 5 emails ciblés (30 derniers jours) ────────────────────────────────
    top_targeted = list(
        month.values('email_attempted')
             .annotate(count=Count('id'))
             .order_by('-count')[:5]
    )

    # ── Top 5 IPs suspectes (30 derniers jours) ────────────────────────────────
    top_ips = list(
        month.exclude(ip_address=None)
             .values('ip_address')
             .annotate(count=Count('id'))
             .order_by('-count')[:5]
    )

    # ── Emails ciblés plusieurs fois dans les 7 derniers jours ──────────────
    # Inclut les comptes existants ET les emails inconnus (user=None)
    suspicious_qs = (
        week.values('email_attempted')
            .annotate(
                attempts=Count('id'),
                user_id=Max('user__id'),
                username=Max('user__username'),
            )
            .filter(attempts__gte=3)
            .order_by('-attempts')[:10]
    )
    suspicious_accounts = [
        {
            'email_attempted': row['email_attempted'],
            'attempts':        row['attempts'],
            'user__id':        row['user_id'],
            'user__username':  row['username'],
        }
        for row in suspicious_qs
    ]

    return Response({
        'summary':             summary,
        'recent_attempts':     recent,
        'top_targeted':        top_targeted,
        'top_ips':             top_ips,
        'suspicious_accounts': suspicious_accounts,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_security_blocks(request):
    """Liste des blocages actifs."""
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django.utils import timezone
    now = timezone.now()
    blocks = LoginBlock.objects.filter(blocked_until__gt=now).order_by('-created_at')
    data = [
        {
            'id':             b.pk,
            'block_type':     b.block_type,
            'block_type_label': b.get_block_type_display(),
            'value':          b.value,
            'blocked_until':  b.blocked_until.isoformat(),
            'attempts_count': b.attempts_count,
            'is_manual':      b.is_manual,
            'created_at':     b.created_at.isoformat(),
        }
        for b in blocks
    ]
    config = LoginSecurityConfig.get_config()
    return Response({
        'blocks': data,
        'config': {
            'enabled':                    config.enabled,
            'ip_max_attempts':            config.ip_max_attempts,
            'email_max_attempts':         config.email_max_attempts,
            'window_minutes':             config.window_minutes,
            'ip_block_duration_minutes':  config.ip_block_duration_minutes,
            'email_block_duration_minutes': config.email_block_duration_minutes,
        },
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def admin_security_unblock(request, block_id):
    """Débloquer manuellement un blocage."""
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        block = LoginBlock.objects.get(pk=block_id)
        value = block.value
        block.delete()
        logger.info("[SECURITY] Déblocage manuel de '%s' par %s", value, request.user.username)
        return Response({'success': True})
    except LoginBlock.DoesNotExist:
        return Response({'error': 'Blocage introuvable.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_security_config(request):
    """Lire ou modifier la configuration de sécurité login."""
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    config = LoginSecurityConfig.get_config()

    if request.method == 'GET':
        return Response(_serialize_config(config))

    # PATCH
    allowed = {
        'enabled', 'ip_max_attempts', 'email_max_attempts',
        'window_minutes', 'ip_block_duration_minutes',
        'email_block_duration_minutes', 'whitelist_ips',
    }
    errors = {}
    for field in allowed & set(request.data.keys()):
        value = request.data[field]
        if field == 'enabled':
            if not isinstance(value, bool):
                errors[field] = 'Doit être un booléen.'
                continue
        elif field == 'whitelist_ips':
            if not isinstance(value, str):
                errors[field] = 'Doit être une chaîne.'
                continue
        else:
            try:
                value = int(value)
                if value < 1:
                    raise ValueError
            except (ValueError, TypeError):
                errors[field] = 'Doit être un entier positif.'
                continue
        setattr(config, field, value)

    if errors:
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    config.save()
    logger.info("[SECURITY] Config mise à jour par %s", request.user.username)
    return Response(_serialize_config(config))


def _serialize_config(config):
    return {
        'enabled':                      config.enabled,
        'ip_max_attempts':              config.ip_max_attempts,
        'email_max_attempts':           config.email_max_attempts,
        'window_minutes':               config.window_minutes,
        'ip_block_duration_minutes':    config.ip_block_duration_minutes,
        'email_block_duration_minutes': config.email_block_duration_minutes,
        'whitelist_ips':                config.whitelist_ips,
    }


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_throttle_config(request):
    """Lire ou modifier la configuration du throttling DRF."""
    from parametre.permissions import can_manage_users
    from parametre.models import ThrottleConfig
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    config = ThrottleConfig.get_config()

    if request.method == 'GET':
        return Response(_serialize_throttle_config(config))

    # PATCH — valide le format N/period avant de sauvegarder
    import re
    RATE_RE = re.compile(r'^\d+/(second|sec|minute|min|hour|hr|day)$')
    RATE_NORMALIZE = {'sec': 'second', 'min': 'minute', 'hr': 'hour'}
    allowed = {'enabled', 'anon_rate', 'user_rate', 'sensitive_rate'}
    errors = {}

    for field in allowed & set(request.data.keys()):
        value = request.data[field]
        if field == 'enabled':
            if not isinstance(value, bool):
                errors[field] = 'Doit être un booléen.'
                continue
        else:
            if not isinstance(value, str) or not RATE_RE.match(value.strip()):
                errors[field] = 'Format invalide. Exemples : 100/minute, 1000/hour'
                continue
            count, period = value.strip().split('/')
            value = f'{count}/{RATE_NORMALIZE.get(period, period)}'
        setattr(config, field, value)

    if errors:
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    config.save()  # invalide le cache throttle_config
    logger.info("[THROTTLE] Config mise à jour par %s", request.user.username)
    return Response(_serialize_throttle_config(config))


_RATE_NORMALIZE = {'sec': 'second', 'min': 'minute', 'hr': 'hour'}


def _normalize_rate(rate):
    if not rate or '/' not in rate:
        return rate
    count, period = rate.split('/', 1)
    return f'{count}/{_RATE_NORMALIZE.get(period, period)}'


def _serialize_throttle_config(config):
    return {
        'enabled':        config.enabled,
        'anon_rate':      _normalize_rate(config.anon_rate),
        'user_rate':      _normalize_rate(config.user_rate),
        'sensitive_rate': _normalize_rate(config.sensitive_rate),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER (APScheduler)
# ─────────────────────────────────────────────────────────────────────────────

