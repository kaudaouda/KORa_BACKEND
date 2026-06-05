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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cibles_list(request):
    """Liste toutes les cibles"""
    try:
        from parametre.models import Cible
        
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Filtrer les cibles pour ne montrer que celles des tableaux de bord accessibles
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les cibles sans filtre
            cibles = Cible.objects.all().order_by('indicateur_id', 'created_at')
        elif user_processus_uuids:
            cibles = Cible.objects.filter(
                indicateur_id__objective_id__tableau_bord__processus__uuid__in=user_processus_uuids
            ).order_by('indicateur_id', 'created_at')
        else:
            cibles = Cible.objects.none()  # Aucun processus, donc aucune cible
        # ========== FIN FILTRAGE ==========
        
        serializer = CibleSerializer(cibles, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': cibles.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération des cibles: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des cibles'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cibles_detail(request, uuid):
    """Détail d'une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        serializer = CibleSerializer(cible)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Cible.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cible non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération de la cible %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardCibleCreatePermission])
def cibles_create(request):
    """Créer une nouvelle cible"""
    try:
        from parametre.models import Cible
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        # SAUF si c'est une copie depuis l'année précédente (from_copy=True)
        is_copy = request.data.get('from_copy', False)
        indicateur_uuid = request.data.get('indicateur_id')
        if indicateur_uuid and not is_copy:
            try:
                indicateur = Indicateur.objects.get(uuid=indicateur_uuid)
                if indicateur.objective_id.tableau_bord:
                    tableau = indicateur.objective_id.tableau_bord
                    
                    # Security by Design : La vérification d'accès au processus est gérée par DashboardCibleCreatePermission
                    # via le décorateur @permission_classes
                    
                    if tableau.is_validated:
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer une cible : le tableau est déjà validé'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Vérifier que le tableau n'a pas d'amendements suivants
                    if tableau.has_amendements():
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer une cible : ce tableau a des amendements suivants'
                        }, status=status.HTTP_400_BAD_REQUEST)
            except Indicateur.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Indicateur non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CibleCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            cible = serializer.save()
            response_serializer = CibleSerializer(cible)
            
            logger.info("Cible créée/mise à jour: %s par %s", cible, request.user.username)
            
            return Response({
                'success': True,
                'message': 'Cible sauvegardée avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error("Erreur lors de la création de la cible: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardCibleUpdatePermission])
def cibles_update(request, uuid):
    """Mettre à jour une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        try:
            indicateur = Indicateur.objects.get(uuid=cible.indicateur_id.uuid)
            if indicateur.objective_id.tableau_bord:
                tableau = indicateur.objective_id.tableau_bord
                
                # Security by Design : La vérification d'accès au processus est gérée par DashboardCibleUpdatePermission
                # via le décorateur @permission_classes
                
                if tableau.is_validated:
                    return Response({
                        'success': False,
                        'error': 'Impossible de modifier la cible : le tableau est déjà validé'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Vérifier que le tableau n'a pas d'amendements suivants
                if tableau.has_amendements():
                    return Response({
                        'success': False,
                        'error': 'Impossible de modifier la cible : ce tableau a des amendements suivants'
                    }, status=status.HTTP_400_BAD_REQUEST)
        except Indicateur.DoesNotExist:
            pass  # Continuer avec la validation normale
        
        serializer = CibleUpdateSerializer(cible, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_cible = serializer.save()
            response_serializer = CibleSerializer(updated_cible)
            
            logger.info("Cible mise à jour: %s par %s", cible, request.user.username)
            
            return Response({
                'success': True,
                'message': 'Cible mise à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Cible.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cible non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la mise à jour de la cible %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardCibleDeletePermission])
def cibles_delete(request, uuid):
    """Supprimer une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardCibleDeletePermission
        # via le décorateur @permission_classes
        
        cible.delete()
        
        logger.info("Cible supprimée: %s par %s", cible, request.user.username)
        
        return Response({
            'success': True,
            'message': 'Cible supprimée avec succès'
        }, status=status.HTTP_200_OK)
        
    except Cible.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cible non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la suppression de la cible %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cibles_by_indicateur(request, indicateur_uuid):
    """Récupérer les cibles d'un indicateur spécifique"""
    try:
        from parametre.models import Cible
        from .models import Indicateur
        
        # Récupérer l'indicateur
        indicateur = Indicateur.objects.get(uuid=indicateur_uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par les permissions DRF
        # (cet endpoint est utilisé pour la lecture, pas de permission spécifique requise car c'est un GET)
        
        # Récupérer la cible liée à l'indicateur (une seule)
        cible = Cible.objects.filter(indicateur_id=indicateur).first()
        serializer = CibleSerializer(cible) if cible else None
        
        return Response({
            'success': True,
            'data': serializer.data if serializer else None,
            'count': 1 if cible else 0,
            'indicateur': {
                'uuid': str(indicateur.uuid),
                'libelle': indicateur.libelle,
                'frequence_nom': indicateur.frequence_id.nom
            }
        }, status=status.HTTP_200_OK)
        
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération des cibles de l'indicateur %s: %s", indicateur_uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des cibles de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
