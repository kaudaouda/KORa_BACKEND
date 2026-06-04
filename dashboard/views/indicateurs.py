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

def indicateurs_list(request):
    """Liste tous les indicateurs"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Filtrer les indicateurs pour ne montrer que ceux des tableaux de bord accessibles
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les indicateurs sans filtre
            indicateurs = Indicateur.objects.all().order_by('objective_id', 'libelle')
        elif user_processus_uuids:
            indicateurs = Indicateur.objects.filter(
                objective_id__tableau_bord__processus__uuid__in=user_processus_uuids
            ).order_by('objective_id', 'libelle')
        else:
            indicateurs = Indicateur.objects.none()  # Aucun processus, donc aucun indicateur
        # ========== FIN FILTRAGE ==========
        
        serializer = IndicateurSerializer(indicateurs, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': indicateurs.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération des indicateurs: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des indicateurs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicateurs_detail(request, uuid):
    """Détail d'un indicateur"""
    try:
        indicateur = Indicateur.objects.get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurUpdatePermission
        # via le décorateur @permission_classes
        
        serializer = IndicateurSerializer(indicateur)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération de l'indicateur %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardIndicateurCreatePermission])
def indicateurs_create(request):
    """Créer un nouvel indicateur"""
    try:
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        objective_uuid = request.data.get('objective_id')
        if objective_uuid:
            try:
                objective = Objectives.objects.get(uuid=objective_uuid)
                if objective.tableau_bord:
                    tableau = objective.tableau_bord
                    
                    # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurCreatePermission
                    # via le décorateur @permission_classes
                    
                    if tableau.is_validated:
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer un indicateur : le tableau est déjà validé'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Vérifier que le tableau n'a pas d'amendements suivants
                    if tableau.has_amendements():
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer un indicateur : ce tableau a des amendements suivants'
                        }, status=status.HTTP_400_BAD_REQUEST)
            except Objectives.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Objectif non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = IndicateurCreateSerializer(data=request.data)

        if serializer.is_valid():
            indicateur = serializer.save()

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_indicateur_creation(request.user, indicateur, ip_address, user_agent)
            except Exception as log_error:
                logger.error("Erreur lors du logging de la création de l'indicateur: %s", log_error)

            # Retourner l'indicateur créé avec tous ses détails
            response_serializer = IndicateurSerializer(indicateur)

            logger.info("Indicateur créé: %s par %s", indicateur.libelle, request.user.username)

            return Response({
                'success': True,
                'message': 'Indicateur créé avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error("Erreur lors de la création de l'indicateur: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardIndicateurUpdatePermission])
def indicateurs_update(request, uuid):
    """Mettre à jour un indicateur"""
    try:
        indicateur = Indicateur.objects.get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurUpdatePermission
        # via le décorateur @permission_classes
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        if indicateur.objective_id.tableau_bord:
            tableau = indicateur.objective_id.tableau_bord
            if tableau.is_validated:
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'indicateur : le tableau est déjà validé'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier que le tableau n'a pas d'amendements suivants
            if tableau.has_amendements():
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'indicateur : ce tableau a des amendements suivants'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = IndicateurUpdateSerializer(indicateur, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_indicateur = serializer.save()
            
            # Retourner l'indicateur mis à jour avec tous ses détails
            response_serializer = IndicateurSerializer(updated_indicateur)
            
            logger.info("Indicateur mis à jour: %s par %s", indicateur.libelle, request.user.username)
            
            return Response({
                'success': True,
                'message': 'Indicateur mis à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error("Erreur lors de la mise à jour de l'indicateur %s: %s\n%s", uuid, str(e), error_traceback)
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardIndicateurDeletePermission])
def indicateurs_delete(request, uuid):
    """Supprimer un indicateur"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardIndicateurDeletePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'indicateur depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        indicateur = Indicateur.objects.select_related(
            'objective_id__tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurDeletePermission
        # via le décorateur @permission_classes
        
        indicateur_libelle = indicateur.libelle
        indicateur.delete()
        
        logger.info("Indicateur supprimé: %s par %s", indicateur_libelle, request.user.username)
        
        return Response({
            'success': True,
            'message': 'Indicateur supprimé avec succès'
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la suppression de l'indicateur %s: %s", uuid, str(e), exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== INDICATEURS PAR OBJECTIF ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def objectives_indicateurs(request, objective_uuid):
    """Liste tous les indicateurs d'un objectif"""
    try:
        # Vérifier que l'objectif existe
        objective = Objectives.objects.get(uuid=objective_uuid)
        
        indicateurs = Indicateur.objects.filter(objective_id=objective).order_by('libelle')
        serializer = IndicateurSerializer(indicateurs, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': indicateurs.count(),
            'objective': {
                'uuid': str(objective.uuid),
                'number': objective.number,
                'libelle': objective.libelle
            }
        }, status=status.HTTP_200_OK)
        
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération des indicateurs de l'objectif %s: %s", objective_uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des indicateurs de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
