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



class ServerSentEventRenderer(BaseRenderer):
    """Renderer passthrough pour les flux SSE (text/event-stream).
    Permet à DRF d'accepter les requêtes EventSource sans négociation de contenu.
    Le rendu réel est géré par StreamingHttpResponse, pas par ce renderer.
    """
    media_type = 'text/event-stream'
    format = 'sse'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


def get_client_ip(request):
    """
    Récupère l'adresse IP réelle du client en tenant compte des proxies de confiance.

    Utilise TRUSTED_PROXY_COUNT (settings) pour déterminer combien de proxies sont
    devant Django. Avec N proxies de confiance, l'IP client est à l'index len(XFF)-N
    dans le header X-Forwarded-For.

    Sans proxy (dev) : retourne REMOTE_ADDR directement, XFF ignoré.
    Avec 1 proxy (nginx) : XFF="client, proxy" → idx=0 → "client".

    Ce comportement est identique à IPBlockMiddleware._get_ip() pour garantir
    que les mêmes IPs sont bloquées par le middleware et loguées dans les vues.
    """
    trusted_proxy_count = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    if trusted_proxy_count > 0:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ips = [ip.strip() for ip in xff.split(',') if ip.strip()]
        if ips:
            idx = max(0, len(ips) - trusted_proxy_count)
            return ips[idx]
    return request.META.get('REMOTE_ADDR')


def _parse_user_agent(ua_string):
    """Parse un user-agent string et retourne (device_type, browser, os_name)."""
    if not ua_string:
        return None, None, None
    try:
        import user_agents
        ua = user_agents.parse(ua_string)
        if ua.is_mobile:
            device_type = 'mobile'
        elif ua.is_tablet:
            device_type = 'tablet'
        else:
            device_type = 'desktop'
        browser = ua.browser.family or None
        os_name = ua.os.family or None
        return device_type, browser, os_name
    except Exception:
        return None, None, None


def log_activity(user, action, entity_type, entity_id=None, entity_name=None, description=None, ip_address=None, user_agent=None):
    """
    Enregistre une activité utilisateur
    """
    try:
        device_type, browser, os_name = _parse_user_agent(user_agent)
        activity_log = ActivityLog.objects.create(
            user=user,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            description=description or f"{user.username} a {action} {entity_type}",
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            browser=browser,
            os_name=os_name,
        )
        logger.info("Activité enregistrée: %s", activity_log)
        return activity_log
    except Exception as e:
        logger.error("Erreur lors de l'enregistrement de l'activité: %s", e)
        return None


def get_model_list_data(model_class, order_by='nom', include_inactive=False):
    """
    Fonction utilitaire pour récupérer les données d'un modèle avec gestion des états
    
    Args:
        model_class: Classe du modèle Django
        order_by: Champ pour trier les résultats
        include_inactive: Si True, inclut les éléments désactivés
    
    Returns:
        list: Liste des données formatées
    """
    try:
        queryset = model_class.objects.all()
        
        # Filtrer par is_active si le modèle a ce champ
        if hasattr(model_class, 'is_active') and not include_inactive:
            queryset = queryset.filter(is_active=True)
        
        queryset = queryset.order_by(order_by)
        
        data = []
        for obj in queryset:
            item_data = {
                'uuid': str(obj.uuid),
                'nom': obj.nom,
                'description': obj.description,
                'created_at': obj.created_at.isoformat(),
                'updated_at': obj.updated_at.isoformat()
            }
            
            # Ajouter is_active si le modèle a ce champ
            if hasattr(obj, 'is_active'):
                item_data['is_active'] = obj.is_active
            
            # Ajouter des champs spécifiques selon le modèle
            if hasattr(obj, 'direction'):
                item_data['direction'] = {
                    'uuid': str(obj.direction.uuid),
                    'nom': obj.direction.nom
                }
            
            if hasattr(obj, 'sous_direction'):
                item_data['sous_direction'] = {
                    'uuid': str(obj.sous_direction.uuid),
                    'nom': obj.sous_direction.nom,
                    'direction': {
                        'uuid': str(obj.sous_direction.direction.uuid),
                        'nom': obj.sous_direction.direction.nom
                    }
                }
            
            if hasattr(obj, 'cree_par'):
                item_data['cree_par'] = {
                    'id': obj.cree_par.id,
                    'username': obj.cree_par.username,
                    'first_name': obj.cree_par.first_name,
                    'last_name': obj.cree_par.last_name
                }
            
            if hasattr(obj, 'numero_processus'):
                item_data['numero_processus'] = obj.numero_processus
            
            data.append(item_data)
        
        return data
    except Exception as e:
        logger.error("Erreur lors de la récupération des données %s: %s", model_class.__name__, e)
        raise e


