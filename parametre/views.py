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
    SousDirection, Service, Processus, Preuve, ActivityLog
)
# Import supprimé - logique intégrée directement dans les vues

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
        natures = Nature.objects.all().order_by('nom')
        data = []
        for nature in natures:
            data.append({
                'uuid': str(nature.uuid),
                'nom': nature.nom,
                'description': nature.description,
                'created_at': nature.created_at.isoformat(),
                'updated_at': nature.updated_at.isoformat()
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
        categories = Categorie.objects.all().order_by('nom')
        data = []
        for categorie in categories:
            data.append({
                'uuid': str(categorie.uuid),
                'nom': categorie.nom,
                'description': categorie.description,
                'created_at': categorie.created_at.isoformat(),
                'updated_at': categorie.updated_at.isoformat()
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
        sources = Source.objects.all().order_by('nom')
        data = []
        for source in sources:
            data.append({
                'uuid': str(source.uuid),
                'nom': source.nom,
                'description': source.description,
                'created_at': source.created_at.isoformat(),
                'updated_at': source.updated_at.isoformat()
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
        action_types = ActionType.objects.all().order_by('nom')
        data = []
        for action_type in action_types:
            data.append({
                'uuid': str(action_type.uuid),
                'nom': action_type.nom,
                'description': action_type.description,
                'created_at': action_type.created_at.isoformat(),
                'updated_at': action_type.updated_at.isoformat()
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
        etats = EtatMiseEnOeuvre.objects.all().order_by('nom')
        data = []
        for etat in etats:
            data.append({
                'uuid': str(etat.uuid),
                'nom': etat.nom,
                'description': etat.description,
                'created_at': etat.created_at.isoformat(),
                'updated_at': etat.updated_at.isoformat()
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
        appreciations = Appreciation.objects.all().order_by('nom')
        data = []
        for appreciation in appreciations:
            data.append({
                'uuid': str(appreciation.uuid),
                'nom': appreciation.nom,
                'description': appreciation.description,
                'created_at': appreciation.created_at.isoformat(),
                'updated_at': appreciation.updated_at.isoformat()
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
        directions = Direction.objects.all().order_by('nom')
        data = []
        for direction in directions:
            data.append({
                'uuid': str(direction.uuid),
                'nom': direction.nom,
                'description': direction.description,
                'created_at': direction.created_at.isoformat(),
                'updated_at': direction.updated_at.isoformat()
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
        processus = Processus.objects.select_related('cree_par').order_by('numero_processus')
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
                'updated_at': processus.updated_at.isoformat()
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