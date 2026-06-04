from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
import logging
from django.db import models
from ..models import Objectives, Indicateur, Observation, TableauBord
from analyse_tableau.models import AnalyseTableau
from parametre.views import (
    log_tableau_bord_creation,
    log_tableau_bord_update,
    log_objectif_creation,
    log_indicateur_creation,
    get_client_ip
)
from parametre.permissions import get_user_processus_list, user_has_access_to_processus
from permissions.permissions import (
    DashboardTableauCreatePermission,
    DashboardTableauUpdatePermission,
    DashboardTableauDeletePermission,
    DashboardTableauValidatePermission,
    DashboardTableauDevalidatePermission,
    DashboardTableauReadPermission,
    DashboardTableauListCreatePermission,
    DashboardTableauDetailPermission,
    DashboardAmendementCreatePermission,
    DashboardObjectiveCreatePermission,
    DashboardObjectiveUpdatePermission,
    DashboardObjectiveDeletePermission,
    DashboardIndicateurCreatePermission,
    DashboardIndicateurUpdatePermission,
    DashboardIndicateurDeletePermission,
    DashboardCibleCreatePermission,
    DashboardCibleUpdatePermission,
    DashboardCibleDeletePermission,
    DashboardPeriodiciteCreatePermission,
    DashboardPeriodiciteUpdatePermission,
    DashboardPeriodiciteDeletePermission,
    DashboardObservationCreatePermission,
    DashboardObservationUpdatePermission,
    DashboardObservationDeletePermission,
)
from ..serializers import (
    ObjectivesSerializer, ObjectivesCreateSerializer, ObjectivesUpdateSerializer,
    IndicateurSerializer, IndicateurCreateSerializer, IndicateurUpdateSerializer,
    CibleSerializer, CibleCreateSerializer, CibleUpdateSerializer,
    PeriodiciteSerializer, PeriodiciteCreateSerializer, PeriodiciteUpdateSerializer,
    ObservationSerializer, ObservationCreateSerializer, ObservationUpdateSerializer,
    TableauBordSerializer
)

logger = logging.getLogger(__name__)

def objectives_list(request):
    """Liste tous les objectifs"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Filtrer les objectifs pour ne montrer que ceux des tableaux de bord accessibles
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les objectifs sans filtre
            objectives = Objectives.objects.all().order_by('number')
        elif user_processus_uuids:
            objectives = Objectives.objects.filter(
                tableau_bord__processus__uuid__in=user_processus_uuids
            ).order_by('number')
        else:
            objectives = Objectives.objects.none()  # Aucun processus, donc aucun objectif
        # ========== FIN FILTRAGE ==========
        
        serializer = ObjectivesSerializer(objectives, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': objectives.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération des objectifs: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des objectifs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def objectives_detail(request, uuid):
    """Détail d'un objectif"""
    try:
        objective = Objectives.objects.get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveUpdatePermission
        # via le décorateur @permission_classes
        
        serializer = ObjectivesSerializer(objective)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération de l'objectif %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardObjectiveCreatePermission])
def objectives_create(request):
    """Créer un nouvel objectif"""
    try:
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        tableau_bord_uuid = request.data.get('tableau_bord')
        if tableau_bord_uuid:
            try:
                tableau = TableauBord.objects.get(uuid=tableau_bord_uuid)
                
                # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveCreatePermission
                # via le décorateur @permission_classes
                
                if tableau.is_validated:
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer un objectif : le tableau est déjà validé'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Bloquer si un amendement suivant existe pour ce tableau
                has_successor = TableauBord.objects.filter(
                    annee=tableau.annee,
                    processus=tableau.processus,
                    num_amendement=tableau.num_amendement + 1
                ).exists()
                if has_successor:
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer un objectif : un amendement suivant existe pour ce tableau'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except TableauBord.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Tableau de bord non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ObjectivesCreateSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            objective = serializer.save()

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_objectif_creation(request.user, objective, ip_address, user_agent)
            except Exception as log_error:
                logger.error("Erreur lors du logging de la création de l'objectif: %s", log_error)

            # Retourner l'objectif créé avec tous ses détails
            response_serializer = ObjectivesSerializer(objective)

            return Response({
                'success': True,
                'message': 'Objectif créé avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Exception as e:
        logger.error("Erreur lors de la création de l'objectif: %s", str(e), exc_info=True)
        return Response({
            'success': False,
            'error': f'Erreur lors de la création de l\'objectif: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardObjectiveUpdatePermission])
def objectives_update(request, uuid):
    """Mettre à jour un objectif"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObjectiveUpdatePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'objectif depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        objective = Objectives.objects.select_related(
            'tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveUpdatePermission
        # via le décorateur @permission_classes
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        if objective.tableau_bord:
            if objective.tableau_bord.is_validated:
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'objectif : le tableau est déjà validé'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier que le tableau n'a pas d'amendements suivants
            if objective.tableau_bord.has_amendements():
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'objectif : ce tableau a des amendements suivants'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ObjectivesUpdateSerializer(objective, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_objective = serializer.save()
            
            # Retourner l'objectif mis à jour avec tous ses détails
            response_serializer = ObjectivesSerializer(updated_objective)
            
            logger.info("Objectif mis à jour: %s par %s", objective.number, request.user.username)
            
            return Response({
                'success': True,
                'message': 'Objectif mis à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la mise à jour de l'objectif %s: %s", uuid, str(e), exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardObjectiveDeletePermission])
def objectives_delete(request, uuid):
    """Supprimer un objectif"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObjectiveDeletePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'objectif depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        objective = Objectives.objects.select_related(
            'tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveDeletePermission
        # via le décorateur @permission_classes
        
        objective_number = objective.number
        objective.delete()
        
        logger.info("Objectif supprimé: %s par %s", objective_number, request.user.username)
        
        return Response({
            'success': True,
            'message': 'Objectif supprimé avec succès'
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la suppression de l'objectif %s: %s", uuid, str(e), exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
