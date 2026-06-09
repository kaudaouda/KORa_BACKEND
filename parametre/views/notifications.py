from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
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



def resolve_notification_settings(obj):
    """
    Résout les paramètres de notification pour un objet donné.
    Retourne le délai de réalisation et la fréquence des rappels.
    
    Args:
        obj: L'objet pour lequel résoudre les paramètres (PAC, Traitement, Suivi, etc.)
    
    Returns:
        dict: Paramètres de notification globaux
    """
    # Récupérer les paramètres globaux par défaut
    global_settings = NotificationSettings.get_solo()
    
    # Retourner le délai de réalisation et la fréquence des rappels
    return {
        'traitement_delai_notice_days': global_settings.traitement_delai_notice_days,
        'traitement_reminder_frequency_days': global_settings.traitement_reminder_frequency_days,
    }


# ==================== NOTIFICATION SETTINGS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_settings_get(request):
    """
    Récupère les paramètres globaux de notification (singleton)
    """
    try:
        settings_instance = NotificationSettings.get_solo()
        serializer = NotificationSettingsSerializer(settings_instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des paramètres de notification: %s", str(e))
        return Response({'error': 'Impossible de récupérer les paramètres'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def notification_settings_update(request):
    """
    Met à jour les paramètres globaux de notification (admin recommandé)
    """
    try:
        # Optionnel: restreindre aux admins
        # if not request.user.is_staff:
        #     return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

        settings_instance = NotificationSettings.get_solo()
        serializer = NotificationSettingsSerializer(settings_instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour des paramètres de notification: %s", str(e))
        return Response({'error': 'Impossible de mettre à jour les paramètres'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_settings_effective(request):
    """
    Récupère les paramètres de notification effectifs pour un objet donné.
    Query params:
    - content_type: Le type de contenu (ex: 'pac.pac', 'pac.traitement', 'pac.suivi')
    - object_id: L'ID de l'objet
    """
    try:
        content_type_str = request.GET.get('content_type')
        object_id = request.GET.get('object_id')
        
        if not content_type_str or not object_id:
            return Response({
                'error': 'content_type et object_id sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Récupérer l'objet
        from django.contrib.contenttypes.models import ContentType
        try:
            content_type = ContentType.objects.get(model=content_type_str.split('.')[-1])
            obj = content_type.get_object_for_this_type(pk=object_id)
        except (ContentType.DoesNotExist, Exception) as e:
            return Response({
                'error': f'Objet non trouvé: {str(e)}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Résoudre les paramètres
        resolved_settings = resolve_notification_settings(obj)
        
        return Response({
            'object': {
                'type': content_type_str,
                'id': object_id,
                'name': str(obj)
            },
            'settings': resolved_settings
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la résolution des paramètres effectifs: %s", str(e))
        return Response({'error': 'Impossible de résoudre les paramètres'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== DASHBOARD NOTIFICATION SETTINGS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_notification_settings_get(request):
    """
    Récupère les paramètres de notification pour les tableaux de bord
    """
    try:
        settings_instance = DashboardNotificationSettings.get_solo()
        serializer = DashboardNotificationSettingsSerializer(settings_instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des paramètres dashboard: %s", str(e))
        return Response({'error': 'Impossible de récupérer les paramètres'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def dashboard_notification_settings_update(request):
    """
    Met à jour les paramètres de notification pour les tableaux de bord
    """
    try:
        settings_instance = DashboardNotificationSettings.get_solo()
        serializer = DashboardNotificationSettingsSerializer(
            settings_instance, 
            data=request.data, 
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour des paramètres dashboard: %s", str(e))
        return Response({'error': 'Impossible de mettre à jour les paramètres'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upcoming_notifications(request):
    """
    Récupère les échéances à venir pour l'utilisateur connecté - Délai de réalisation uniquement
    """
    try:
        from parametre.services.pac_notification_service import get_pac_notifications
        data = get_pac_notifications(request.user)
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des échéances: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({'error': 'Impossible de récupérer les échéances'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_list(request):
    """
    Liste générique des notifications pour l'utilisateur connecté.
    Permet d'exploiter la table parametre.Notification pour toutes les apps.
    Filtres possibles (query params) :
    - is_read=true|false
    - include_dismissed=true pour inclure les notifications masquées
    - source_app=pac|dashboard|...
    - notification_type=traitement|suivi|...
    - limit, offset pour la pagination simple
    """
    try:
        qs = Notification.objects.filter(user=request.user)

        # Filtre masquées
        include_dismissed = request.query_params.get('include_dismissed')
        if not (include_dismissed and include_dismissed.lower() in ('1', 'true', 'yes')):
            qs = qs.filter(dismissed_at__isnull=True)

        # Filtre lu / non lu
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            is_read = is_read.lower()
            if is_read in ('1', 'true', 'yes'):
                qs = qs.filter(read_at__isnull=False)
            elif is_read in ('0', 'false', 'no'):
                qs = qs.filter(read_at__isnull=True)

        # Filtre source_app
        source_app = request.query_params.get('source_app')
        if source_app:
            qs = qs.filter(source_app=source_app)

        # Filtre type métier
        notif_type = request.query_params.get('notification_type')
        if notif_type:
            qs = qs.filter(notification_type=notif_type)

        qs = qs.order_by('-created_at')

        # Pagination simple
        try:
            limit = int(request.query_params.get('limit', '100'))
        except ValueError:
            limit = 100
        try:
            offset = int(request.query_params.get('offset', '0'))
        except ValueError:
            offset = 0

        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        total = qs.count()
        notifications_qs = qs[offset:offset + limit]

        notifications_data = []
        for n in notifications_qs:
            notifications_data.append({
                'notification_uuid': str(n.uuid),
                'title': n.title,
                'message': n.message,
                'source_app': n.source_app,
                'notification_type': n.notification_type,
                'action_url': n.action_url,
                'priority': n.priority,
                'due_date': n.due_date.isoformat() if n.due_date else None,
                'read_at': n.read_at.isoformat() if n.read_at else None,
                'dismissed_at': n.dismissed_at.isoformat() if n.dismissed_at else None,
                'sent_by_email_at': n.sent_by_email_at.isoformat() if n.sent_by_email_at else None,
                'shown_in_ui_at': n.shown_in_ui_at.isoformat() if n.shown_in_ui_at else None,
                'content_type': n.content_type.model if n.content_type else None,
                'object_id': str(n.object_id) if n.object_id is not None else None,
                'created_at': n.created_at.isoformat() if n.created_at else None,
                'updated_at': n.updated_at.isoformat() if n.updated_at else None,
                'is_read': bool(n.read_at),
            })

        return Response({
            'notifications': notifications_data,
            'total': total,
            'limit': limit,
            'offset': offset,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Erreur lors de la récupération de la liste des notifications: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        return Response({'error': 'Impossible de récupérer les notifications'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH', 'POST'])
@permission_classes([IsAuthenticated])
def notification_mark_read(request, uuid):
    """
    Marquer une notification comme lue (read_at) pour l'utilisateur connecté.
    """
    try:
        notif = Notification.objects.filter(uuid=uuid, user=request.user).first()
        if not notif:
            return Response(
                {'error': 'Notification introuvable ou accès refusé'},
                status=status.HTTP_404_NOT_FOUND
            )
        if not notif.read_at:
            notif.read_at = timezone.now()
            notif.save(update_fields=['read_at', 'updated_at'])
        return Response({
            'success': True,
            'notification_uuid': str(notif.uuid),
            'read_at': notif.read_at.isoformat(),
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors du marquage lu de la notification %s: %s", uuid, e)
        return Response(
            {'error': 'Impossible de marquer la notification comme lue'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

