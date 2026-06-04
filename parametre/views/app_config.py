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



def application_config_list(request):
    """Liste toutes les configurations d'applications (super admin uniquement)"""
    if not (request.user.is_staff and request.user.is_superuser):
        return JsonResponse({'error': 'Accès non autorisé'}, status=403)
    try:
        from parametre.models import ApplicationConfig
        configs = ApplicationConfig.objects.all().order_by('app_name')
        data = [
            {
                'app_name': c.app_name,
                'label': c.get_app_name_display(),
                'is_enabled': c.is_enabled,
                'maintenance_message': c.maintenance_message or '',
                'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                'updated_by': c.updated_by.username if c.updated_by else None,
            }
            for c in configs
        ]
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.error("Erreur application_config_list: %s", {e})
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def application_config_toggle(request, app_name):
    """Active ou désactive une application (super admin uniquement)"""
    if not (request.user.is_staff and request.user.is_superuser):
        return JsonResponse({'error': 'Accès non autorisé'}, status=403)
    try:
        from parametre.models import ApplicationConfig
        config = ApplicationConfig.objects.get(app_name=app_name)
        config.is_enabled = not config.is_enabled
        config.updated_by = request.user
        config.save()
        return JsonResponse({
            'app_name': config.app_name,
            'label': config.get_app_name_display(),
            'is_enabled': config.is_enabled,
        })
    except ApplicationConfig.DoesNotExist:
        return JsonResponse({'error': 'Application non trouvée'}, status=404)
    except Exception as e:
        logger.error("Erreur application_config_toggle: %s", {e})
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@renderer_classes([ServerSentEventRenderer])
def app_status_stream(request):
    """SSE : pousse les changements de statut de maintenance en temps réel.

    Security by Design :
    - Authentification obligatoire (cookie JWT via DRF)
    - Données filtrées selon le rôle (superadmin bypass)
    - Aucune donnée sensible dans le stream
    - Heartbeat toutes les 15 s pour détecter les déconnexions
    - Détection de changements via updated_at (requête légère)
    - GeneratorExit capturé pour libérer proprement la connexion
    """
    is_superadmin = request.user.is_staff and request.user.is_superuser
    username = request.user.username

    def _snapshot():
        """Retourne (données_effectives, hash_de_changement)."""
        from parametre.models import ApplicationConfig
        configs = list(
            ApplicationConfig.objects.all()
            .values('app_name', 'is_enabled', 'maintenance_message', 'maintenance_end')
            .order_by('app_name')
        )
        # Hash basé uniquement sur les champs métier (is_enabled suffit)
        change_hash = hashlib.md5(
            str([(c['app_name'], c['is_enabled']) for c in configs]).encode()
        ).hexdigest()

        data = {}
        for c in configs:
            data[c['app_name']] = {
                'is_enabled': True if is_superadmin else c['is_enabled'],
                'maintenance_message': c['maintenance_message'] or '',
                'maintenance_end': (
                    c['maintenance_end'].isoformat() if c['maintenance_end'] else None
                ),
            }
        return data, change_hash

    def _event(event_name, payload):
        return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"

    def stream():
        last_hash = None
        heartbeat_ticks = 0
        POLL_INTERVAL = 3       # secondes entre chaque vérification DB
        HEARTBEAT_EVERY = 5     # ticks → heartbeat toutes les 15 s

        try:
            # État initial envoyé immédiatement à la connexion
            data, last_hash = _snapshot()
            yield _event('status', data)
        except Exception as e:
            logger.error("[SSE] Erreur initialisation (%s): %s", {username}, {e})
            return

        while True:
            try:
                time.sleep(POLL_INTERVAL)

                data, current_hash = _snapshot()

                if current_hash != last_hash:
                    yield _event('status', data)
                    last_hash = current_hash
                    heartbeat_ticks = 0
                else:
                    heartbeat_ticks += 1
                    if heartbeat_ticks >= HEARTBEAT_EVERY:
                        yield ": heartbeat\n\n"
                        heartbeat_ticks = 0

            except GeneratorExit:
                logger.info("[SSE] Client déconnecté : %s", {username})
                break
            except Exception as e:
                logger.error("[SSE] Erreur stream (%s): %s", {username}, {e})
                break

    response = StreamingHttpResponse(
        streaming_content=stream(),
        content_type='text/event-stream; charset=utf-8',
    )
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['X-Accel-Buffering'] = 'no'   # désactive le buffering Nginx

    # Headers CORS explicites : StreamingHttpResponse peut contourner le middleware
    # corsheaders dans certaines configurations WSGI dev. On les pose directement.
    from django.conf import settings as _settings
    origin = request.META.get('HTTP_ORIGIN', '')
    allowed = getattr(_settings, 'CORS_ALLOWED_ORIGINS', [])
    if origin in allowed:
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Vary'] = 'Origin'

    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def app_status(request):
    """Statut effectif de toutes les apps pour l'utilisateur courant.
    Superadmins voient toutes les apps comme actives (bypass maintenance)."""
    try:
        from parametre.models import ApplicationConfig
        is_superadmin = request.user.is_staff and request.user.is_superuser
        configs = ApplicationConfig.objects.all().values(
            'app_name', 'is_enabled', 'maintenance_message', 'maintenance_end'
        )
        data = {}
        for c in configs:
            data[c['app_name']] = {
                'is_enabled': True if is_superadmin else c['is_enabled'],
                'maintenance_message': c['maintenance_message'] or '',
                'maintenance_end': c['maintenance_end'].isoformat() if c['maintenance_end'] else None,
            }
        return JsonResponse(data)
    except Exception as e:
        logger.error("Erreur app_status: %s", {e})
        return JsonResponse({}, status=200)

