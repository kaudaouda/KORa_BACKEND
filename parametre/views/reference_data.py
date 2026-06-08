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
    ReminderEmailLog, FailedLoginAttempt, LoginSecurityConfig, LoginBlock, Annee, Periodicite,
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
    TypeDocumentSerializer, AnneeSerializer,
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
        logger.error("Erreur lors de la récupération des natures: %s", e)
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
        logger.error("Erreur lors de la récupération des catégories: %s", e)
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
        logger.error("Erreur lors de la récupération des sources: %s", e)
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
        logger.error("Erreur lors de la récupération des types d'action: %s", e)
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
        logger.error("Erreur lors de la récupération des statuts: %s", e)
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
        logger.error("Erreur lors de la récupération des états de mise en œuvre: %s", e)
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
        logger.error("Erreur lors de la récupération des appréciations: %s", e)
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
        logger.error("Erreur lors de la récupération des statuts d'action: %s", e)
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
        logger.error("Erreur lors de la récupération des directions: %s", e)
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
        logger.error("Erreur lors de la récupération des sous-directions: %s", e)
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
        logger.error("Erreur lors de la récupération des services: %s", e)
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
        logger.error("Erreur lors de la récupération des processus: %s", e)
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
        logger.error("Erreur lors de la récupération des dysfonctionnements: %s", e)
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
        logger.error("Erreur lors de la récupération de tous les dysfonctionnements: %s", e)
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
        logger.error("Erreur lors de la création de l'appréciation: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour de l'appréciation: %s", str(e))
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
        logger.error("Erreur lors de la suppression de l'appréciation: %s", str(e))
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
        logger.error("Erreur lors de la création de la catégorie: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour de la catégorie: %s", str(e))
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
        logger.error("Erreur lors de la suppression de la catégorie: %s", str(e))
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
        logger.error("Erreur lors de la création de la direction: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour de la direction: %s", str(e))
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
        logger.error("Erreur lors de la suppression de la direction: %s", str(e))
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
        logger.error("Erreur lors de la création de la sous-direction: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour de la sous-direction: %s", str(e))
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
        logger.error("Erreur lors de la suppression de la sous-direction: %s", str(e))
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
        logger.error("Erreur lors de la création du type d'action: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour du type d'action: %s", str(e))
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
        logger.error("Erreur lors de la suppression du type d'action: %s", str(e))
        return Response({'error': 'Impossible de supprimer le type d\'action'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== NOTIFICATIONS UPCOMING ====================

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
        logger.error("Erreur lors de la récupération de toutes les natures: %s", e)
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
        logger.error("Erreur lors de la récupération de toutes les catégories: %s", e)
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
        logger.error("Erreur lors de la récupération de toutes les sources: %s", e)
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
        logger.error("Erreur lors de la récupération de tous les types d'action: %s", e)
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
        logger.error("Erreur lors de la récupération de tous les statuts: %s", e)
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
        logger.error("Erreur lors de la récupération de tous les états de mise en œuvre: %s", e)
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
        logger.error("Erreur lors de la récupération de toutes les appréciations: %s", e)
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
        logger.error("Erreur lors de la récupération de toutes les directions: %s", e)
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
        logger.error("Erreur lors de la récupération de toutes les sous-directions: %s", e)
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
        logger.error("Erreur lors de la récupération de tous les services: %s", e)
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
        logger.error("Erreur lors de la récupération de tous les processus: %s", e)
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les processus',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== MEDIAS ====================

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
        logger.error("Erreur lors de la liste des fréquences: %s", str(e))
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
        logger.error("Erreur lors de la liste des mois: %s", str(e))
        return Response({'error': 'Impossible de lister les mois'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_list(request):
    """Liste toutes les périodicités"""
    try:
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
        logger.error("Erreur lors de la liste des périodicités: %s", str(e))
        return Response({'error': 'Impossible de lister les périodicités'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ANNÉES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def annees_list(request):
    """
    Liste des années actives pour les formulaires
    """
    try:
        annees = Annee.objects.filter(is_active=True).order_by('-annee')
        serializer = AnneeSerializer(annees, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la liste des années: %s", str(e))
        return Response({'error': 'Impossible de lister les années'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def annees_all_list(request):
    """
    Liste de toutes les années (actives et inactives)
    """
    try:
        annees = Annee.objects.all().order_by('-annee')
        serializer = AnneeSerializer(annees, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la liste des années: %s", str(e))
        return Response({'error': 'Impossible de lister les années'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Années CRUD (super admin uniquement)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def annee_create(request):
    """Créer une nouvelle année"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        serializer = AnneeSerializer(data=request.data)
        if serializer.is_valid():
            annee = serializer.save()
            return Response(AnneeSerializer(annee).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur annee_create: %s", e)
        return Response({'error': "Impossible de créer l'année"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def annee_update(request, uuid):
    """Mettre à jour une année"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        annee = Annee.objects.get(uuid=uuid)
        serializer = AnneeSerializer(annee, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Annee.DoesNotExist:
        return Response({'error': 'Année non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur annee_update: %s", e)
        return Response({'error': "Impossible de mettre à jour l'année"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def annee_delete(request, uuid):
    """Supprimer une année"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
    try:
        annee = Annee.objects.get(uuid=uuid)
        annee.delete()
        return Response({'message': 'Année supprimée avec succès'}, status=status.HTTP_200_OK)
    except Annee.DoesNotExist:
        return Response({'error': 'Année non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur annee_delete: %s", e)
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
        logger.error("Erreur lors de la liste des fréquences de risque: %s", str(e))
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
        logger.error("Erreur lors de la liste des gravités de risque: %s", str(e))
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
        logger.error("Erreur lors de la liste des criticités de risque: %s", str(e))
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
        logger.error("Erreur lors de la liste de toutes les criticités: %s", str(e))
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
        logger.error("Erreur lors de la création de la criticité: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour de la criticité: %s", str(e))
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
        logger.error("Erreur lors de la suppression de la criticité: %s", str(e))
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
        logger.error("Erreur lors de la création du dysfonctionnement: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour du dysfonctionnement: %s", str(e))
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
        logger.error("Erreur lors de la suppression du dysfonctionnement: %s", str(e))
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
        logger.error("Erreur lors de la liste des risques: %s", str(e))
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
        logger.error("Erreur lors de la liste des risques: %s", str(e))
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
        logger.error("Erreur lors de la création du risque: %s", str(e))
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
        logger.error("Erreur lors de la mise à jour du risque: %s", str(e))
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
        logger.error("Erreur lors de la suppression du risque: %s", str(e))
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
        logger.error("Erreur nature_create: %s", e)
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
        logger.error("Erreur nature_update: %s", e)
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
        logger.error("Erreur nature_delete: %s", e)
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
        logger.error("Erreur service_create: %s", e)
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
        logger.error("Erreur service_update: %s", e)
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
        logger.error("Erreur service_delete: %s", e)
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
        logger.error("Erreur processus_create: %s", e)
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
        logger.error("Erreur processus_update: %s", e)
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
        logger.error("Erreur processus_delete: %s", e)
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
        logger.error("Erreur mois_create: %s", e)
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
        logger.error("Erreur mois_update: %s", e)
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
        logger.error("Erreur mois_delete: %s", e)
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
        logger.error("Erreur frequences_all_list: %s", e)
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
        logger.error("Erreur frequence_create: %s", e)
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
        logger.error("Erreur frequence_update: %s", e)
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
        logger.error("Erreur frequence_delete: %s", e)
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
        logger.error("Erreur frequences_risque_all_list: %s", e)
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
        logger.error("Erreur frequence_risque_create: %s", e)
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
        logger.error("Erreur frequence_risque_update: %s", e)
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
        logger.error("Erreur frequence_risque_delete: %s", e)
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
        logger.error("Erreur gravites_risque_all_list: %s", e)
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
        logger.error("Erreur gravite_risque_create: %s", e)
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
        logger.error("Erreur gravite_risque_update: %s", e)
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
        logger.error("Erreur gravite_risque_delete: %s", e)
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
        logger.error("Erreur statuts_action_cdr_all_list: %s", e)
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
        logger.error("Erreur statut_action_cdr_create: %s", e)
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
        logger.error("Erreur statut_action_cdr_update: %s", e)
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
        logger.error("Erreur statut_action_cdr_delete: %s", e)
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
        logger.error("Erreur types_document_list: %s", e)
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
        logger.error("Erreur types_document_all_list: %s", e)
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
        logger.error("Erreur type_document_create: %s", e)
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
        logger.error("Erreur type_document_update: %s", e)
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
        logger.error("Erreur type_document_delete: %s", e)
        return Response({'error': 'Impossible de supprimer le type de document'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== SYSTÈME DE RÔLES ====================

