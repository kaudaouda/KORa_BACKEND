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

def observations_list(request):
    """Liste toutes les observations"""
    try:
        observations = Observation.objects.select_related(
            'indicateur_id', 'indicateur_id__objective_id', 'cree_par'
        ).all().order_by('indicateur_id__objective_id', 'created_at')
        serializer = ObservationSerializer(observations, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': observations.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des observations: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des observations'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardObservationCreatePermission])
def observations_create(request):
    """Créer une nouvelle observation"""
    try:
        # Ajouter l'utilisateur connecté comme créateur
        data = request.data.copy()
        data['cree_par'] = request.user.id
        
        # Vérifier que l'indicateur existe et récupérer le tableau
        indicateur_id = data.get('indicateur_id')
        if not indicateur_id:
            return Response({
                'success': False,
                'error': 'Indicateur requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            indicateur = Indicateur.objects.get(uuid=indicateur_id)
            # Sécuriser la chaîne de relations (peut être None selon les données)
            objective = getattr(indicateur, 'objective_id', None) or getattr(indicateur, 'objective', None)
            if objective is None:
                return Response({
                    'success': False,
                    'error': "Impossible de créer l'observation : l'indicateur n'est rattaché à aucun objectif"
                }, status=status.HTTP_400_BAD_REQUEST)

            tableau = getattr(objective, 'tableau_bord', None)
            if tableau is None:
                return Response({
                    'success': False,
                    'error': "Impossible de créer l'observation : l'objectif n'est rattaché à aucun tableau"
                }, status=status.HTTP_400_BAD_REQUEST)
        except Indicateur.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Indicateur non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)

        # Security by Design : La vérification d'accès au processus est gérée par DashboardObservationCreatePermission
        # via le décorateur @permission_classes

        # Vérifier si le tableau est validé
        if not tableau.is_validated:
            return Response({
                'success': False,
                'error': 'Vous devez d\'abord valider le tableau pour ajouter des observations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ObservationCreateSerializer(data=data)
        
        if serializer.is_valid():
            observation = serializer.save()
            response_serializer = ObservationSerializer(observation)
            
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Observation créée avec succès'
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
        import traceback
        from django.conf import settings
        logger.error(
            f"Erreur lors de la création de l'observation: {str(e)}\n{traceback.format_exc()}",
            exc_info=True
        )
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'observation',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def observations_detail(request, uuid):
    """Détail d'une observation"""
    try:
        observation = Observation.objects.select_related(
            'indicateur_id', 'indicateur_id__objective_id', 'cree_par'
        ).get(uuid=uuid)
        serializer = ObservationSerializer(observation)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Observation non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'observation {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'observation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardObservationUpdatePermission])
def observations_update(request, uuid):
    """Mettre à jour une observation"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObservationUpdatePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'observation depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        observation = Observation.objects.select_related(
            'indicateur_id__objective_id__tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Récupérer le tableau via l'indicateur (correction : utiliser indicateur_id et objective_id)
        tableau = observation.indicateur_id.objective_id.tableau_bord

        # Security by Design : La vérification d'accès au processus est gérée par DashboardObservationUpdatePermission
        # via le décorateur @permission_classes
        
        # Vérifier si le tableau est validé
        if not tableau.is_validated:
            return Response({
                'success': False,
                'error': 'Vous devez d\'abord valider le tableau pour modifier les observations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ObservationUpdateSerializer(observation, data=request.data, partial=True)
        
        if serializer.is_valid():
            observation = serializer.save()
            response_serializer = ObservationSerializer(observation)
            
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Observation mise à jour avec succès'
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
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Observation non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'observation {uuid}: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'observation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardObservationDeletePermission])
def observations_delete(request, uuid):
    """Supprimer une observation"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObservationDeletePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'observation depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        observation = Observation.objects.select_related(
            'indicateur_id__objective_id__tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObservationDeletePermission
        # via le décorateur @permission_classes
        
        observation.delete()
        
        logger.info(f"Observation supprimée: {uuid} par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Observation supprimée avec succès'
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Observation non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'observation {uuid}: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'observation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def observations_by_indicateur(request, indicateur_uuid):
    """Récupérer l'observation d'un indicateur"""
    try:
        observation = Observation.objects.select_related(
            'indicateur_id', 'indicateur_id__objective_id', 'cree_par'
        ).get(indicateur_id=indicateur_uuid)
        serializer = ObservationSerializer(observation)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Aucune observation trouvée pour cet indicateur'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'observation de l'indicateur {indicateur_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'observation de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_tableau_bord_previous_year(request):
    """
    Récupérer le dernier Tableau de Bord de l'année précédente pour un processus donné.
    Retourne le tableau avec le num_amendement le plus élevé.

    Query params:
    - annee: année actuelle (nombre entier, ex: 2025)
    - processus: UUID du processus
    """
    try:
        annee = request.query_params.get('annee')
        processus_uuid = request.query_params.get('processus')

        if not annee or not processus_uuid:
            return Response({
                'error': 'Les paramètres annee et processus sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            annee = int(annee)
        except (ValueError, TypeError):
            return Response({
                'error': 'Le paramètre annee doit être un nombre entier'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Calculer l'année précédente
        annee_precedente = annee - 1

        logger.info(f"[get_last_tableau_bord_previous_year] Recherche du dernier Tableau de Bord pour processus={processus_uuid}, année={annee_precedente}")

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'error': 'Vous n\'avez pas accès à ce processus. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Récupérer le tableau avec le num_amendement le plus élevé pour l'année précédente
        tableau = TableauBord.objects.filter(
            annee=annee_precedente,
            processus__uuid=processus_uuid,
        ).select_related('processus', 'cree_par', 'valide_par').order_by('-num_amendement').first()

        if tableau:
            logger.info(f"[get_last_tableau_bord_previous_year] Tableau de Bord trouvé: {tableau.uuid} (num_amendement={tableau.num_amendement})")
            serializer = TableauBordSerializer(tableau)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun Tableau de Bord trouvé pour l'année précédente
        logger.info(f"[get_last_tableau_bord_previous_year] Aucun Tableau de Bord trouvé pour l'année {annee_precedente}")
        return Response({
            'message': f'Aucun Tableau de Bord trouvé pour l\'année {annee_precedente}',
            'found': False
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier Tableau de Bord de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération du Tableau de Bord',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
