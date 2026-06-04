from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from ..models import ActivitePeriodique, DetailsAP, SuivisAP
from permissions.permissions import (
    ActivitePeriodiqueListPermission,
    ActivitePeriodiqueCreatePermission,
    ActivitePeriodiqueUpdatePermission,
    ActivitePeriodiqueDeletePermission,
    ActivitePeriodiqueValidatePermission,
    ActivitePeriodiqueUnvalidatePermission,
    ActivitePeriodiqueReadPermission,
    ActivitePeriodiqueDetailPermission,
    ActivitePeriodiqueAmendementCreatePermission,
    ActivitePeriodiqueDetailCreatePermission,
    ActivitePeriodiqueDetailUpdatePermission,
    ActivitePeriodiqueDetailDeletePermission,
    ActivitePeriodiqueSuiviCreatePermission,
    ActivitePeriodiqueSuiviUpdatePermission,
    ActivitePeriodiqueSuiviDeletePermission,
)
from ..serializers import (
    ActivitePeriodiqueSerializer,
    ActivitePeriodiqueCompletSerializer,
    DetailsAPSerializer,
    DetailsAPCreateSerializer,
    SuivisAPSerializer,
    SuivisAPCreateSerializer,
    MediaLivrableSerializer,
    MediaLivrableCreateSerializer,
    MediaLivrableUpdateSerializer,
)
from parametre.models import Media
try:
    from parametre.models import MediaLivrable
except (ImportError, AttributeError):
    MediaLivrable = None
from parametre.models import Processus, Annee
from parametre.views import (
    log_activite_periodique_creation,
    log_activite_periodique_update,
    log_activite_periodique_validation,
    get_client_ip,
)
from parametre.permissions import check_permission_or_403, get_user_processus_list, user_has_access_to_processus
import logging

logger = logging.getLogger(__name__)

from .utils import _has_amendements_following, _get_next_num_amendement_for_ap

@permission_classes([IsAuthenticated, ActivitePeriodiqueListPermission])
def details_ap_list(request):
    """Liste tous les détails AP de l'utilisateur connecté"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        if not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun détail AP trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)

        details = DetailsAP.objects.filter(
            activite_periodique__processus__uuid__in=user_processus_uuids
        ).select_related(
            'activite_periodique', 'responsabilite_direction', 'responsabilite_sous_direction', 'responsabilite_service'
        ).prefetch_related('responsables_directions', 'responsables_sous_directions', 'responsables_services')
        # ========== FIN FILTRAGE ==========
        
        serializer = DetailsAPSerializer(details, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': details.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_list: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des détails AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueReadPermission])
def details_ap_by_activite_periodique(request, ap_uuid):
    """Récupérer tous les détails AP pour une Activité Périodique spécifique"""
    try:
        ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # La permission ActivitePeriodiqueReadPermission vérifie déjà l'accès au processus
        # Mais on garde cette vérification pour cohérence
        if not user_has_access_to_processus(request.user, ap.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à cette Activité Périodique. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les détails AP
        details = DetailsAP.objects.filter(activite_periodique=ap).select_related(
            'activite_periodique', 'responsabilite_direction', 'responsabilite_sous_direction', 'responsabilite_service', 'frequence'
        ).prefetch_related('responsables_directions', 'responsables_sous_directions', 'responsables_services', 'suivis__mois', 'suivis__etat_mise_en_oeuvre')
        
        serializer = DetailsAPSerializer(details, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': details.count()
        }, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_by_activite_periodique: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des détails AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueDetailCreatePermission])
def details_ap_create(request):
    """Créer un nouveau détail AP"""
    try:
        data = request.data.copy()
        ap_uuid = data.get('activite_periodique')
        
        # Vérifier que l'AP existe
        try:
            ap = ActivitePeriodique.objects.get(uuid=ap_uuid)
        except ActivitePeriodique.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Activité Périodique non trouvée'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueDetailCreatePermission vérifie déjà
        # la permission create_detail_activite_periodique, donc pas besoin de vérifier ici
        if not user_has_access_to_processus(request.user, ap.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à cette Activité Périodique. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP n'est pas validée
        if ap.is_validated:
            return Response({
                'error': 'Impossible d\'ajouter un détail à une Activité Périodique validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(ap):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DetailsAPCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            detail = serializer.save()
            # Utiliser DetailsAPSerializer pour la réponse (avec tous les champs read_only)
            response_serializer = DetailsAPSerializer(detail)
            logger.info(f"[details_ap_create] ✅ Détail créé avec succès: {detail.uuid}, numero_ap: {detail.numero_ap}")
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_create: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la création du détail AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueDetailUpdatePermission])
def details_ap_update(request, uuid):
    """Mettre à jour un détail AP"""
    try:
        detail = DetailsAP.objects.select_related('activite_periodique', 'activite_periodique__processus', 'activite_periodique__annee').get(
            uuid=uuid
        )
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueDetailUpdatePermission vérifie déjà
        # la permission update_detail_activite_periodique, donc pas besoin de vérifier ici
        if not user_has_access_to_processus(request.user, detail.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce détail. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP n'est pas validée
        if detail.activite_periodique.is_validated:
            return Response({
                'error': 'Impossible de modifier un détail d\'une Activité Périodique validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(detail.activite_periodique):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DetailsAPSerializer(detail, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except DetailsAP.DoesNotExist:
        return Response({
            'error': 'Détail AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_update: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la mise à jour du détail AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueDetailDeletePermission])
def details_ap_delete(request, uuid):
    """Supprimer un détail AP"""
    try:
        detail = DetailsAP.objects.select_related('activite_periodique', 'activite_periodique__processus', 'activite_periodique__annee').get(
            uuid=uuid
        )
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, detail.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce détail. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # ========== VÉRIFICATION PERMISSION ÉCRIRE (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueDetailDeletePermission vérifie déjà
        # la permission delete_detail_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION ==========
        
        from parametre.permissions import is_super_admin, can_manage_users, is_supervisor_smi
        is_super = can_manage_users(request.user) or is_super_admin(request.user) or is_supervisor_smi(request.user)
        
        # Vérifier que l'AP n'est pas validée (sauf pour super admin)
        if detail.activite_periodique.is_validated and not is_super:
            return Response({
                'error': 'Impossible de supprimer un détail d\'une Activité Périodique validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (sauf pour super admin)
        if _has_amendements_following(detail.activite_periodique) and not is_super:
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        detail.delete()
        return Response({
            'success': True,
            'message': 'Détail AP supprimé avec succès'
        }, status=status.HTTP_200_OK)
    except DetailsAP.DoesNotExist:
        return Response({
            'error': 'Détail AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_delete: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la suppression du détail AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS API SUIVIS AP ====================

