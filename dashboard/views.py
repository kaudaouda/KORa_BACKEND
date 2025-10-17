"""
Vues API pour l'application Dashboard
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.utils import timezone
from .models import Objectives, Indicateur
from .serializers import (
    ObjectivesSerializer, ObjectivesCreateSerializer, ObjectivesUpdateSerializer,
    IndicateurSerializer, IndicateurCreateSerializer, IndicateurUpdateSerializer,
    CibleSerializer, CibleCreateSerializer, CibleUpdateSerializer,
    PeriodiciteSerializer, PeriodiciteCreateSerializer, PeriodiciteUpdateSerializer
)
import logging

logger = logging.getLogger(__name__)


# ==================== OBJECTIFS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def objectives_list(request):
    """Liste tous les objectifs"""
    try:
        objectives = Objectives.objects.all().order_by('number')
        serializer = ObjectivesSerializer(objectives, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': objectives.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des objectifs: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération de l'objectif {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def objectives_create(request):
    """Créer un nouvel objectif"""
    try:
        serializer = ObjectivesCreateSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            objective = serializer.save()
            
            # Retourner l'objectif créé avec tous ses détails
            response_serializer = ObjectivesSerializer(objective)
            
            logger.info(f"Objectif créé: {objective.number} par {request.user.username}")
            
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
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'objectif: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def objectives_update(request, uuid):
    """Mettre à jour un objectif"""
    try:
        objective = Objectives.objects.get(uuid=uuid)
        serializer = ObjectivesUpdateSerializer(objective, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_objective = serializer.save()
            
            # Retourner l'objectif mis à jour avec tous ses détails
            response_serializer = ObjectivesSerializer(updated_objective)
            
            logger.info(f"Objectif mis à jour: {objective.number} par {request.user.username}")
            
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
            
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'objectif {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def objectives_delete(request, uuid):
    """Supprimer un objectif"""
    try:
        objective = Objectives.objects.get(uuid=uuid)
        objective_number = objective.number
        
        objective.delete()
        
        logger.info(f"Objectif supprimé: {objective_number} par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Objectif supprimé avec succès'
        }, status=status.HTTP_200_OK)
        
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'objectif {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATISTIQUES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Statistiques du tableau de bord"""
    try:
        # Compter les objectifs
        total_objectives = Objectives.objects.count()
        
        # Compter les fréquences
        from parametre.models import Frequence
        total_frequences = Frequence.objects.count()
        
        # Compter les indicateurs
        total_indicateurs = Indicateur.objects.count()
        
        # Objectifs créés aujourd'hui
        today = timezone.now().date()
        objectives_today = Objectives.objects.filter(created_at__date=today).count()
        
        # Objectifs créés cette semaine
        from datetime import timedelta
        week_ago = today - timedelta(days=7)
        objectives_this_week = Objectives.objects.filter(created_at__date__gte=week_ago).count()
        
        # Objectifs créés ce mois
        month_ago = today - timedelta(days=30)
        objectives_this_month = Objectives.objects.filter(created_at__date__gte=month_ago).count()
        
        # Calculer les pourcentages de cibles atteintes et non atteintes
        from parametre.models import Cible, Periodicite
        from django.db.models import Q, Count, Case, When, DecimalField, F
        
        # Récupérer toutes les cibles avec leurs indicateurs
        cibles_with_periodicites = Cible.objects.select_related('indicateur_id').prefetch_related(
            'indicateur_id__periodicites'
        ).all()
        
        total_cibles = cibles_with_periodicites.count()
        cibles_atteintes = 0
        cibles_non_atteintes = 0
        
        # Pour chaque cible, vérifier si elle est atteinte en comparant avec les périodicités
        for cible in cibles_with_periodicites:
            # Récupérer la dernière périodicité pour cet indicateur
            derniere_periodicite = Periodicite.objects.filter(
                indicateur_id=cible.indicateur_id
            ).order_by('-created_at').first()
            
            if derniere_periodicite and derniere_periodicite.taux is not None:
                # Utiliser la méthode is_objectif_atteint pour vérifier si la cible est atteinte
                if cible.is_objectif_atteint(float(derniere_periodicite.taux)):
                    cibles_atteintes += 1
                else:
                    cibles_non_atteintes += 1
        
        # Calculer les pourcentages
        pourcentage_atteintes = (cibles_atteintes / total_cibles * 100) if total_cibles > 0 else 0
        pourcentage_non_atteintes = (cibles_non_atteintes / total_cibles * 100) if total_cibles > 0 else 0
        
        stats = {
            'total_objectives': total_objectives,
            'total_frequences': total_frequences,
            'total_indicateurs': total_indicateurs,
            'objectives_today': objectives_today,
            'objectives_this_week': objectives_this_week,
            'objectives_this_month': objectives_this_month,
            'total_cibles': total_cibles,
            'cibles_atteintes': cibles_atteintes,
            'cibles_non_atteintes': cibles_non_atteintes,
            'pourcentage_atteintes': round(pourcentage_atteintes, 2),
            'pourcentage_non_atteintes': round(pourcentage_non_atteintes, 2),
        }
        
        return Response({
            'success': True,
            'data': stats
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des statistiques'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== INDICATEURS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicateurs_list(request):
    """Liste tous les indicateurs"""
    try:
        indicateurs = Indicateur.objects.all().order_by('objective_id', 'libelle')
        serializer = IndicateurSerializer(indicateurs, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': indicateurs.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des indicateurs: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération de l'indicateur {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def indicateurs_create(request):
    """Créer un nouvel indicateur"""
    try:
        serializer = IndicateurCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            indicateur = serializer.save()
            
            # Retourner l'indicateur créé avec tous ses détails
            response_serializer = IndicateurSerializer(indicateur)
            
            logger.info(f"Indicateur créé: {indicateur.libelle} par {request.user.username}")
            
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
        logger.error(f"Erreur lors de la création de l'indicateur: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def indicateurs_update(request, uuid):
    """Mettre à jour un indicateur"""
    try:
        indicateur = Indicateur.objects.get(uuid=uuid)
        serializer = IndicateurUpdateSerializer(indicateur, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_indicateur = serializer.save()
            
            # Retourner l'indicateur mis à jour avec tous ses détails
            response_serializer = IndicateurSerializer(updated_indicateur)
            
            logger.info(f"Indicateur mis à jour: {indicateur.libelle} par {request.user.username}")
            
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
        logger.error(f"Erreur lors de la mise à jour de l'indicateur {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def indicateurs_delete(request, uuid):
    """Supprimer un indicateur"""
    try:
        indicateur = Indicateur.objects.get(uuid=uuid)
        indicateur_libelle = indicateur.libelle
        
        indicateur.delete()
        
        logger.info(f"Indicateur supprimé: {indicateur_libelle} par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Indicateur supprimé avec succès'
        }, status=status.HTTP_200_OK)
        
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'indicateur {uuid}: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération des indicateurs de l'objectif {objective_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des indicateurs de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== CIBLES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cibles_list(request):
    """Liste toutes les cibles"""
    try:
        from parametre.models import Cible
        cibles = Cible.objects.all().order_by('indicateur_id', 'created_at')
        serializer = CibleSerializer(cibles, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': cibles.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des cibles: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération de la cible {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cibles_create(request):
    """Créer une nouvelle cible"""
    try:
        from parametre.models import Cible
        serializer = CibleCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            cible = serializer.save()
            response_serializer = CibleSerializer(cible)
            
            logger.info(f"Cible créée/mise à jour: {cible} par {request.user.username}")
            
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
        logger.error(f"Erreur lors de la création de la cible: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def cibles_update(request, uuid):
    """Mettre à jour une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        serializer = CibleUpdateSerializer(cible, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_cible = serializer.save()
            response_serializer = CibleSerializer(updated_cible)
            
            logger.info(f"Cible mise à jour: {cible} par {request.user.username}")
            
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
        logger.error(f"Erreur lors de la mise à jour de la cible {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cibles_delete(request, uuid):
    """Supprimer une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        cible.delete()
        
        logger.info(f"Cible supprimée: {cible} par {request.user.username}")
        
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
        logger.error(f"Erreur lors de la suppression de la cible {uuid}: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération des cibles de l'indicateur {indicateur_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des cibles de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== PERIODICITES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_list(request):
    """Liste toutes les périodicités"""
    try:
        from parametre.models import Periodicite
        periodicites = Periodicite.objects.all().order_by('indicateur_id', 'periode')
        serializer = PeriodiciteSerializer(periodicites, many=True)

        return Response({
            'success': True,
            'data': serializer.data,
            'count': periodicites.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des périodicités: {str(e)}")
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
        logger.error(f"Erreur lors de la récupération de la périodicité {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def periodicites_create(request):
    """Créer une nouvelle périodicité"""
    try:
        serializer = PeriodiciteCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            periodicite = serializer.save()
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
        logger.error(f"Erreur lors de la création de la périodicité: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def periodicites_update(request, uuid):
    """Mettre à jour une périodicité"""
    try:
        from parametre.models import Periodicite
        periodicite = Periodicite.objects.get(uuid=uuid)
        serializer = PeriodiciteUpdateSerializer(periodicite, data=request.data)
        
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
        logger.error(f"Erreur lors de la mise à jour de la périodicité {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def periodicites_delete(request, uuid):
    """Supprimer une périodicité"""
    try:
        from parametre.models import Periodicite
        periodicite = Periodicite.objects.get(uuid=uuid)
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
        logger.error(f"Erreur lors de la suppression de la périodicité {uuid}: {str(e)}")
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

        # Récupérer les périodicités liées à l'indicateur
        periodicites = Periodicite.objects.filter(indicateur_id=indicateur).order_by('periode')
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
        logger.error(f"Erreur lors de la récupération des périodicités de l'indicateur {indicateur_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des périodicités de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)