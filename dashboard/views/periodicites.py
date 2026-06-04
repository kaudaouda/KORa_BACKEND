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
def periodicites_list(request):
    """Liste toutes les périodicités"""
    try:
        from parametre.models import Periodicite
        import decimal
        
        # Récupérer les périodicités avec gestion d'erreur pour les données corrompues
        periodicites_data = []
        periodicites = Periodicite.objects.all().select_related('preuve').prefetch_related('preuve__medias').order_by('indicateur_id', 'periode')
        
        # Utiliser le serializer pour inclure toutes les données de preuve
        from .serializers import PeriodiciteSerializer
        
        for periodicite in periodicites:
            try:
                # Utiliser le serializer pour avoir toutes les données de preuve
                serializer = PeriodiciteSerializer(periodicite)
                periodicite_data = serializer.data
                # Convertir l'indicateur_id en string si c'est un objet
                if 'indicateur_id' in periodicite_data and not isinstance(periodicite_data['indicateur_id'], str):
                    periodicite_data['indicateur_id'] = str(periodicite_data['indicateur_id'])
                periodicites_data.append(periodicite_data)
            except (ValueError, TypeError, decimal.InvalidOperation) as e:
                logger.warning("Périodicité %s ignorée à cause de données corrompues: %s", periodicite.uuid, str(e))
                # Utiliser le serializer même pour les données corrompues pour avoir les preuves
                try:
                    serializer = PeriodiciteSerializer(periodicite)
                    periodicite_data = serializer.data
                    # Forcer les valeurs par défaut pour les champs corrompus
                    periodicite_data['a_realiser'] = 0.0
                    periodicite_data['realiser'] = 0.0
                    periodicite_data['taux'] = 0.0
                    if 'indicateur_id' in periodicite_data and not isinstance(periodicite_data['indicateur_id'], str):
                        periodicite_data['indicateur_id'] = str(periodicite_data['indicateur_id'])
                    periodicites_data.append(periodicite_data)
                except Exception as serializer_error:
                    logger.error("Erreur lors de la sérialisation de la périodicité %s: %s", periodicite.uuid, str(serializer_error))
                    # Fallback : créer un dictionnaire minimal avec les champs de preuve
                    periodicite_data = {
                        'uuid': str(periodicite.uuid),
                        'indicateur_id': str(periodicite.indicateur_id.uuid) if periodicite.indicateur_id else None,
                        'indicateur_libelle': periodicite.indicateur_id.libelle if periodicite.indicateur_id else 'Indicateur supprimé',
                        'periode': periodicite.periode,
                        'periode_display': periodicite.get_periode_display(),
                        'a_realiser': 0.0,
                        'realiser': 0.0,
                        'taux': 0.0,
                        'preuve': str(periodicite.preuve.uuid) if periodicite.preuve else None,
                        'preuve_uuid': str(periodicite.preuve.uuid) if periodicite.preuve else None,
                        'preuve_titre': periodicite.preuve.titre if periodicite.preuve else None,
                        'preuve_media_url': None,
                        'preuve_media_urls': [],
                        'preuve_medias': [],
                        'created_at': periodicite.created_at,
                        'updated_at': periodicite.updated_at
                    }
                    periodicites_data.append(periodicite_data)

        return Response({
            'success': True,
            'data': periodicites_data,
            'count': len(periodicites_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération des périodicités: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des périodicités'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_detail(request, uuid):
    """Détail d'une périodicité"""
    try:
        from parametre.models import Periodicite
        periodicite = Periodicite.objects.get(uuid=uuid)
        serializer = PeriodiciteSerializer(periodicite)

        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Periodicite.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Périodicité non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la récupération de la périodicité %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardPeriodiciteCreatePermission])
def periodicites_create(request):
    """Créer une nouvelle périodicité"""
    try:
        from parametre.models import Periodicite
        # Vérifier que le tableau est validé et n'a pas d'amendements avant de permettre la création de périodicités
        # SAUF si c'est une copie depuis l'année précédente (from_copy=True)
        is_copy = request.data.get('from_copy', False)
        indicateur_uuid = request.data.get('indicateur_id')
        if indicateur_uuid and not is_copy:
            try:
                indicateur = Indicateur.objects.get(uuid=indicateur_uuid)
                tableau = indicateur.objective_id.tableau_bord
                
                if not tableau.is_validated:
                    return Response({
                        'success': False,
                        'error': 'Vous devez d\'abord valider le tableau avant de saisir les données trimestrielles'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Vérifier que le tableau n'a pas d'amendements suivants
                if tableau.has_amendements():
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer une périodicité : ce tableau a des amendements suivants'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Indicateur.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Indicateur non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = PeriodiciteCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            periodicite = serializer.save()
            # Optimiser la requête pour inclure la preuve et ses médias
            periodicite = Periodicite.objects.select_related('preuve').prefetch_related('preuve__medias').get(uuid=periodicite.uuid)
            response_serializer = PeriodiciteSerializer(periodicite)
            
            return Response({
                'success': True,
                'message': 'Périodicité créée avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error("Erreur lors de la création de la périodicité: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardPeriodiciteUpdatePermission])
def periodicites_update(request, uuid):
    """Mettre à jour une périodicité"""
    try:
        from parametre.models import Periodicite
        # Optimiser la requête pour inclure la preuve et ses médias
        periodicite = Periodicite.objects.select_related('preuve').prefetch_related('preuve__medias').get(uuid=uuid)
        
        # Vérifier que le tableau est validé et n'a pas d'amendements avant de permettre la modification de périodicités
        try:
            indicateur = periodicite.indicateur_id
            tableau = indicateur.objective_id.tableau_bord
            
            if not tableau.is_validated:
                return Response({
                    'success': False,
                    'error': 'Vous devez d\'abord valider le tableau avant de modifier les données trimestrielles'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier que le tableau n'a pas d'amendements suivants
            if tableau.has_amendements():
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier la périodicité : ce tableau a des amendements suivants'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception:
            pass  # En cas d'erreur, continuer avec la validation normale
        
        serializer = PeriodiciteUpdateSerializer(periodicite, data=request.data, partial=True)
        
        if serializer.is_valid():
            periodicite = serializer.save()
            response_serializer = PeriodiciteSerializer(periodicite)
            
            return Response({
                'success': True,
                'message': 'Périodicité mise à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Periodicite.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Périodicité non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour de la périodicité %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardPeriodiciteDeletePermission])
def periodicites_delete(request, uuid):
    """Supprimer une périodicité"""
    try:
        from parametre.models import Periodicite
        periodicite = Periodicite.objects.get(uuid=uuid)
        
        # Note: La vérification des permissions est maintenant gérée par DashboardPeriodiciteDeletePermission
        # via le décorateur @permission_classes
        
        periodicite.delete()
        
        return Response({
            'success': True,
            'message': 'Périodicité supprimée avec succès'
        }, status=status.HTTP_200_OK)
        
    except Periodicite.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Périodicité non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la suppression de la périodicité %s: %s", uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_by_indicateur(request, indicateur_uuid):
    """Récupérer les périodicités d'un indicateur spécifique"""
    try:
        from parametre.models import Periodicite
        from .models import Indicateur

        # Récupérer l'indicateur
        indicateur = Indicateur.objects.get(uuid=indicateur_uuid)

        # Récupérer les périodicités liées à l'indicateur avec optimisation pour les preuves
        periodicites = Periodicite.objects.filter(indicateur_id=indicateur).select_related('preuve').prefetch_related('preuve__medias').order_by('periode')
        serializer = PeriodiciteSerializer(periodicites, many=True)

        return Response({
            'success': True,
            'data': serializer.data,
            'count': periodicites.count(),
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
        logger.error("Erreur lors de la récupération des périodicités de l'indicateur %s: %s", indicateur_uuid, str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des périodicités de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
