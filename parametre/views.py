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

from .models import (
    Nature, Categorie, Source, ActionType, Statut,
    EtatMiseEnOeuvre, Appreciation, Media, Direction,
    SousDirection, Service, Processus, Preuve, ActivityLog, StatutActionCDR,
    NotificationSettings, DashboardNotificationSettings, EmailSettings, DysfonctionnementRecommandation, Frequence,
    FrequenceRisque, GraviteRisque, CriticiteRisque, Risque, Mois, TypeDocument,
    Role, UserProcessus, UserProcessusRole, Notification, NotificationPolicy,
    ReminderEmailLog, FailedLoginAttempt, LoginSecurityConfig, LoginBlock,
)
from .utils.notification_policy import should_notify_pac
from .serializers import (
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
from .utils.email_security import EmailValidator, EmailContentSanitizer, EmailRateLimiter, SecureEmailLogger
from .utils.email_config import load_email_settings_into_django

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
    Récupère l'adresse IP du client
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


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
        logger.info(f"Activité enregistrée: {activity_log}")
        return activity_log
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de l'activité: {e}")
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
        logger.error(f"Erreur lors de la récupération des données {model_class.__name__}: {e}")
        raise e


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
        logger.error(f"Erreur lors de la récupération des paramètres de notification: {str(e)}")
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
        logger.error(f"Erreur lors de la mise à jour des paramètres de notification: {str(e)}")
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
        logger.error(f"Erreur lors de la résolution des paramètres effectifs: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération des paramètres dashboard: {str(e)}")
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
        logger.error(f"Erreur lors de la mise à jour des paramètres dashboard: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour les paramètres'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def log_pac_creation(user, pac, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un PAC
    """
    # Le modèle Pac n'a pas de champs numero_pac ni libelle
    # Ces informations sont dans les relations
    processus_nom = pac.processus.nom if pac.processus else "Processus inconnu"
    annee_libelle = f"{pac.annee.annee}" if pac.annee else "Année non définie"
    nom_version = pac.nom_version if hasattr(pac, 'nom_version') else f"Amendement {pac.num_amendement}"

    return log_activity(
        user=user,
        action='create',
        entity_type='pac',
        entity_id=str(pac.uuid),
        entity_name=f"PAC {pac.uuid}",
        description=f"Création du PAC pour {processus_nom} - {annee_libelle} ({nom_version})",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_pac_update(user, pac, ip_address=None, user_agent=None):
    """
    Log spécifique pour la modification d'un PAC
    """
    # Le modèle Pac n'a pas de champ numero_pac
    processus_nom = pac.processus.nom if pac.processus else "Processus inconnu"
    annee_libelle = f"{pac.annee.annee}" if pac.annee else "Année non définie"

    return log_activity(
        user=user,
        action='update',
        entity_type='pac',
        entity_id=str(pac.uuid),
        entity_name=f"PAC {pac.uuid}",
        description=f"Modification du PAC pour {processus_nom} - {annee_libelle}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_traitement_creation(user, traitement, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un traitement
    """
    # numero_pac est sur DetailsPac, pas sur Pac
    numero_pac = 'N/A'
    if traitement.details_pac and traitement.details_pac.numero_pac:
        numero_pac = traitement.details_pac.numero_pac
    
    return log_activity(
        user=user,
        action='create',
        entity_type='traitement',
        entity_id=str(traitement.uuid),
        entity_name=f"Traitement pour PAC {numero_pac}",
        description=f"Création d'un traitement: {traitement.action[:50]}...",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_suivi_creation(user, suivi, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un suivi
    """
    # numero_pac est sur DetailsPac, pas sur Pac
    numero_pac = 'N/A'
    if suivi.traitement and suivi.traitement.details_pac and suivi.traitement.details_pac.numero_pac:
        numero_pac = suivi.traitement.details_pac.numero_pac
    
    return log_activity(
        user=user,
        action='create',
        entity_type='suivi',
        entity_id=str(suivi.uuid),
        entity_name=f"Suivi pour PAC {numero_pac}",
        description=f"Création d'un suivi: {suivi.etat_mise_en_oeuvre.nom}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_user_login(user, ip_address=None, user_agent=None):
    """
    Log spécifique pour la connexion utilisateur
    """
    return log_activity(
        user=user,
        action='login',
        entity_type='user',
        entity_id=str(user.id),
        entity_name=user.username,
        description=f"Connexion de {user.username}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_user_logout(user, ip_address=None, user_agent=None):
    """
    Log spécifique pour la déconnexion utilisateur
    """
    return log_activity(
        user=user,
        action='logout',
        entity_type='user',
        entity_id=str(user.id),
        entity_name=user.username,
        description=f"Déconnexion de {user.username}",
        ip_address=ip_address,
        user_agent=user_agent
    )


# ============================================
# LOGS POUR ACTIVITÉS PÉRIODIQUES
# ============================================

def log_activite_periodique_creation(user, ap, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'une Activité Périodique
    """
    processus_nom = ap.processus.nom if hasattr(ap, 'processus') and ap.processus else 'N/A'
    annee = ap.annee_valeur if hasattr(ap, 'annee_valeur') else (ap.annee.libelle if hasattr(ap, 'annee') and ap.annee else 'N/A')
    nom_version = ap.nom_version if hasattr(ap, 'nom_version') else f"Amendement {ap.num_amendement}"

    return log_activity(
        user=user,
        action='create',
        entity_type='activite_periodique',
        entity_id=str(ap.uuid),
        entity_name=f"{processus_nom} - {annee}",
        description=f"Création de l'Activité Périodique pour {processus_nom} - {annee} ({nom_version})",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_activite_periodique_update(user, ap, ip_address=None, user_agent=None):
    """
    Log spécifique pour la modification d'une Activité Périodique
    """
    processus_nom = ap.processus.nom if hasattr(ap, 'processus') and ap.processus else 'N/A'
    annee = ap.annee_valeur if hasattr(ap, 'annee_valeur') else (ap.annee.libelle if hasattr(ap, 'annee') and ap.annee else 'N/A')

    return log_activity(
        user=user,
        action='update',
        entity_type='activite_periodique',
        entity_id=str(ap.uuid),
        entity_name=f"{processus_nom} - {annee}",
        description=f"Modification de l'Activité Périodique pour {processus_nom} - {annee}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_activite_periodique_validation(user, ap, ip_address=None, user_agent=None):
    """
    Log spécifique pour la validation d'une Activité Périodique
    """
    processus_nom = ap.processus.nom if hasattr(ap, 'processus') and ap.processus else 'N/A'
    annee = ap.annee_valeur if hasattr(ap, 'annee_valeur') else (ap.annee.libelle if hasattr(ap, 'annee') and ap.annee else 'N/A')

    return log_activity(
        user=user,
        action='update',
        entity_type='activite_periodique',
        entity_id=str(ap.uuid),
        entity_name=f"{processus_nom} - {annee}",
        description=f"Validation de l'Activité Périodique pour {processus_nom} - {annee}",
        ip_address=ip_address,
        user_agent=user_agent
    )


# ============================================
# LOGS POUR CARTOGRAPHIE DE RISQUE (CDR)
# ============================================

def log_cdr_creation(user, cdr, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'une Cartographie de Risque
    """
    processus_nom = cdr.processus.nom if hasattr(cdr, 'processus') and cdr.processus else 'N/A'
    annee = cdr.annee if hasattr(cdr, 'annee') else 'N/A'
    nom_version = cdr.nom_version if hasattr(cdr, 'nom_version') else f"Amendement {cdr.num_amendement}"

    return log_activity(
        user=user,
        action='create',
        entity_type='cdr',
        entity_id=str(cdr.uuid),
        entity_name=f"{processus_nom} - {annee}",
        description=f"Création de la Cartographie de Risque pour {processus_nom} - {annee} ({nom_version})",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_cdr_update(user, cdr, ip_address=None, user_agent=None):
    """
    Log spécifique pour la modification d'une Cartographie de Risque
    """
    processus_nom = cdr.processus.nom if hasattr(cdr, 'processus') and cdr.processus else 'N/A'
    annee = cdr.annee if hasattr(cdr, 'annee') else 'N/A'

    return log_activity(
        user=user,
        action='update',
        entity_type='cdr',
        entity_id=str(cdr.uuid),
        entity_name=f"{processus_nom} - {annee}",
        description=f"Modification de la Cartographie de Risque pour {processus_nom} - {annee}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_cdr_validation(user, cdr, ip_address=None, user_agent=None):
    """
    Log spécifique pour la validation d'une Cartographie de Risque
    """
    processus_nom = cdr.processus.nom if hasattr(cdr, 'processus') and cdr.processus else 'N/A'
    annee = cdr.annee if hasattr(cdr, 'annee') else 'N/A'

    return log_activity(
        user=user,
        action='update',
        entity_type='cdr',
        entity_id=str(cdr.uuid),
        entity_name=f"{processus_nom} - {annee}",
        description=f"Validation de la Cartographie de Risque pour {processus_nom} - {annee}",
        ip_address=ip_address,
        user_agent=user_agent
    )


# ============================================
# LOGS POUR DOCUMENTATION
# ============================================

def log_document_creation(user, document, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un Document
    """
    titre = document.titre if hasattr(document, 'titre') else 'N/A'
    type_doc = document.type_document.nom if hasattr(document, 'type_document') and document.type_document else 'N/A'

    return log_activity(
        user=user,
        action='create',
        entity_type='document',
        entity_id=str(document.uuid),
        entity_name=titre[:100],
        description=f"Création du document '{titre}' ({type_doc})",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_document_update(user, document, ip_address=None, user_agent=None):
    """
    Log spécifique pour la modification d'un Document
    """
    titre = document.titre if hasattr(document, 'titre') else 'N/A'

    return log_activity(
        user=user,
        action='update',
        entity_type='document',
        entity_id=str(document.uuid),
        entity_name=titre[:100],
        description=f"Modification du document '{titre}'",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_document_edition_creation(user, edition, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'une Édition de document
    """
    document_titre = edition.document.titre if hasattr(edition, 'document') and edition.document else 'N/A'
    numero = edition.numero if hasattr(edition, 'numero') else 'N/A'

    return log_activity(
        user=user,
        action='create',
        entity_type='document_edition',
        entity_id=str(edition.uuid),
        entity_name=f"{document_titre} - Édition {numero}",
        description=f"Création de l'édition {numero} du document '{document_titre}'",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_document_amendement_creation(user, amendement, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un Amendement de document
    """
    document_titre = amendement.document.titre if hasattr(amendement, 'document') and amendement.document else 'N/A'
    numero = amendement.numero if hasattr(amendement, 'numero') else 'N/A'

    return log_activity(
        user=user,
        action='create',
        entity_type='document_amendement',
        entity_id=str(amendement.uuid),
        entity_name=f"{document_titre} - Amendement {numero}",
        description=f"Création de l'amendement {numero} du document '{document_titre}'",
        ip_address=ip_address,
        user_agent=user_agent
    )


# ============================================
# LOGS POUR TABLEAU DE BORD
# ============================================

def log_tableau_bord_creation(user, tableau, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un Tableau de Bord
    """
    nom = tableau.nom if hasattr(tableau, 'nom') else 'N/A'
    annee = tableau.annee.libelle if hasattr(tableau, 'annee') and tableau.annee else 'N/A'

    return log_activity(
        user=user,
        action='create',
        entity_type='tableau_bord',
        entity_id=str(tableau.uuid),
        entity_name=f"{nom} - {annee}",
        description=f"Création du Tableau de Bord '{nom}' pour l'année {annee}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_tableau_bord_update(user, tableau, ip_address=None, user_agent=None):
    """
    Log spécifique pour la modification d'un Tableau de Bord
    """
    nom = tableau.nom if hasattr(tableau, 'nom') else 'N/A'

    return log_activity(
        user=user,
        action='update',
        entity_type='tableau_bord',
        entity_id=str(tableau.uuid),
        entity_name=nom,
        description=f"Modification du Tableau de Bord '{nom}'",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_objectif_creation(user, objectif, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un Objectif
    """
    nom = objectif.nom if hasattr(objectif, 'nom') else 'N/A'
    numero = objectif.numero if hasattr(objectif, 'numero') else 'N/A'

    return log_activity(
        user=user,
        action='create',
        entity_type='objectif',
        entity_id=str(objectif.uuid),
        entity_name=f"Objectif {numero}: {nom[:50]}",
        description=f"Création de l'objectif '{nom}'",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_indicateur_creation(user, indicateur, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un Indicateur
    """
    nom = indicateur.nom if hasattr(indicateur, 'nom') else 'N/A'

    return log_activity(
        user=user,
        action='create',
        entity_type='indicateur',
        entity_id=str(indicateur.uuid),
        entity_name=nom[:100],
        description=f"Création de l'indicateur '{nom}'",
        ip_address=ip_address,
        user_agent=user_agent
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_activities(request):
    """
    API pour récupérer les activités récentes
    """
    try:
        limit = int(request.GET.get('limit', 10))
        user_specific = request.GET.get('user_only', 'false').lower() == 'true'
        
        # Récupération des activités directement (exclure login/logout)
        queryset = ActivityLog.objects.select_related('user').exclude(action__in=['login', 'logout'])

        if user_specific:
            queryset = queryset.filter(user=request.user)

        activities = queryset.order_by('-created_at')[:limit]
        
        # Formatage des données
        data = []
        for activity in activities:
            data.append({
                'uuid': str(activity.uuid),
                'user': {
                    'username': activity.user.username,
                    'first_name': activity.user.first_name,
                    'last_name': activity.user.last_name,
                    'initials': f"{activity.user.first_name[0] if activity.user.first_name else ''}{activity.user.last_name[0] if activity.user.last_name else ''}".upper()
                },
                'action': activity.action,
                'action_display': activity.get_action_display(),
                'entity_type': activity.entity_type,
                'entity_name': activity.entity_name,
                'description': activity.description,
                'time_ago': activity.time_ago,
                'action_icon': activity.action_icon,
                'status_color': activity.status_color,
                'created_at': activity.created_at.isoformat()
            })
        
        return Response({
            'success': True,
            'data': data,
            'count': len(data)
        }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des activités: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des activités',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_activities(request):
    """
    API pour récupérer les activités d'un utilisateur spécifique
    """
    try:
        limit = int(request.GET.get('limit', 20))

        # Récupération des activités de l'utilisateur (exclure login/logout)
        activities = ActivityLog.objects.filter(user=request.user).exclude(action__in=['login', 'logout']).select_related('user').order_by('-created_at')[:limit]
        
        # Formatage des données
        data = []
        for activity in activities:
            data.append({
                'uuid': str(activity.uuid),
                'user': {
                    'username': activity.user.username,
                    'first_name': activity.user.first_name,
                    'last_name': activity.user.last_name,
                    'initials': f"{activity.user.first_name[0] if activity.user.first_name else ''}{activity.user.last_name[0] if activity.user.last_name else ''}".upper()
                },
                'action': activity.action,
                'action_display': activity.get_action_display(),
                'entity_type': activity.entity_type,
                'entity_name': activity.entity_name,
                'description': activity.description,
                'time_ago': activity.time_ago,
                'action_icon': activity.action_icon,
                'status_color': activity.status_color,
                'created_at': activity.created_at.isoformat()
            })
        
        return Response({
            'success': True,
            'data': data,
            'count': len(data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des activités utilisateur: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des activités',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_notifications_list(request):
    """
    API admin : toutes les notifications (tous utilisateurs).
    Security by Design : is_staff ET is_superuser requis.
    Filtres : source_app, is_read, limit, offset.
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'success': False, 'message': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

    try:
        qs = Notification.objects.select_related('user', 'content_type').order_by('-created_at')

        source_app = request.GET.get('source_app')
        if source_app:
            qs = qs.filter(source_app=source_app)

        is_read = request.GET.get('is_read')
        if is_read == 'true':
            qs = qs.filter(read_at__isnull=False)
        elif is_read == 'false':
            qs = qs.filter(read_at__isnull=True)

        try:
            limit = min(int(request.GET.get('limit', 50)), 200)
            offset = max(0, int(request.GET.get('offset', 0)))
        except ValueError:
            limit, offset = 50, 0

        total = qs.count()
        data = []
        for n in qs[offset:offset + limit]:
            data.append({
                'uuid': str(n.uuid),
                'title': n.title,
                'message': n.message,
                'source_app': n.source_app,
                'notification_type': n.notification_type,
                'priority': n.priority,
                'action_url': n.action_url,
                'due_date': n.due_date.isoformat() if n.due_date else None,
                'is_read': bool(n.read_at),
                'is_dismissed': bool(n.dismissed_at),
                'sent_by_email': bool(n.sent_by_email_at),
                'created_at': n.created_at.isoformat(),
                'user': {
                    'username': n.user.username,
                    'first_name': n.user.first_name,
                    'last_name': n.user.last_name,
                },
            })

        return Response({
            'success': True,
            'data': data,
            'total': total,
            'limit': limit,
            'offset': offset,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des notifications admin: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des notifications',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_email_logs(request):
    """
    API admin pour récupérer les logs des emails de relance.
    Security by Design : is_staff ET is_superuser requis (deny by default).
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'success': False, 'message': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)

    try:
        limit = min(int(request.GET.get('limit', 50)), 200)
        success_filter = request.GET.get('success')

        queryset = ReminderEmailLog.objects.select_related('user').order_by('-sent_at')

        if success_filter == 'true':
            queryset = queryset.filter(success=True)
        elif success_filter == 'false':
            queryset = queryset.filter(success=False)

        logs = queryset[:limit]

        data = []
        for log in logs:
            data.append({
                'uuid': str(log.uuid),
                'recipient': log.recipient,
                'subject': log.subject,
                'sent_at': log.sent_at.isoformat(),
                'success': log.success,
                'error_message': log.error_message or '',
                'ip_address': log.ip_address,
                'user': {
                    'username': log.user.username,
                    'first_name': log.user.first_name,
                    'last_name': log.user.last_name,
                } if log.user else None,
            })

        return Response({
            'success': True,
            'data': data,
            'count': len(data),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs email: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des logs email',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Vues existantes pour les paramètres
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def natures_list(request):
    """
    Liste des natures
    """
    try:
        natures = Nature.objects.filter(is_active=True).order_by('nom')
        data = []
        for nature in natures:
            data.append({
                'uuid': str(nature.uuid),
                'nom': nature.nom,
                'description': nature.description,
                'created_at': nature.created_at.isoformat(),
                'is_active': nature.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des natures: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des natures',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories_list(request):
    """
    Liste des catégories
    """
    try:
        categories = Categorie.objects.filter(is_active=True).order_by('nom')
        data = []
        for categorie in categories:
            data.append({
                'uuid': str(categorie.uuid),
                'nom': categorie.nom,
                'description': categorie.description,
                'created_at': categorie.created_at.isoformat(),
                'is_active': categorie.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des catégories: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des catégories',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sources_list(request):
    """
    Liste des sources
    """
    try:
        sources = Source.objects.filter(is_active=True).order_by('nom')
        data = []
        for source in sources:
            data.append({
                'uuid': str(source.uuid),
                'nom': source.nom,
                'description': source.description,
                'created_at': source.created_at.isoformat(),
                'is_active': source.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sources: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des sources',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def action_types_list(request):
    """
    Liste des types d'action
    """
    try:
        action_types = ActionType.objects.filter(is_active=True).order_by('nom')
        data = []
        for action_type in action_types:
            data.append({
                'uuid': str(action_type.uuid),
                'nom': action_type.nom,
                'description': action_type.description,
                'created_at': action_type.created_at.isoformat(),
                'is_active': action_type.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des types d'action: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des types d\'action',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statuts_list(request):
    """
    Liste des statuts
    """
    try:
        statuts = Statut.objects.all().order_by('nom')
        data = []
        for statut in statuts:
            data.append({
                'uuid': str(statut.uuid),
                'nom': statut.nom,
                'description': statut.description,
                'created_at': statut.created_at.isoformat(),
                'updated_at': statut.updated_at.isoformat()
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statuts: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des statuts',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def etats_mise_en_oeuvre_list(request):
    """
    Liste des états de mise en œuvre
    """
    try:
        etats = EtatMiseEnOeuvre.objects.filter(is_active=True).order_by('nom')
        data = []
        for etat in etats:
            data.append({
                'uuid': str(etat.uuid),
                'nom': etat.nom,
                'description': etat.description,
                'created_at': etat.created_at.isoformat(),
                'is_active': etat.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des états de mise en œuvre: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des états de mise en œuvre',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appreciations_list(request):
    """
    Liste des appréciations
    """
    try:
        appreciations = Appreciation.objects.filter(is_active=True).order_by('nom')
        data = []
        for appreciation in appreciations:
            data.append({
                'uuid': str(appreciation.uuid),
                'nom': appreciation.nom,
                'description': appreciation.description,
                'created_at': appreciation.created_at.isoformat(),
                'is_active': appreciation.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des appréciations: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des appréciations',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statuts_action_cdr_list(request):
    """
    Liste des statuts d'action CDR
    """
    try:
        statuts = StatutActionCDR.objects.filter(is_active=True).order_by('nom')
        data = []
        for statut in statuts:
            data.append({
                'uuid': str(statut.uuid),
                'nom': statut.nom,
                'description': statut.description,
                'created_at': statut.created_at.isoformat(),
                'is_active': statut.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statuts d'action: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des statuts d\'action',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def directions_list(request):
    """
    Liste des directions
    """
    try:
        directions = Direction.objects.filter(is_active=True).order_by('nom')
        data = []
        for direction in directions:
            data.append({
                'uuid': str(direction.uuid),
                'nom': direction.nom,
                'description': direction.description,
                'created_at': direction.created_at.isoformat(),
                'is_active': direction.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des directions: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des directions',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sous_directions_list(request):
    """
    Liste des sous-directions
    """
    try:
        direction_uuid = request.GET.get('direction_uuid')
        sous_directions = SousDirection.objects.select_related('direction').filter(is_active=True)
        
        if direction_uuid:
            sous_directions = sous_directions.filter(direction__uuid=direction_uuid)
        
        sous_directions = sous_directions.order_by('direction__nom', 'nom')

        data = []
        for sous_direction in sous_directions:
            data.append({
                'uuid': str(sous_direction.uuid),
                'nom': sous_direction.nom,
                'description': sous_direction.description,
                'direction': {
                    'uuid': str(sous_direction.direction.uuid),
                    'nom': sous_direction.direction.nom
                },
                'created_at': sous_direction.created_at.isoformat(),
                'is_active': sous_direction.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sous-directions: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des sous-directions',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def services_list(request):
    """
    Liste des services
    """
    try:
        sous_direction_uuid = request.GET.get('sous_direction_uuid')
        services = Service.objects.select_related('sous_direction__direction').filter(is_active=True)
        
        if sous_direction_uuid:
            services = services.filter(sous_direction__uuid=sous_direction_uuid)
        
        services = services.order_by('sous_direction__direction__nom', 'sous_direction__nom', 'nom')

        data = []
        for service in services:
            data.append({
                'uuid': str(service.uuid),
                'nom': service.nom,
                'description': service.description,
                'sous_direction': {
                    'uuid': str(service.sous_direction.uuid),
                    'nom': service.sous_direction.nom,
                    'direction': {
                        'uuid': str(service.sous_direction.direction.uuid),
                        'nom': service.sous_direction.direction.nom
                    }
                },
                'created_at': service.created_at.isoformat(),
                'is_active': service.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des services: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des services',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processus_list(request):
    """
    Liste des processus
    """
    try:
        processus = Processus.objects.select_related('cree_par').filter(is_active=True).order_by('numero_processus')
        data = []
        for processus in processus:
            data.append({
                'uuid': str(processus.uuid),
                'numero_processus': processus.numero_processus,
                'nom': processus.nom,
                'description': processus.description,
                'cree_par': {
                    'id': processus.cree_par.id,
                    'username': processus.cree_par.username,
                    'first_name': processus.cree_par.first_name,
                    'last_name': processus.cree_par.last_name
                },
                'created_at': processus.created_at.isoformat(),
                'is_active': processus.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des processus: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des processus',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dysfonctionnements_list(request):
    """
    Liste des dysfonctionnements/recommandations (éléments actifs uniquement)
    """
    try:
        dysfonctionnements = DysfonctionnementRecommandation.objects.select_related('cree_par').filter(is_active=True).order_by('nom')
        data = []
        for dysfonctionnement in dysfonctionnements:
            data.append({
                'uuid': str(dysfonctionnement.uuid),
                'nom': dysfonctionnement.nom,
                'description': dysfonctionnement.description,
                'cree_par': {
                    'id': dysfonctionnement.cree_par.id,
                    'username': dysfonctionnement.cree_par.username,
                    'first_name': dysfonctionnement.cree_par.first_name,
                    'last_name': dysfonctionnement.cree_par.last_name
                },
                'created_at': dysfonctionnement.created_at.isoformat(),
                'is_active': dysfonctionnement.is_active,
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des dysfonctionnements: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des dysfonctionnements',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dysfonctionnements_all_list(request):
    """
    Liste de tous les dysfonctionnements/recommandations (y compris les désactivés) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(DysfonctionnementRecommandation, order_by='nom', include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de tous les dysfonctionnements: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les dysfonctionnements',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== CRUD ENDPOINTS ====================

# Appreciations CRUD
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def appreciation_create(request):
    """Créer une nouvelle appréciation — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = AppreciationSerializer(data=request.data)
        if serializer.is_valid():
            appreciation = serializer.save()
            return Response(AppreciationSerializer(appreciation).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'appréciation: {str(e)}")
        return Response({'error': 'Impossible de créer l\'appréciation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def appreciation_update(request, uuid):
    """Mettre à jour une appréciation — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        appreciation = Appreciation.objects.get(uuid=uuid)
        serializer = AppreciationSerializer(appreciation, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Appreciation.DoesNotExist:
        return Response({'error': 'Appréciation non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'appréciation: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour l\'appréciation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def appreciation_delete(request, uuid):
    """Supprimer une appréciation — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        appreciation = Appreciation.objects.get(uuid=uuid)
        appreciation.delete()
        return Response({'message': 'Appréciation supprimée avec succès'}, status=status.HTTP_200_OK)
    except Appreciation.DoesNotExist:
        return Response({'error': 'Appréciation non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'appréciation: {str(e)}")
        return Response({'error': 'Impossible de supprimer l\'appréciation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Categories CRUD
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def categorie_create(request):
    """Créer une nouvelle catégorie — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = CategorieSerializer(data=request.data)
        if serializer.is_valid():
            categorie = serializer.save()
            return Response(CategorieSerializer(categorie).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de la catégorie: {str(e)}")
        return Response({'error': 'Impossible de créer la catégorie'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def categorie_update(request, uuid):
    """Mettre à jour une catégorie — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        categorie = Categorie.objects.get(uuid=uuid)
        serializer = CategorieSerializer(categorie, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Categorie.DoesNotExist:
        return Response({'error': 'Catégorie non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la catégorie: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour la catégorie'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def categorie_delete(request, uuid):
    """Supprimer une catégorie — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        categorie = Categorie.objects.get(uuid=uuid)
        categorie.delete()
        return Response({'message': 'Catégorie supprimée avec succès'}, status=status.HTTP_200_OK)
    except Categorie.DoesNotExist:
        return Response({'error': 'Catégorie non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la catégorie: {str(e)}")
        return Response({'error': 'Impossible de supprimer la catégorie'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Directions CRUD
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def direction_create(request):
    """Créer une nouvelle direction — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = DirectionSerializer(data=request.data)
        if serializer.is_valid():
            direction = serializer.save()
            return Response(DirectionSerializer(direction).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de la direction: {str(e)}")
        return Response({'error': 'Impossible de créer la direction'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def direction_update(request, uuid):
    """Mettre à jour une direction — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        direction = Direction.objects.get(uuid=uuid)
        serializer = DirectionSerializer(direction, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Direction.DoesNotExist:
        return Response({'error': 'Direction non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la direction: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour la direction'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def direction_delete(request, uuid):
    """Supprimer une direction — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        direction = Direction.objects.get(uuid=uuid)
        direction.delete()
        return Response({'message': 'Direction supprimée avec succès'}, status=status.HTTP_200_OK)
    except Direction.DoesNotExist:
        return Response({'error': 'Direction non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la direction: {str(e)}")
        return Response({'error': 'Impossible de supprimer la direction'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# SousDirections CRUD
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sous_direction_create(request):
    """Créer une nouvelle sous-direction — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = SousDirectionSerializer(data=request.data)
        if serializer.is_valid():
            sous_direction = serializer.save()
            return Response(SousDirectionSerializer(sous_direction).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de la sous-direction: {str(e)}")
        return Response({'error': 'Impossible de créer la sous-direction'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def sous_direction_update(request, uuid):
    """Mettre à jour une sous-direction — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        sous_direction = SousDirection.objects.get(uuid=uuid)
        serializer = SousDirectionSerializer(sous_direction, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except SousDirection.DoesNotExist:
        return Response({'error': 'Sous-direction non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la sous-direction: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour la sous-direction'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def sous_direction_delete(request, uuid):
    """Supprimer une sous-direction — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        sous_direction = SousDirection.objects.get(uuid=uuid)
        sous_direction.delete()
        return Response({'message': 'Sous-direction supprimée avec succès'}, status=status.HTTP_200_OK)
    except SousDirection.DoesNotExist:
        return Response({'error': 'Sous-direction non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la sous-direction: {str(e)}")
        return Response({'error': 'Impossible de supprimer la sous-direction'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ActionTypes CRUD
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def action_type_create(request):
    """Créer un nouveau type d'action — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = ActionTypeSerializer(data=request.data)
        if serializer.is_valid():
            action_type = serializer.save()
            return Response(ActionTypeSerializer(action_type).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du type d'action: {str(e)}")
        return Response({'error': 'Impossible de créer le type d\'action'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def action_type_update(request, uuid):
    """Mettre à jour un type d'action — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        action_type = ActionType.objects.get(uuid=uuid)
        serializer = ActionTypeSerializer(action_type, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except ActionType.DoesNotExist:
        return Response({'error': 'Type d\'action non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du type d'action: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour le type d\'action'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def action_type_delete(request, uuid):
    """Supprimer un type d'action — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        action_type = ActionType.objects.get(uuid=uuid)
        action_type.delete()
        return Response({'message': 'Type d\'action supprimé avec succès'}, status=status.HTTP_200_OK)
    except ActionType.DoesNotExist:
        return Response({'error': 'Type d\'action non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du type d'action: {str(e)}")
        return Response({'error': 'Impossible de supprimer le type d\'action'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== NOTIFICATIONS UPCOMING ====================

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
        logger.error(f"Erreur lors de la récupération des échéances: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération de la liste des notifications: {e}")
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
        logger.error(f"Erreur lors du marquage lu de la notification {uuid}: {e}")
        return Response(
            {'error': 'Impossible de marquer la notification comme lue'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== EMAIL SETTINGS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def email_settings_detail(request):
    """
    Récupérer les paramètres email globaux
    """
    try:
        settings = EmailSettings.get_solo()
        serializer = EmailSettingsSerializer(settings)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des paramètres email: {str(e)}")
        return Response({'error': 'Impossible de récupérer les paramètres email'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def email_settings_update(request):
    """
    Mettre à jour les paramètres email globaux
    """
    try:
        settings = EmailSettings.get_solo()
        serializer = EmailSettingsSerializer(settings, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            # Log de l'activité
            ActivityLog.objects.create(
                user=request.user,
                action='update',
                entity_type='email_settings',
                entity_id=str(settings.uuid),
                entity_name='Paramètres email',
                description=f'Paramètres email mis à jour par {request.user.username}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response({
                'message': 'Paramètres email mis à jour avec succès',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des paramètres email: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour les paramètres email'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_email_configuration(request):
    """
    Tester la configuration email (version sécurisée)
    Security by Design : Validation stricte, logging sécurisé
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from .utils.email_security import EmailValidator, EmailContentSanitizer, SecureEmailLogger
        
        email_settings = EmailSettings.get_solo()
        
        # Récupérer et valider l'email de test
        test_email = request.data.get('test_email', request.user.email)
        if not test_email:
            return Response({'error': 'Adresse email de test requise'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider l'email
        if not EmailValidator.is_valid_email(test_email):
            return Response({
                'error': 'Adresse email invalide',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que la configuration est complète
        if not email_settings.email_host_user or not email_settings.get_password():
            return Response({
                'error': 'Configuration email incomplète',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Test de connexion SMTP d'abord
        connection_ok, connection_message = email_settings.test_smtp_connection()
        if not connection_ok:
            SecureEmailLogger.log_security_event('smtp_connection_failed', {
                'user': request.user.username,
                'error': connection_message
            })
            return Response({
                'error': f'Échec de la connexion SMTP : {connection_message}',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Configuration temporaire
        original_config = {
            'EMAIL_HOST': getattr(settings, 'EMAIL_HOST', ''),
            'EMAIL_PORT': getattr(settings, 'EMAIL_PORT', 587),
            'EMAIL_HOST_USER': getattr(settings, 'EMAIL_HOST_USER', ''),
            'EMAIL_HOST_PASSWORD': getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
            'EMAIL_USE_TLS': getattr(settings, 'EMAIL_USE_TLS', True),
            'EMAIL_USE_SSL': getattr(settings, 'EMAIL_USE_SSL', False),
            'EMAIL_TIMEOUT': getattr(settings, 'EMAIL_TIMEOUT', 10),
        }
        
        # Appliquer la configuration depuis la base de données
        test_config = email_settings.get_email_config()
        for key, value in test_config.items():
            setattr(settings, key, value)
        
        try:
            # Préparer le contenu sécurisé
            subject = EmailContentSanitizer.sanitize_subject('Test de configuration email - KORA')
            message = EmailContentSanitizer.sanitize_html('Ceci est un email de test pour vérifier la configuration SMTP.')
            
            # Envoyer l'email
            send_mail(
                subject=subject,
                message=message,
                from_email=test_config['DEFAULT_FROM_EMAIL'],
                recipient_list=[test_email],
                fail_silently=False,
            )
            
            # Logger le succès
            SecureEmailLogger.log_email_sent(test_email, subject, True)
            
            # Créer un log d'activité
            ActivityLog.objects.create(
                user=request.user,
                action='test',
                entity_type='email_settings',
                entity_id=str(email_settings.uuid),
                entity_name='Configuration email',
                description=f'Test email réussi vers {SecureEmailLogger.mask_email(test_email)}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response({
                'message': f'Email de test envoyé avec succès à {test_email}',
                'status': 'success'
            }, status=status.HTTP_200_OK)
            
        except Exception as send_error:
            # Logger l'échec
            SecureEmailLogger.log_email_sent(test_email, 'Test email', False)
            
            return Response({
                'error': f'Erreur lors de l\'envoi : {str(send_error)}',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        finally:
            # Restaurer la configuration originale
            for key, value in original_config.items():
                setattr(settings, key, value)
        
    except Exception as e:
        logger.error(f"Erreur lors du test email: {str(e)}")
        return Response({
            'error': 'Erreur interne lors du test',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS POUR AFFICHAGE COMPLET (AVEC ÉLÉMENTS DÉSACTIVÉS) ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def natures_all_list(request):
    """
    Liste de toutes les natures (y compris les désactivées) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(Nature, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de toutes les natures: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de toutes les natures',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories_all_list(request):
    """
    Liste de toutes les catégories (y compris les désactivées) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(Categorie, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de toutes les catégories: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de toutes les catégories',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sources_all_list(request):
    """
    Liste de toutes les sources (y compris les désactivées) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(Source, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de toutes les sources: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de toutes les sources',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def action_types_all_list(request):
    """
    Liste de tous les types d'action (y compris les désactivés) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(ActionType, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de tous les types d'action: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les types d\'action',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statuts_all_list(request):
    """
    Liste de tous les statuts (y compris les désactivés) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(Statut, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de tous les statuts: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les statuts',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def etats_mise_en_oeuvre_all_list(request):
    """
    Liste de tous les états de mise en œuvre (y compris les désactivés) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(EtatMiseEnOeuvre, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de tous les états de mise en œuvre: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les états de mise en œuvre',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appreciations_all_list(request):
    """
    Liste de toutes les appréciations (y compris les désactivées) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(Appreciation, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de toutes les appréciations: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de toutes les appréciations',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def directions_all_list(request):
    """
    Liste de toutes les directions (y compris les désactivées) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(Direction, include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de toutes les directions: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de toutes les directions',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sous_directions_all_list(request):
    """
    Liste de toutes les sous-directions (y compris les désactivées) - pour l'affichage des données existantes
    """
    try:
        direction_uuid = request.GET.get('direction_uuid')
        sous_directions = SousDirection.objects.select_related('direction')
        
        if direction_uuid:
            sous_directions = sous_directions.filter(direction__uuid=direction_uuid)
        
        sous_directions = sous_directions.order_by('direction__nom', 'nom')
        
        data = []
        for sous_direction in sous_directions:
            data.append({
                'uuid': str(sous_direction.uuid),
                'nom': sous_direction.nom,
                'description': sous_direction.description,
                'is_active': sous_direction.is_active,
                'direction': {
                    'uuid': str(sous_direction.direction.uuid),
                    'nom': sous_direction.direction.nom
                },
                'created_at': sous_direction.created_at.isoformat(),
                'updated_at': sous_direction.updated_at.isoformat()
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de toutes les sous-directions: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de toutes les sous-directions',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def services_all_list(request):
    """
    Liste de tous les services (y compris les désactivés) - pour l'affichage des données existantes
    """
    try:
        sous_direction_uuid = request.GET.get('sous_direction_uuid')
        services = Service.objects.select_related('sous_direction__direction')
        
        if sous_direction_uuid:
            services = services.filter(sous_direction__uuid=sous_direction_uuid)
        
        services = services.order_by('sous_direction__direction__nom', 'sous_direction__nom', 'nom')

        data = []
        for service in services:
            data.append({
                'uuid': str(service.uuid),
                'nom': service.nom,
                'description': service.description,
                'is_active': service.is_active,
                'sous_direction': {
                    'uuid': str(service.sous_direction.uuid),
                    'nom': service.sous_direction.nom,
                    'direction': {
                        'uuid': str(service.sous_direction.direction.uuid),
                        'nom': service.sous_direction.direction.nom
                    }
                },
                'created_at': service.created_at.isoformat(),
                'updated_at': service.updated_at.isoformat()
            })

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de tous les services: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les services',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processus_all_list(request):
    """
    Liste de tous les processus (y compris les désactivés) - pour l'affichage des données existantes
    """
    try:
        data = get_model_list_data(Processus, order_by='numero_processus', include_inactive=True)
        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de tous les processus: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les processus',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== MEDIAS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def media_create(request):
    """
    Créer un nouveau média (upload de fichier)
    """
    try:
        fichier = request.FILES.get('fichier')
        url_fichier = request.data.get('url_fichier')
        description = request.data.get('description', '')

        if not fichier and not url_fichier:
            return Response({
                'error': 'Fichier ou URL fichier requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Créer le média
        media = Media.objects.create(
            fichier=fichier if fichier else None,
            url_fichier=url_fichier if url_fichier else None,
            description=description if description else None
        )

        # Retourner les données du média créé
        return Response({
            'uuid': str(media.uuid),
            'fichier_url': media.get_url(),
            'url_fichier': media.url_fichier,
            'description': media.description,
            'created_at': media.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Erreur lors de la création du média: {str(e)}")
        return Response({
            'error': f'Impossible de créer le média: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def media_update_description(request, uuid):
    """Mettre à jour la description d'un média"""
    try:
        try:
            media = Media.objects.get(uuid=uuid)
        except Media.DoesNotExist:
            return Response({'error': 'Média non trouvé'}, status=status.HTTP_404_NOT_FOUND)

        description = request.data.get('description', '')
        media.description = description
        media.save()

        return Response({
            'success': True,
            'message': 'Description mise à jour avec succès',
            'media': {
                'uuid': str(media.uuid),
                'fichier_url': media.get_url(),
                'url_fichier': media.url_fichier,
                'description': media.description,
                'created_at': media.created_at.isoformat()
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la description: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour la description'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def media_list(request):
    """Lister les médias existants"""
    try:
        medias = Media.objects.all().order_by('-created_at')
        data = []
        for m in medias:
            data.append({
                'uuid': str(m.uuid),
                'fichier_url': m.get_url(),
                'url_fichier': m.url_fichier,
                'description': m.description,
                'created_at': m.created_at.isoformat()
            })
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des médias: {str(e)}")
        return Response({'error': 'Impossible de lister les médias'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preuve_create_with_medias(request):
    """Créer une preuve et y associer une liste de médias (uuids)."""
    try:
        titre = request.data.get('titre')
        media_uuids = request.data.get('medias', [])
        if not titre:
            return Response({'error': 'titre est requis'}, status=status.HTTP_400_BAD_REQUEST)
        preuve = Preuve.objects.create(titre=titre)
        if isinstance(media_uuids, list) and len(media_uuids) > 0:
            medias = list(Media.objects.filter(uuid__in=media_uuids))
            preuve.medias.add(*medias)
        return Response({
            'uuid': str(preuve.uuid),
            'titre': preuve.titre,
            'medias': [str(m.uuid) for m in preuve.medias.all()],
            'created_at': preuve.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Erreur lors de la création de la preuve: {str(e)}")
        return Response({'error': 'Impossible de créer la preuve'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preuve_add_medias(request, uuid):
    """Ajouter des médias à une preuve existante"""
    try:
        try:
            preuve = Preuve.objects.prefetch_related('medias').get(uuid=uuid)
        except Preuve.DoesNotExist:
            return Response({'error': 'Preuve non trouvée'}, status=status.HTTP_404_NOT_FOUND)
        
        media_uuids = request.data.get('medias', [])
        if not isinstance(media_uuids, list) or len(media_uuids) == 0:
            return Response({'error': 'medias (liste d\'UUIDs) est requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        medias = list(Media.objects.filter(uuid__in=media_uuids))
        if len(medias) != len(media_uuids):
            return Response({'error': 'Certains médias n\'ont pas été trouvés'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Ajouter les médias à la preuve (ManyToMany.add ignore les doublons)
        preuve.medias.add(*medias)
        
        # Recharger la preuve depuis la DB avec prefetch pour avoir les médias à jour
        # IMPORTANT: refresh_from_db() ne rafraîchit pas les relations ManyToMany
        preuve = Preuve.objects.prefetch_related('medias').get(uuid=uuid)
        
        return Response({
            'uuid': str(preuve.uuid),
            'titre': preuve.titre,
            'medias': [str(m.uuid) for m in preuve.medias.all()],
            'created_at': preuve.created_at.isoformat()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"[PREUVE_ADD_MEDIAS] Erreur lors de l'ajout de médias à la preuve: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({'error': 'Impossible d\'ajouter les médias à la preuve'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def preuve_remove_media(request, uuid, media_uuid):
    """Supprimer un média d'une preuve"""
    try:
        try:
            preuve = Preuve.objects.get(uuid=uuid)
        except Preuve.DoesNotExist:
            return Response({'error': 'Preuve non trouvée'}, status=status.HTTP_404_NOT_FOUND)

        try:
            media = Media.objects.get(uuid=media_uuid)
        except Media.DoesNotExist:
            return Response({'error': 'Média non trouvé'}, status=status.HTTP_404_NOT_FOUND)

        # Vérifier que le média appartient bien à cette preuve
        if media not in preuve.medias.all():
            return Response({'error': 'Ce média n\'appartient pas à cette preuve'}, status=status.HTTP_400_BAD_REQUEST)

        # Retirer le média de la preuve
        preuve.medias.remove(media)

        # Supprimer le média de la base de données (si souhaité)
        # Attention : cela supprimera aussi le fichier physique
        media.delete()

        return Response({
            'success': True,
            'message': 'Média supprimé avec succès',
            'preuve': {
                'uuid': str(preuve.uuid),
                'titre': preuve.titre,
                'medias': [str(m.uuid) for m in preuve.medias.all()]
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du média: {str(e)}")
        return Response({'error': 'Impossible de supprimer le média'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def preuves_list(request):
    """Lister les preuves avec leurs médias"""
    try:
        preuves = Preuve.objects.prefetch_related('medias').order_by('-created_at')
        data = []
        for p in preuves:
            data.append({
                'uuid': str(p.uuid),
                'titre': p.titre,
                'medias': [
                    {
                        'uuid': str(m.uuid),
                        'fichier_url': m.get_url(),
                        'url_fichier': m.url_fichier,
                        'created_at': m.created_at.isoformat()
                    }
                    for m in p.medias.all()
                ],
                'created_at': p.created_at.isoformat()
            })
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des preuves: {str(e)}")
        return Response({'error': 'Impossible de lister les preuves'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== FRÉQUENCES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def frequences_list(request):
    """
    Liste toutes les fréquences
    """
    try:
        frequences = Frequence.objects.all().order_by('nom')
        serializer = FrequenceSerializer(frequences, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des fréquences: {str(e)}")
        return Response({'error': 'Impossible de lister les fréquences'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mois_list(request):
    """
    Liste tous les mois avec leurs abréviations
    """
    try:
        from parametre.models import Mois
        mois = Mois.objects.all().order_by('numero')
        data = [{
            'uuid': str(m.uuid),
            'numero': m.numero,
            'nom': m.nom,
            'abreviation': m.abreviation
        } for m in mois]
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des mois: {str(e)}")
        return Response({'error': 'Impossible de lister les mois'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_list(request):
    """Liste toutes les périodicités"""
    try:
        from .models import Periodicite
        periodicites = Periodicite.objects.all().order_by('frequence_id', 'periode')
        
        # Créer un serializer simple pour les périodicités
        data = []
        for periodicite in periodicites:
            data.append({
                'uuid': str(periodicite.uuid),
                'periode': periodicite.periode,
                'periode_display': periodicite.get_periode_display(),
                'a_realiser': float(periodicite.a_realiser),
                'realiser': float(periodicite.realiser),
                'taux': float(periodicite.taux),
                'frequence_id': str(periodicite.frequence_id.uuid),
                'frequence_nom': periodicite.frequence_id.nom,
                'created_at': periodicite.created_at,
                'updated_at': periodicite.updated_at
            })
        
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des périodicités: {str(e)}")
        return Response({'error': 'Impossible de lister les périodicités'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ANNÉES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def annees_list(request):
    """
    Liste des années actives pour les formulaires
    """
    try:
        from .models import Annee
        from .serializers import AnneeSerializer
        
        annees = Annee.objects.filter(is_active=True).order_by('-annee')
        serializer = AnneeSerializer(annees, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des années: {str(e)}")
        return Response({'error': 'Impossible de lister les années'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def annees_all_list(request):
    """
    Liste de toutes les années (actives et inactives)
    """
    try:
        from .models import Annee
        from .serializers import AnneeSerializer
        
        annees = Annee.objects.all().order_by('-annee')
        serializer = AnneeSerializer(annees, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des années: {str(e)}")
        return Response({'error': 'Impossible de lister les années'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Années CRUD (super admin uniquement)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def annee_create(request):
    """Créer une nouvelle année"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        from .models import Annee
        from .serializers import AnneeSerializer
        serializer = AnneeSerializer(data=request.data)
        if serializer.is_valid():
            annee = serializer.save()
            return Response(AnneeSerializer(annee).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur annee_create: {e}")
        return Response({'error': "Impossible de créer l'année"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def annee_update(request, uuid):
    """Mettre à jour une année"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        from .models import Annee
        from .serializers import AnneeSerializer
        annee = Annee.objects.get(uuid=uuid)
        serializer = AnneeSerializer(annee, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Annee.DoesNotExist:
        return Response({'error': 'Année non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur annee_update: {e}")
        return Response({'error': "Impossible de mettre à jour l'année"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def annee_delete(request, uuid):
    """Supprimer une année"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        from .models import Annee
        annee = Annee.objects.get(uuid=uuid)
        annee.delete()
        return Response({'message': 'Année supprimée avec succès'}, status=status.HTTP_200_OK)
    except Annee.DoesNotExist:
        return Response({'error': 'Année non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur annee_delete: {e}")
        return Response({'error': "Impossible de supprimer l'année"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== TYPES DE TABLEAU ====================

# Les endpoints types_tableau_* ont été supprimés avec le modèle Versions.
# Les versions sont maintenant gérées via num_amendement (entier) sur chaque modèle.


# ==================== CARTOGRAPHIE DES RISQUES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def frequences_risque_list(request):
    """Liste toutes les fréquences de risque (actives uniquement)"""
    try:
        frequences = FrequenceRisque.objects.filter(is_active=True).order_by('libelle')
        data = [{
            'uuid': str(f.uuid),
            'libelle': f.libelle,
            'valeur': f.valeur,
            'is_active': f.is_active
        } for f in frequences]
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des fréquences de risque: {str(e)}")
        return Response({'error': 'Impossible de lister les fréquences de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gravites_risque_list(request):
    """Liste toutes les gravités de risque (actives uniquement)"""
    try:
        gravites = GraviteRisque.objects.filter(is_active=True).order_by('libelle')
        data = [{
            'uuid': str(g.uuid),
            'libelle': g.libelle,
            'code': g.code,
            'is_active': g.is_active
        } for g in gravites]
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des gravités de risque: {str(e)}")
        return Response({'error': 'Impossible de lister les gravités de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def criticités_risque_list(request):
    """Liste toutes les criticités de risque (actives uniquement)"""
    try:
        criticités = CriticiteRisque.objects.filter(is_active=True).order_by('libelle')
        data = [{
            'uuid': str(c.uuid),
            'libelle': c.libelle,
            'is_active': c.is_active
        } for c in criticités]
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des criticités de risque: {str(e)}")
        return Response({'error': 'Impossible de lister les criticités de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def criticites_all_list(request):
    """Liste toutes les criticités de risque (actives et inactives)"""
    try:
        criticites = CriticiteRisque.objects.all().order_by('libelle')
        serializer = CriticiteRisqueSerializer(criticites, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste de toutes les criticités: {str(e)}")
        return Response({'error': 'Impossible de lister les criticités'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criticite_create(request):
    """Créer une criticité de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = CriticiteRisqueSerializer(data=request.data)
        if serializer.is_valid():
            criticite = serializer.save()
            return Response(CriticiteRisqueSerializer(criticite).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de la criticité: {str(e)}")
        return Response({'error': 'Impossible de créer la criticité'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def criticite_update(request, uuid):
    """Mettre à jour une criticité de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        criticite = CriticiteRisque.objects.get(uuid=uuid)
        serializer = CriticiteRisqueSerializer(criticite, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except CriticiteRisque.DoesNotExist:
        return Response({'error': 'Criticité non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la criticité: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour la criticité'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def criticite_delete(request, uuid):
    """Supprimer une criticité de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        criticite = CriticiteRisque.objects.get(uuid=uuid)
        criticite.delete()
        return Response({'message': 'Criticité supprimée avec succès'}, status=status.HTTP_200_OK)
    except CriticiteRisque.DoesNotExist:
        return Response({'error': 'Criticité non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la criticité: {str(e)}")
        return Response({'error': 'Impossible de supprimer la criticité'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== DYSFONCTIONNEMENTS/RECOMMANDATIONS CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dysfonctionnement_create(request):
    """Créer un dysfonctionnement/recommandation — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = DysfonctionnementRecommandationSerializer(data=request.data)
        if serializer.is_valid():
            dysfn = serializer.save(cree_par=request.user)
            return Response(DysfonctionnementRecommandationSerializer(dysfn).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du dysfonctionnement: {str(e)}")
        return Response({'error': 'Impossible de créer le dysfonctionnement'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def dysfonctionnement_update(request, uuid):
    """Mettre à jour un dysfonctionnement/recommandation — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        dysfn = DysfonctionnementRecommandation.objects.get(uuid=uuid)
        serializer = DysfonctionnementRecommandationSerializer(dysfn, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except DysfonctionnementRecommandation.DoesNotExist:
        return Response({'error': 'Dysfonctionnement non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du dysfonctionnement: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour le dysfonctionnement'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def dysfonctionnement_delete(request, uuid):
    """Supprimer un dysfonctionnement/recommandation — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        dysfn = DysfonctionnementRecommandation.objects.get(uuid=uuid)
        dysfn.delete()
        return Response({'message': 'Dysfonctionnement supprimé avec succès'}, status=status.HTTP_200_OK)
    except DysfonctionnementRecommandation.DoesNotExist:
        return Response({'error': 'Dysfonctionnement non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du dysfonctionnement: {str(e)}")
        return Response({'error': 'Impossible de supprimer le dysfonctionnement'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def risques_list(request):
    """Liste tous les types de risques (actifs uniquement)"""
    try:
        risques = Risque.objects.filter(is_active=True).order_by('libelle')
        serializer = RisqueSerializer(risques, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des risques: {str(e)}")
        return Response({'error': 'Impossible de lister les risques'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def risques_all_list(request):
    """Liste tous les types de risques (actifs et inactifs)"""
    try:
        risques = Risque.objects.all().order_by('libelle')
        serializer = RisqueSerializer(risques, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des risques: {str(e)}")
        return Response({'error': 'Impossible de lister les risques'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def risque_create(request):
    """Créer un nouveau risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = RisqueSerializer(data=request.data)
        if serializer.is_valid():
            risque = serializer.save()
            return Response(RisqueSerializer(risque).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du risque: {str(e)}")
        return Response({'error': 'Impossible de créer le risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def risque_update(request, uuid):
    """Mettre à jour un risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        risque = Risque.objects.get(uuid=uuid)
        serializer = RisqueSerializer(risque, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Risque.DoesNotExist:
        return Response({'error': 'Risque non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du risque: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour le risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def risque_delete(request, uuid):
    """Supprimer un risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        risque = Risque.objects.get(uuid=uuid)
        risque.delete()
        return Response({'message': 'Risque supprimé avec succès'}, status=status.HTTP_200_OK)
    except Risque.DoesNotExist:
        return Response({'error': 'Risque non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du risque: {str(e)}")
        return Response({'error': 'Impossible de supprimer le risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== NATURES CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def nature_create(request):
    """Créer une nature — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = NatureSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(NatureSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur nature_create: {e}")
        return Response({'error': 'Impossible de créer la nature'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def nature_update(request, uuid):
    """Mettre à jour une nature — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Nature.objects.get(uuid=uuid)
        serializer = NatureSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Nature.DoesNotExist:
        return Response({'error': 'Nature non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur nature_update: {e}")
        return Response({'error': 'Impossible de mettre à jour la nature'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def nature_delete(request, uuid):
    """Supprimer une nature — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Nature.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Nature supprimée avec succès'}, status=status.HTTP_200_OK)
    except Nature.DoesNotExist:
        return Response({'error': 'Nature non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur nature_delete: {e}")
        return Response({'error': 'Impossible de supprimer la nature'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== SERVICES CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def service_create(request):
    """Créer un service — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = ServiceSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(ServiceSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur service_create: {e}")
        return Response({'error': 'Impossible de créer le service'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def service_update(request, uuid):
    """Mettre à jour un service — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Service.objects.get(uuid=uuid)
        serializer = ServiceSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Service.DoesNotExist:
        return Response({'error': 'Service non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur service_update: {e}")
        return Response({'error': 'Impossible de mettre à jour le service'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def service_delete(request, uuid):
    """Supprimer un service — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Service.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Service supprimé avec succès'}, status=status.HTTP_200_OK)
    except Service.DoesNotExist:
        return Response({'error': 'Service non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur service_delete: {e}")
        return Response({'error': 'Impossible de supprimer le service'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== PROCESSUS CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def processus_create(request):
    """Créer un processus — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = ProcessusSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save(cree_par=request.user)
            return Response(ProcessusSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur processus_create: {e}")
        return Response({'error': 'Impossible de créer le processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def processus_update(request, uuid):
    """Mettre à jour un processus — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Processus.objects.get(uuid=uuid)
        serializer = ProcessusSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Processus.DoesNotExist:
        return Response({'error': 'Processus non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur processus_update: {e}")
        return Response({'error': 'Impossible de mettre à jour le processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def processus_delete(request, uuid):
    """Supprimer un processus — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Processus.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Processus supprimé avec succès'}, status=status.HTTP_200_OK)
    except Processus.DoesNotExist:
        return Response({'error': 'Processus non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur processus_delete: {e}")
        return Response({'error': 'Impossible de supprimer le processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== MOIS CRUD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mois_create(request):
    """Créer un mois — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = MoisSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(MoisSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur mois_create: {e}")
        return Response({'error': 'Impossible de créer le mois'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def mois_update(request, uuid):
    """Mettre à jour un mois — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Mois.objects.get(uuid=uuid)
        serializer = MoisSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Mois.DoesNotExist:
        return Response({'error': 'Mois non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur mois_update: {e}")
        return Response({'error': 'Impossible de mettre à jour le mois'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def mois_delete(request, uuid):
    """Supprimer un mois — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Mois.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Mois supprimé avec succès'}, status=status.HTTP_200_OK)
    except Mois.DoesNotExist:
        return Response({'error': 'Mois non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur mois_delete: {e}")
        return Response({'error': 'Impossible de supprimer le mois'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== FRÉQUENCES CRUD ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def frequences_all_list(request):
    """Liste toutes les fréquences (admin)"""
    try:
        objs = Frequence.objects.all().order_by('nom')
        serializer = FrequenceSerializer(objs, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur frequences_all_list: {e}")
        return Response({'error': 'Impossible de lister les fréquences'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def frequence_create(request):
    """Créer une fréquence — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = FrequenceSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(FrequenceSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur frequence_create: {e}")
        return Response({'error': 'Impossible de créer la fréquence'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def frequence_update(request, uuid):
    """Mettre à jour une fréquence — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Frequence.objects.get(uuid=uuid)
        serializer = FrequenceSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Frequence.DoesNotExist:
        return Response({'error': 'Fréquence non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur frequence_update: {e}")
        return Response({'error': 'Impossible de mettre à jour la fréquence'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def frequence_delete(request, uuid):
    """Supprimer une fréquence — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = Frequence.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Fréquence supprimée avec succès'}, status=status.HTTP_200_OK)
    except Frequence.DoesNotExist:
        return Response({'error': 'Fréquence non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur frequence_delete: {e}")
        return Response({'error': 'Impossible de supprimer la fréquence'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== FRÉQUENCES RISQUE CRUD ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def frequences_risque_all_list(request):
    """Liste toutes les fréquences de risque (actives et inactives)"""
    try:
        objs = FrequenceRisque.objects.all().order_by('libelle')
        serializer = FrequenceRisqueSerializer(objs, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur frequences_risque_all_list: {e}")
        return Response({'error': 'Impossible de lister les fréquences de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def frequence_risque_create(request):
    """Créer une fréquence de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = FrequenceRisqueSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(FrequenceRisqueSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur frequence_risque_create: {e}")
        return Response({'error': 'Impossible de créer la fréquence de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def frequence_risque_update(request, uuid):
    """Mettre à jour une fréquence de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = FrequenceRisque.objects.get(uuid=uuid)
        serializer = FrequenceRisqueSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except FrequenceRisque.DoesNotExist:
        return Response({'error': 'Fréquence de risque non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur frequence_risque_update: {e}")
        return Response({'error': 'Impossible de mettre à jour la fréquence de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def frequence_risque_delete(request, uuid):
    """Supprimer une fréquence de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = FrequenceRisque.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Fréquence de risque supprimée avec succès'}, status=status.HTTP_200_OK)
    except FrequenceRisque.DoesNotExist:
        return Response({'error': 'Fréquence de risque non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur frequence_risque_delete: {e}")
        return Response({'error': 'Impossible de supprimer la fréquence de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== GRAVITÉS RISQUE CRUD ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gravites_risque_all_list(request):
    """Liste toutes les gravités de risque (actives et inactives)"""
    try:
        objs = GraviteRisque.objects.all().order_by('libelle')
        serializer = GraviteRisqueSerializer(objs, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur gravites_risque_all_list: {e}")
        return Response({'error': 'Impossible de lister les gravités de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gravite_risque_create(request):
    """Créer une gravité de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = GraviteRisqueSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(GraviteRisqueSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur gravite_risque_create: {e}")
        return Response({'error': 'Impossible de créer la gravité de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def gravite_risque_update(request, uuid):
    """Mettre à jour une gravité de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = GraviteRisque.objects.get(uuid=uuid)
        serializer = GraviteRisqueSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except GraviteRisque.DoesNotExist:
        return Response({'error': 'Gravité de risque non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur gravite_risque_update: {e}")
        return Response({'error': 'Impossible de mettre à jour la gravité de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def gravite_risque_delete(request, uuid):
    """Supprimer une gravité de risque — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = GraviteRisque.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Gravité de risque supprimée avec succès'}, status=status.HTTP_200_OK)
    except GraviteRisque.DoesNotExist:
        return Response({'error': 'Gravité de risque non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur gravite_risque_delete: {e}")
        return Response({'error': 'Impossible de supprimer la gravité de risque'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATUTS ACTION CDR CRUD ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statuts_action_cdr_all_list(request):
    """Liste tous les statuts d'action CDR (actifs et inactifs)"""
    try:
        objs = StatutActionCDR.objects.all().order_by('nom')
        serializer = StatutActionCDRSerializer(objs, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur statuts_action_cdr_all_list: {e}")
        return Response({'error': 'Impossible de lister les statuts'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def statut_action_cdr_create(request):
    """Créer un statut d'action CDR — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = StatutActionCDRSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(StatutActionCDRSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur statut_action_cdr_create: {e}")
        return Response({'error': 'Impossible de créer le statut'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def statut_action_cdr_update(request, uuid):
    """Mettre à jour un statut d'action CDR — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = StatutActionCDR.objects.get(uuid=uuid)
        serializer = StatutActionCDRSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except StatutActionCDR.DoesNotExist:
        return Response({'error': 'Statut non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur statut_action_cdr_update: {e}")
        return Response({'error': 'Impossible de mettre à jour le statut'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def statut_action_cdr_delete(request, uuid):
    """Supprimer un statut d'action CDR — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = StatutActionCDR.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Statut supprimé avec succès'}, status=status.HTTP_200_OK)
    except StatutActionCDR.DoesNotExist:
        return Response({'error': 'Statut non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur statut_action_cdr_delete: {e}")
        return Response({'error': 'Impossible de supprimer le statut'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== TYPES DE DOCUMENT CRUD ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def types_document_list(request):
    """Liste les types de document actifs"""
    try:
        objs = TypeDocument.objects.filter(is_active=True).order_by('nom')
        serializer = TypeDocumentSerializer(objs, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur types_document_list: {e}")
        return Response({'error': 'Impossible de lister les types de document'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def types_document_all_list(request):
    """Liste tous les types de document (actifs et inactifs)"""
    try:
        objs = TypeDocument.objects.all().order_by('nom')
        serializer = TypeDocumentSerializer(objs, many=True)
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur types_document_all_list: {e}")
        return Response({'error': 'Impossible de lister les types de document'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def type_document_create(request):
    """Créer un type de document — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = TypeDocumentSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(TypeDocumentSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur type_document_create: {e}")
        return Response({'error': 'Impossible de créer le type de document'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def type_document_update(request, uuid):
    """Mettre à jour un type de document — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = TypeDocument.objects.get(uuid=uuid)
        serializer = TypeDocumentSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except TypeDocument.DoesNotExist:
        return Response({'error': 'Type de document non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur type_document_update: {e}")
        return Response({'error': 'Impossible de mettre à jour le type de document'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def type_document_delete(request, uuid):
    """Supprimer un type de document — superadmin uniquement"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        obj = TypeDocument.objects.get(uuid=uuid)
        obj.delete()
        return Response({'message': 'Type de document supprimé avec succès'}, status=status.HTTP_200_OK)
    except TypeDocument.DoesNotExist:
        return Response({'error': 'Type de document non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur type_document_delete: {e}")
        return Response({'error': 'Impossible de supprimer le type de document'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== SYSTÈME DE RÔLES ====================

# Roles CRUD
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roles_list(request):
    """Liste des rôles actifs"""
    try:
        roles = Role.objects.filter(is_active=True).order_by('nom')
        serializer = RoleSerializer(roles, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des rôles: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des rôles',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roles_all_list(request):
    """
    Liste de tous les rôles (y compris les désactivés)
    Security by Design : Accessible uniquement aux utilisateurs avec is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent voir tous les rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        roles = Role.objects.all().order_by('nom')
        serializer = RoleSerializer(roles, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de tous les rôles: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les rôles',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def role_create(request):
    """
    Créer un nouveau rôle (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent créer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        serializer = RoleSerializer(data=request.data)
        if serializer.is_valid():
            role = serializer.save()
            log_activity(
                user=request.user,
                action='create',
                entity_type='role',
                entity_id=str(role.uuid),
                entity_name=role.nom,
                description=f"Création du rôle {role.nom}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du rôle: {str(e)}")
        return Response({'error': 'Impossible de créer le rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def role_update(request, uuid):
    """
    Mettre à jour un rôle (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent modifier des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        role = Role.objects.get(uuid=uuid)
        serializer = RoleSerializer(role, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            log_activity(
                user=request.user,
                action='update',
                entity_type='role',
                entity_id=str(role.uuid),
                entity_name=role.nom,
                description=f"Modification du rôle {role.nom}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Role.DoesNotExist:
        return Response({'error': 'Rôle non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du rôle: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour le rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def role_delete(request, uuid):
    """
    Supprimer un rôle (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent supprimer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        role = Role.objects.get(uuid=uuid)
        role_nom = role.nom
        role_code = role.code
        
        # Vérifier si le rôle est utilisé dans des attributions
        from parametre.models import UserProcessusRole
        user_roles_count = UserProcessusRole.objects.filter(role=role).count()
        
        if user_roles_count > 0:
            return Response({
                'error': f'Impossible de supprimer le rôle "{role_nom}". Il est actuellement attribué à {user_roles_count} utilisateur(s). Veuillez d\'abord retirer toutes les attributions de ce rôle.',
                'code': 'ROLE_IN_USE',
                'user_roles_count': user_roles_count
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Supprimer automatiquement les mappings de permissions associés au rôle
        from permissions.models import RolePermissionMapping
        from permissions.services.permission_service import PermissionService
        permission_mappings = RolePermissionMapping.objects.filter(role=role)
        permission_mappings_count = permission_mappings.count()
        
        if permission_mappings_count > 0:
            # Supprimer les mappings de permissions
            permission_mappings.delete()
            
            # Invalider le cache des permissions pour tous les utilisateurs qui avaient ce rôle
            # Récupérer tous les utilisateurs qui ont ce rôle
            user_processus_roles = UserProcessusRole.objects.filter(role=role).select_related('user', 'processus')
            affected_users = set()
            for upr in user_processus_roles:
                # processus peut être None pour les rôles globaux (is_global=True)
                if upr.processus:
                    affected_users.add((upr.user.id, str(upr.processus.uuid)))
                else:
                    affected_users.add((upr.user.id, None))
            
            # Invalider le cache pour chaque utilisateur/processus
            for user_id, processus_uuid in affected_users:
                try:
                    PermissionService.invalidate_user_cache(user_id, processus_uuid=processus_uuid)
                except Exception as e:
                    logger.warning(f"Erreur lors de l'invalidation du cache pour user_id={user_id}, processus={processus_uuid}: {e}")
            
            logger.info(f"Suppression de {permission_mappings_count} mapping(s) de permissions pour le rôle {role_nom}")
        
        # Supprimer le rôle (Django supprimera automatiquement les mappings restants via CASCADE)
        role.delete()
        
        # Construire le message de succès
        description_parts = [f"Suppression du rôle {role_nom} ({role_code})"]
        if permission_mappings_count > 0:
            description_parts.append(f"et de {permission_mappings_count} mapping(s) de permissions associé(s)")
        
        log_activity(
            user=request.user,
            action='delete',
            entity_type='role',
            entity_id=str(uuid),
            entity_name=role_nom,
            description=" ".join(description_parts),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Construire le message de réponse
        message = f'Rôle "{role_nom}" supprimé avec succès'
        if permission_mappings_count > 0:
            message += f' ({permission_mappings_count} mapping(s) de permissions supprimé(s) automatiquement)'
        
        return Response({
            'success': True,
            'message': message,
            'permission_mappings_deleted': permission_mappings_count
        }, status=status.HTTP_200_OK)
    except Role.DoesNotExist:
        return Response({'error': 'Rôle non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du rôle: {str(e)}")
        return Response({'error': 'Impossible de supprimer le rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UserProcessus CRUD
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_processus_list(request):
    """
    Liste des attributions processus-utilisateur.
    - Utilisateurs avec is_staff ET is_superuser (can_manage_users=True) : peuvent voir toutes les attributions, avec filtres optionnels.
    - Autres utilisateurs : ne voient que leurs propres attributions, sans filtres arbitraires.
    Security by Design : évite qu'un utilisateur normal liste les attributions d'autres utilisateurs.
    """
    try:
        from parametre.permissions import can_manage_users

        user_id = request.GET.get('user_id')
        processus_id = request.GET.get('processus_id')

        # Utilisateur avec droits de gestion : accès complet avec filtres
        if can_manage_users(request.user):
            queryset = UserProcessus.objects.select_related(
                'user', 'processus', 'attribue_par'
            ).filter(is_active=True)

            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if processus_id:
                queryset = queryset.filter(processus_id=processus_id)
        else:
            # Utilisateur normal : uniquement ses propres attributions actives
            queryset = UserProcessus.objects.select_related(
                'user', 'processus', 'attribue_par'
            ).filter(is_active=True, user=request.user)

        serializer = UserProcessusSerializer(queryset.order_by('-date_attribution'), many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des attributions processus: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des attributions processus',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_processus_create(request):
    """
    Créer une nouvelle attribution processus-utilisateur.
    Security by Design : réservé aux super administrateurs (can_manage_users).
    """
    try:
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response(
                {
                    'error': 'Accès refusé. Seuls les super administrateurs peuvent attribuer des processus.',
                    'code': 'PERMISSION_DENIED',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data['attribue_par'] = request.user.id
        
        serializer = UserProcessusSerializer(data=data)
        if serializer.is_valid():
            user_processus = serializer.save()
            log_activity(
                user=request.user,
                action='create',
                entity_type='user_processus',
                entity_id=str(user_processus.uuid),
                entity_name=f"{user_processus.user.username} - {user_processus.processus.nom}",
                description=f"Attribution du processus {user_processus.processus.nom} à {user_processus.user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(UserProcessusSerializer(user_processus).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'attribution processus: {str(e)}")
        return Response({'error': 'Impossible de créer l\'attribution processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def user_processus_update(request, uuid):
    """
    Mettre à jour une attribution processus-utilisateur.
    Security by Design : réservé aux super administrateurs (can_manage_users).
    """
    try:
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response(
                {
                    'error': 'Accès refusé. Seuls les super administrateurs peuvent modifier des attributions processus.',
                    'code': 'PERMISSION_DENIED',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_processus = UserProcessus.objects.get(uuid=uuid)
        serializer = UserProcessusSerializer(user_processus, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            log_activity(
                user=request.user,
                action='update',
                entity_type='user_processus',
                entity_id=str(user_processus.uuid),
                entity_name=f"{user_processus.user.username} - {user_processus.processus.nom}",
                description=f"Modification de l'attribution processus {user_processus.processus.nom} pour {user_processus.user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except UserProcessus.DoesNotExist:
        return Response({'error': 'Attribution processus non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'attribution processus: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour l\'attribution processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def user_processus_delete(request, uuid):
    """
    Supprimer une attribution processus-utilisateur.
    Security by Design : réservé aux super administrateurs (can_manage_users).
    """
    try:
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response(
                {
                    'error': 'Accès refusé. Seuls les super administrateurs peuvent supprimer des attributions processus.',
                    'code': 'PERMISSION_DENIED',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_processus = UserProcessus.objects.get(uuid=uuid)
        user_processus.delete()
        log_activity(
            user=request.user,
            action='delete',
            entity_type='user_processus',
            entity_id=str(user_processus.uuid),
            entity_name=f"{user_processus.user.username} - {user_processus.processus.nom}",
            description=f"Suppression de l'attribution processus {user_processus.processus.nom} pour {user_processus.user.username}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return Response({'message': 'Attribution processus supprimée avec succès'}, status=status.HTTP_200_OK)
    except UserProcessus.DoesNotExist:
        return Response({'error': 'Attribution processus non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'attribution processus: {str(e)}")
        return Response({'error': 'Impossible de supprimer l\'attribution processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UserProcessusRole CRUD
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_processus_role_list(request):
    """
    Liste des rôles attribués aux utilisateurs pour les processus
    - Utilisateurs avec is_staff ET is_superuser : voient tous les rôles
    - Autres utilisateurs : voient uniquement leurs propres rôles
    Security by Design : Vérifie can_manage_users pour voir tous les rôles
    """
    try:
        from parametre.permissions import can_manage_users
        
        # ========== FILTRAGE PAR UTILISATEUR (Security by Design) ==========
        if can_manage_users(request.user):
            # Utilisateur avec is_staff ET is_superuser : voir tous les rôles
            queryset = UserProcessusRole.objects.select_related('user', 'processus', 'role', 'attribue_par').filter(is_active=True)
        else:
            # Utilisateur normal : voir uniquement ses propres rôles
            queryset = UserProcessusRole.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('user', 'processus', 'role', 'attribue_par')
        # ========== FIN FILTRAGE ==========
        
        # Filtres additionnels (seulement pour utilisateurs avec is_staff ET is_superuser)
        if can_manage_users(request.user):
            user_id = request.GET.get('user_id')
            processus_id = request.GET.get('processus_id')
            role_id = request.GET.get('role_id')
            
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if processus_id:
                queryset = queryset.filter(processus_id=processus_id)
            if role_id:
                queryset = queryset.filter(role_id=role_id)
        
        serializer = UserProcessusRoleSerializer(queryset.order_by('-date_attribution'), many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des rôles utilisateur-processus: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des rôles utilisateur-processus',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_processus_role_create(request):
    """
    Créer une nouvelle attribution de rôle utilisateur-processus (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les super administrateurs peuvent attribuer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        data = request.data.copy()
        data['attribue_par'] = request.user.id
        
        # Vérifier si l'attribution existe déjà (contrainte UNIQUE)
        from parametre.models import UserProcessusRole
        user_id = data.get('user')
        processus_id = data.get('processus')
        role_id = data.get('role')
        
        is_global = data.get('is_global', False)
        if is_global and user_id and role_id:
            # Duplicate check for global roles
            existing = UserProcessusRole.objects.filter(
                user_id=user_id,
                role_id=role_id,
                is_global=True,
                is_active=True
            ).first()
            if existing:
                return Response({
                    'error': 'Ce rôle global est déjà attribué à cet utilisateur.',
                    'code': 'ALREADY_EXISTS',
                    'existing_uuid': str(existing.uuid)
                }, status=status.HTTP_400_BAD_REQUEST)

        if user_id and processus_id and role_id:
            existing = UserProcessusRole.objects.filter(
                user_id=user_id,
                processus_id=processus_id,
                role_id=role_id,
                is_active=True
            ).first()

            if existing:
                # Retourner une réponse 400 avec un message clair au lieu d'une erreur 500
                return Response({
                    'error': 'Ce rôle est déjà attribué à cet utilisateur pour ce processus.',
                    'code': 'ALREADY_EXISTS',
                    'existing_uuid': str(existing.uuid)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = UserProcessusRoleSerializer(data=data)
        if serializer.is_valid():
            user_processus_role = serializer.save()
            log_activity(
                user=request.user,
                action='create',
                entity_type='user_processus_role',
                entity_id=str(user_processus_role.uuid),
                entity_name=(
                    f"{user_processus_role.user.username} - "
                    f"{'[GLOBAL]' if user_processus_role.is_global else user_processus_role.processus.nom} - "
                    f"{user_processus_role.role.nom}"
                ),
                description=(
                    f"Attribution du rôle {user_processus_role.role.nom} pour "
                    f"{user_processus_role.user.username} "
                    + (
                        "sur tous les processus (rôle global)"
                        if user_processus_role.is_global
                        else f"sur le processus {user_processus_role.processus.nom}"
                    )
                ),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(UserProcessusRoleSerializer(user_processus_role).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'attribution de rôle: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Vérifier si c'est une erreur de contrainte UNIQUE
        error_str = str(e)
        if 'UNIQUE constraint' in error_str or 'unique constraint' in error_str.lower():
            return Response({
                'error': 'Ce rôle est déjà attribué à cet utilisateur pour ce processus.',
                'code': 'ALREADY_EXISTS'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'error': 'Impossible de créer l\'attribution de rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def user_processus_role_update(request, uuid):
    """
    Mettre à jour une attribution de rôle utilisateur-processus (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent modifier des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        user_processus_role = UserProcessusRole.objects.get(uuid=uuid)
        serializer = UserProcessusRoleSerializer(user_processus_role, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            log_activity(
                user=request.user,
                action='update',
                entity_type='user_processus_role',
                entity_id=str(user_processus_role.uuid),
                entity_name=(
                    f"{user_processus_role.user.username} - "
                    f"{'[GLOBAL]' if user_processus_role.is_global else user_processus_role.processus.nom} - "
                    f"{user_processus_role.role.nom}"
                ),
                description=(
                    f"Modification de l'attribution du rôle {user_processus_role.role.nom} pour "
                    f"{user_processus_role.user.username} "
                    + (
                        "sur tous les processus (rôle global)"
                        if user_processus_role.is_global
                        else f"sur le processus {user_processus_role.processus.nom}"
                    )
                ),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except UserProcessusRole.DoesNotExist:
        return Response({'error': 'Attribution de rôle non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'attribution de rôle: {str(e)}")
        return Response({'error': 'Impossible de mettre à jour l\'attribution de rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def user_processus_role_delete(request, uuid):
    """
    Supprimer une attribution de rôle utilisateur-processus (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent supprimer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        user_processus_role = UserProcessusRole.objects.get(uuid=uuid)
        user_processus_role.delete()
        log_activity(
            user=request.user,
            action='delete',
            entity_type='user_processus_role',
            entity_id=str(user_processus_role.uuid),
            entity_name=(
                f"{user_processus_role.user.username} - "
                f"{'[GLOBAL]' if user_processus_role.is_global else user_processus_role.processus.nom} - "
                f"{user_processus_role.role.nom}"
            ),
            description=(
                f"Suppression de l'attribution du rôle {user_processus_role.role.nom} pour "
                f"{user_processus_role.user.username} "
                + (
                    "sur tous les processus (rôle global)"
                    if user_processus_role.is_global
                    else f"sur le processus {user_processus_role.processus.nom}"
                )
            ),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return Response({'message': 'Attribution de rôle supprimée avec succès'}, status=status.HTTP_200_OK)
    except UserProcessusRole.DoesNotExist:
        return Response({'error': 'Attribution de rôle non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'attribution de rôle: {str(e)}")
        return Response({'error': 'Impossible de supprimer l\'attribution de rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== GESTION DES UTILISATEURS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_list(request):
    """
    Liste tous les utilisateurs (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent voir la liste des utilisateurs.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        from django.contrib.auth.models import User
        
        # Filtres optionnels
        search = request.GET.get('search', '')
        is_active = request.GET.get('is_active')
        
        _last_login_qs = ActivityLog.objects.filter(user=OuterRef('pk'), action='login').order_by('-created_at')
        _last_logout_qs = ActivityLog.objects.filter(user=OuterRef('pk'), action='logout').order_by('-created_at')

        queryset = User.objects.annotate(
            last_login_activity=Subquery(_last_login_qs.values('created_at')[:1]),
            last_login_device=Subquery(_last_login_qs.values('device_type')[:1]),
            last_login_browser=Subquery(_last_login_qs.values('browser')[:1]),
            last_login_os=Subquery(_last_login_qs.values('os_name')[:1]),
            last_logout=Subquery(_last_logout_qs.values('created_at')[:1]),
        ).order_by('-date_joined')

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        serializer = UserSerializer(queryset, many=True)
        data = [
            {
                **dict(d),
                'last_login':         u.last_login_activity.isoformat() if u.last_login_activity else None,
                'last_login_device':  u.last_login_device,
                'last_login_browser': u.last_login_browser,
                'last_login_os':      u.last_login_os,
                'last_logout':        u.last_logout.isoformat()          if u.last_logout          else None,
            }
            for d, u in zip(serializer.data, queryset)
        ]
        return Response({
            'success': True,
            'data': data,
            'count': queryset.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des utilisateurs: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des utilisateurs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def users_create(request):
    """
    Créer un nouvel utilisateur (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent créer des utilisateurs.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Log de l'activité
            log_activity(
                user=request.user,
                action='create',
                entity_type='user',
                entity_id=str(user.id),
                entity_name=f"{user.username} ({user.email})",
                description=f"Création de l'utilisateur {user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Retourner l'utilisateur créé avec le serializer de lecture
            response_serializer = UserSerializer(user)
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Utilisateur créé avec succès'
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'error': 'Données invalides',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'utilisateur: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'utilisateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def users_invite(request):
    """
    Invite un nouvel utilisateur (is_staff ET is_superuser uniquement).
    Security by Design :
    - Vérifie les permissions via can_manage_users
    - Ne manipule jamais de mot de passe côté admin
    - Envoie un lien signé et limité dans le temps pour que l'utilisateur définisse son mot de passe
    """
    try:
        logger.info("=" * 60)
        logger.info("DEBUT users_invite")
        logger.info(f"Utilisateur qui invite: {request.user.username} (is_staff={request.user.is_staff}, is_superuser={request.user.is_superuser})")
        logger.info(f"IP: {get_client_ip(request)}")
        
        # ========== VÉRIFICATION DE SÉCURITÉ ==========
        from parametre.permissions import can_manage_users
        can_manage = can_manage_users(request.user)
        logger.info(f"can_manage_users: {can_manage}")
        
        if not can_manage:
            logger.warning(f"Accès refusé pour {request.user.username}")
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent inviter des utilisateurs.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Rate limiting basique pour éviter le spam d'invitations
        user_limit_ok = EmailRateLimiter.check_user_limit(request.user.id)
        global_limit_ok = EmailRateLimiter.check_global_limit()
        logger.info(f"Rate limiting - user_limit: {user_limit_ok}, global_limit: {global_limit_ok}")
        
        if not user_limit_ok or not global_limit_ok:
            SecureEmailLogger.log_security_event('invite_rate_limit_exceeded', {
                'user': request.user.username,
                'ip': get_client_ip(request),
                'type': 'user_invite'
            })
            logger.warning(f"Rate limit dépassé pour {request.user.username}")
            return Response({
                'success': False,
                'error': "Trop de tentatives d'invitation, veuillez réessayer plus tard."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Logger les données reçues pour le débogage
        logger.info(f"Données brutes reçues (request.data): {request.data}")
        logger.info(f"Type de request.data: {type(request.data)}")
        logger.info(f"Clés présentes: {list(request.data.keys()) if isinstance(request.data, dict) else 'N/A'}")
        
        # Vérifier si l'email existe déjà AVANT la validation du serializer
        email_received = request.data.get('email', '')
        logger.info(f"Email reçu: {email_received}")
        
        if email_received:
            from django.contrib.auth.models import User
            email_exists = User.objects.filter(email=email_received).exists()
            logger.info(f"Email existe déjà dans la DB: {email_exists}")
            if email_exists:
                existing_user = User.objects.filter(email=email_received).first()
                logger.info(f"Utilisateur existant trouvé: username={existing_user.username}, id={existing_user.id}, is_active={existing_user.is_active}")
        
        serializer = UserInviteSerializer(data=request.data)
        logger.info(f"Serializer créé, validation en cours...")
        
        if not serializer.is_valid():
            logger.error(f"ERREUR: Serializer invalide")
            logger.error(f"Erreurs de validation détaillées: {serializer.errors}")
            logger.error(f"Données qui ont causé l'erreur: {request.data}")
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info("Serializer valide, création de l'utilisateur...")

        user = serializer.save()
        logger.info(f"Utilisateur créé avec succès: username={user.username}, email={user.email}, id={user.id}, is_active={user.is_active}")

        # Générer un token d'invitation basé sur le système de reset password
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        logger.info(f"Token d'invitation généré: uid={uid}, token={token[:20]}...")

        frontend_base = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        raw_invite_url = f"{frontend_base}/set-password?uid={uid}&token={token}"
        invite_url = EmailContentSanitizer.sanitize_url(raw_invite_url)

        # Calculer la date d'expiration pour l'affichage dans l'email
        from datetime import datetime, timedelta
        invitation_timeout = getattr(settings, 'INVITATION_TOKEN_TIMEOUT', 604800)  # 7 jours par défaut
        expiration_date = datetime.now() + timedelta(seconds=invitation_timeout)
        expiration_str = expiration_date.strftime("%d/%m/%Y à %H:%M")

        # Vérifier l'email du destinataire
        if not EmailValidator.is_valid_email(user.email):
            return Response({
                'success': False,
                'error': "Adresse email du destinataire invalide."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Préparer le contexte pour le template
        context = {
            'user_first_name': user.first_name,
            'user_username': user.username,
            'user_email': user.email,
            'invite_url': invite_url,
            'expiration_date': expiration_str,
        }

        # Rendre les templates HTML et texte
        html_body = render_to_string('emails/user_invitation_email.html', context)
        text_body = render_to_string('emails/user_invitation_email.txt', context)
        
        subject = EmailContentSanitizer.sanitize_subject("KORA – Activation de votre compte")

        # Charger la configuration SMTP depuis EmailSettings
        config_ok = load_email_settings_into_django()
        if not config_ok:
            logger.warning("Configuration EmailSettings incomplète, utilisation de la configuration actuelle des settings.")

        # Envoyer l'email via la configuration courante
        logger.info(f"Envoi de l'email d'invitation à {user.email}...")
        logger.info(f"URL d'invitation: {invite_url}")
        
        try:
            send_mail(
                subject=subject,
                message=text_body,
                html_message=html_body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', user.email),
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email envoyé avec succès à {user.email}")
        except Exception as email_error:
            logger.error(f"ERREUR lors de l'envoi de l'email: {str(email_error)}")
            # Ne pas échouer complètement si l'email échoue, mais logger l'erreur
            SecureEmailLogger.log_email_sent(user.email, subject, False)

        SecureEmailLogger.log_email_sent(user.email, subject, True)

        # Log de l'activité
        log_activity(
            user=request.user,
            action='create',
            entity_type='user',
            entity_id=str(user.id),
            entity_name=f"{user.username} ({user.email})",
            description=f"Invitation de l'utilisateur {user.username}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        logger.info(f"Invitation terminée avec succès pour {user.email}")
        logger.info("=" * 60)
        
        return Response({
            'success': True,
            'message': "Invitation envoyée avec succès. L'utilisateur recevra un email pour définir son mot de passe."
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"ERREUR EXCEPTION dans users_invite: {str(e)}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback complet:\n{traceback.format_exc()}")
        logger.error("=" * 60)
        SecureEmailLogger.log_email_sent(getattr(request, 'user', None) and getattr(request.user, 'email', ''), "KORA – Invitation utilisateur", False)
        return Response({
            'success': False,
            'error': f"Erreur lors de l'invitation de l'utilisateur: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_get_user_processus(request):
    """Vue pour l'admin Django : retourne les processus d'un utilisateur"""
    from django.contrib.auth.models import User
    from django.http import JsonResponse
    
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'processus': []}, safe=False)
    
    try:
        user = User.objects.get(id=user_id)
        processus_list = UserProcessus.objects.filter(
            user=user,
            is_active=True
        ).select_related('processus')
        
        processus_data = []
        for up in processus_list:
            processus_data.append({
                'uuid': str(up.processus.uuid),
                'nom': up.processus.nom,
                'numero_processus': up.processus.numero_processus
            })
        
        return JsonResponse({'processus': processus_data}, safe=False)
    except User.DoesNotExist:
        return JsonResponse({'processus': []}, safe=False)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des processus utilisateur: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# ==================== APPLICATION CONFIG ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
        logger.error(f"Erreur application_config_list: {e}")
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
        logger.error(f"Erreur application_config_toggle: {e}")
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
            logger.error(f"[SSE] Erreur initialisation ({username}): {e}")
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
                logger.info(f"[SSE] Client déconnecté : {username}")
                break
            except Exception as e:
                logger.error(f"[SSE] Erreur stream ({username}): {e}")
                break

    response = StreamingHttpResponse(
        streaming_content=stream(),
        content_type='text/event-stream; charset=utf-8',
    )
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['X-Accel-Buffering'] = 'no'   # désactive le buffering Nginx
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
        logger.error(f"Erreur app_status: {e}")
        return JsonResponse({}, status=200)


# ==================== MONITORING SÉCURITÉ ====================

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

    # ── Comptes ciblés plusieurs fois dans les 7 derniers jours ───────────────
    suspicious_accounts = list(
        week.exclude(user=None)
            .values('user__id', 'user__username', 'user__email')
            .annotate(attempts=Count('id'))
            .filter(attempts__gte=3)
            .order_by('-attempts')[:10]
    )

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
        logger.info(f"[SECURITY] Déblocage manuel de '{value}' par {request.user.username}")
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
    logger.info(f"[SECURITY] Config mise à jour par {request.user.username}")
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
