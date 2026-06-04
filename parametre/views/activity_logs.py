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
        logger.error("Erreur lors de la récupération des activités: %s", e)
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
        logger.error("Erreur lors de la récupération des activités utilisateur: %s", e)
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
        logger.error("Erreur lors de la récupération des notifications admin: %s", e)
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
        logger.error("Erreur lors de la récupération des logs email: %s", e)
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des logs email',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

