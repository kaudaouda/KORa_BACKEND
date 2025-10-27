from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import json
import logging

from .models import (
    Nature, Categorie, Source, ActionType, Statut,
    EtatMiseEnOeuvre, Appreciation, Media, Direction, 
    SousDirection, Service, Processus, Preuve, ActivityLog,
    NotificationSettings, DashboardNotificationSettings, EmailSettings, DysfonctionnementRecommandation, Frequence
)
from .serializers import (
    AppreciationSerializer, CategorieSerializer, DirectionSerializer,
    SousDirectionSerializer, ActionTypeSerializer, NotificationSettingsSerializer,
    DashboardNotificationSettingsSerializer, EmailSettingsSerializer, FrequenceSerializer
)

logger = logging.getLogger(__name__)


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


def log_activity(user, action, entity_type, entity_id=None, entity_name=None, description=None, ip_address=None, user_agent=None):
    """
    Enregistre une activité utilisateur
    """
    try:
        activity_log = ActivityLog.objects.create(
            user=user,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            description=description or f"{user.username} a {action} {entity_type}",
            ip_address=ip_address,
            user_agent=user_agent
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
    return log_activity(
        user=user,
        action='create',
        entity_type='pac',
        entity_id=str(pac.uuid),
        entity_name=f"PAC {pac.numero_pac}",
        description=f"Création du PAC {pac.numero_pac}: {pac.libelle}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_pac_update(user, pac, ip_address=None, user_agent=None):
    """
    Log spécifique pour la modification d'un PAC
    """
    return log_activity(
        user=user,
        action='update',
        entity_type='pac',
        entity_id=str(pac.uuid),
        entity_name=f"PAC {pac.numero_pac}",
        description=f"Modification du PAC {pac.numero_pac}",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_traitement_creation(user, traitement, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un traitement
    """
    return log_activity(
        user=user,
        action='create',
        entity_type='traitement',
        entity_id=str(traitement.uuid),
        entity_name=f"Traitement pour PAC {traitement.pac.numero_pac}",
        description=f"Création d'un traitement: {traitement.action[:50]}...",
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_suivi_creation(user, suivi, ip_address=None, user_agent=None):
    """
    Log spécifique pour la création d'un suivi
    """
    return log_activity(
        user=user,
        action='create',
        entity_type='suivi',
        entity_id=str(suivi.uuid),
        entity_name=f"Suivi pour PAC {suivi.traitement.pac.numero_pac}",
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_activities(request):
    """
    API pour récupérer les activités récentes
    """
    try:
        limit = int(request.GET.get('limit', 10))
        user_specific = request.GET.get('user_only', 'false').lower() == 'true'
        
        # Récupération des activités directement
        queryset = ActivityLog.objects.select_related('user')
        
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
        
        # Récupération des activités de l'utilisateur
        activities = ActivityLog.objects.filter(user=request.user).select_related('user').order_by('-created_at')[:limit]
        
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
    """Créer une nouvelle appréciation"""
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
    """Mettre à jour une appréciation"""
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
    """Supprimer une appréciation"""
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
    """Créer une nouvelle catégorie"""
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
    """Mettre à jour une catégorie"""
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
    """Supprimer une catégorie"""
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
    """Créer une nouvelle direction"""
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
    """Mettre à jour une direction"""
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
    """Supprimer une direction"""
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
    """Créer une nouvelle sous-direction"""
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
    """Mettre à jour une sous-direction"""
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
    """Supprimer une sous-direction"""
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
    """Créer un nouveau type d'action"""
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
    """Mettre à jour un type d'action"""
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
    """Supprimer un type d'action"""
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
        from datetime import datetime, timedelta
        from django.utils import timezone
        from pac.models import Traitement
        
        today = timezone.now().date()
        notifications = []
        
        # Récupérer les paramètres de notification globaux
        global_settings = NotificationSettings.get_solo()
        
        # Traitements avec délais proches uniquement
        traitement_delai_days = global_settings.traitement_delai_notice_days
        traitement_cutoff_date = today + timedelta(days=traitement_delai_days)
        
        upcoming_traitements = Traitement.objects.filter(
            delai_realisation__lte=traitement_cutoff_date,
            delai_realisation__gte=today
        ).order_by('delai_realisation')
        
        for traitement in upcoming_traitements:
            days_until_due = (traitement.delai_realisation - today).days
            priority = 'high' if days_until_due <= 2 else 'medium' if days_until_due <= 5 else 'low'

            # Déterminer la nature (dysfonctionnement ou recommandation) via le PAC
            nature_label = None
            try:
                # Si une nature est liée sur PAC, utiliser son nom
                if getattr(traitement.pac, 'nature', None):
                    nature_name = (traitement.pac.nature.nom or '').strip().lower()
                    if 'recommand' in nature_name:
                        nature_label = 'Recommandation'
                    elif 'non' in nature_name or 'dysfonction' in nature_name:
                        nature_label = 'Dysfonctionnement'
                    else:
                        nature_label = traitement.pac.nature.nom
            except Exception:
                nature_label = None

            # Type d'action (ActionType.nom)
            type_action = None
            if getattr(traitement, 'type_action', None):
                try:
                    type_action = traitement.type_action.nom
                except Exception:
                    type_action = None

            # Libellé de délai + jours restants entre parenthèses
            delai_label = f"{traitement.delai_realisation.strftime('%d/%m/%Y')} ({days_until_due} jour{'s' if days_until_due > 1 else ''})"

            notifications.append({
                'id': f'traitement_{traitement.uuid}',
                'type': 'traitement',
                'title': f"{traitement.pac.numero_pac} - Action : {traitement.action[:50]}{'...' if len(traitement.action) > 50 else ''}",
                'message': f"Délai de réalisation dans {days_until_due} jour{'s' if days_until_due > 1 else ''}",
                'due_date': traitement.delai_realisation.isoformat(),
                'priority': priority,
                'action_url': f'/pac/traitement/{traitement.uuid}/show',
                'entity_id': str(traitement.uuid),
                # Champs ajoutés pour l'affichage
                'nature_label': nature_label,
                'type_action': type_action,
                'days_remaining': days_until_due,
                'delai_label': delai_label,
            })
        
        # Trier par priorité et date d'échéance
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        notifications.sort(key=lambda x: (priority_order.get(x['priority'], 3), x['due_date']))
        
        return Response({
            'notifications': notifications,
            'total': len(notifications),
            'settings': {
                'traitement_delai_notice_days': traitement_delai_days,
                'traitement_reminder_frequency_days': global_settings.traitement_reminder_frequency_days
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des échéances: {str(e)}")
        return Response({'error': 'Impossible de récupérer les échéances'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
    Tester la configuration email
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        email_settings = EmailSettings.get_solo()
        
        # Configuration temporaire pour le test
        original_config = {
            'EMAIL_HOST': getattr(settings, 'EMAIL_HOST', ''),
            'EMAIL_PORT': getattr(settings, 'EMAIL_PORT', 587),
            'EMAIL_HOST_USER': getattr(settings, 'EMAIL_HOST_USER', ''),
            'EMAIL_HOST_PASSWORD': getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
            'EMAIL_USE_TLS': getattr(settings, 'EMAIL_USE_TLS', True),
            'EMAIL_USE_SSL': getattr(settings, 'EMAIL_USE_SSL', False),
            'EMAIL_TIMEOUT': getattr(settings, 'EMAIL_TIMEOUT', 30),
        }
        
        # Appliquer la configuration depuis la base de données
        test_config = email_settings.get_email_config()
        for key, value in test_config.items():
            setattr(settings, key, value)
        
        # Envoyer un email de test
        test_email = request.data.get('test_email', request.user.email)
        if not test_email:
            return Response({'error': 'Adresse email de test requise'}, status=status.HTTP_400_BAD_REQUEST)
        
        send_mail(
            subject='Test de configuration email - KORA',
            message='Ceci est un email de test pour vérifier la configuration SMTP.',
            from_email=test_config['DEFAULT_FROM_EMAIL'],
            recipient_list=[test_email],
            fail_silently=False,
        )
        
        # Restaurer la configuration originale
        for key, value in original_config.items():
            setattr(settings, key, value)
        
        return Response({
            'message': f'Email de test envoyé avec succès à {test_email}',
            'status': 'success'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors du test email: {str(e)}")
        return Response({
            'error': f'Erreur lors de l\'envoi du test: {str(e)}',
            'status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)


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
        
        if not fichier and not url_fichier:
            return Response({
                'error': 'Fichier ou URL fichier requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Créer le média
        media = Media.objects.create(
            fichier=fichier if fichier else None,
            url_fichier=url_fichier if url_fichier else None
        )
        
        # Retourner les données du média créé
        return Response({
            'uuid': str(media.uuid),
            'fichier_url': media.get_url(),
            'url_fichier': media.url_fichier,
            'created_at': media.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Erreur lors de la création du média: {str(e)}")
        return Response({
            'error': f'Impossible de créer le média: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        description = request.data.get('description')
        media_uuids = request.data.get('medias', [])
        if not description:
            return Response({'error': 'description est requis'}, status=status.HTTP_400_BAD_REQUEST)
        preuve = Preuve.objects.create(description=description)
        if isinstance(media_uuids, list) and len(media_uuids) > 0:
            medias = list(Media.objects.filter(uuid__in=media_uuids))
            preuve.medias.add(*medias)
        return Response({
            'uuid': str(preuve.uuid),
            'description': preuve.description,
            'medias': [str(m.uuid) for m in preuve.medias.all()],
            'created_at': preuve.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Erreur lors de la création de la preuve: {str(e)}")
        return Response({'error': 'Impossible de créer la preuve'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                'description': p.description,
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

