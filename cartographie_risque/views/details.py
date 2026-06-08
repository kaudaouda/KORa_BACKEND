from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import CDR, DetailsCDR, EvaluationRisque, PlanAction, SuiviAction
from ..serializers import (
    CDRSerializer, CDRCreateSerializer,
    DetailsCDRSerializer, DetailsCDRCreateSerializer, DetailsCDRUpdateSerializer,
    EvaluationRisqueSerializer, EvaluationRisqueCreateSerializer, EvaluationRisqueUpdateSerializer,
    PlanActionSerializer, PlanActionCreateSerializer, PlanActionUpdateSerializer,
    SuiviActionSerializer, SuiviActionCreateSerializer, SuiviActionUpdateSerializer,
)
from parametre.views import (
    log_cdr_creation,
    log_cdr_validation,
    get_client_ip,
)
from parametre.permissions import get_user_processus_list, user_has_access_to_processus
from permissions.services.permission_service import PermissionService
import logging

logger = logging.getLogger(__name__)

CDR_403_MESSAGE = "Opération non autorisée."
CDR_500_MESSAGE = "Une erreur interne est survenue."

from .utils import check_cdr_action_or_403, _get_next_num_amendement_for_cdr


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def details_cdr_by_cdr(request, cdr_uuid):
    """Récupérer tous les détails CDR pour une CDR spécifique"""
    try:
        cdr = CDR.objects.get(uuid=cdr_uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les détails CDR
        details = DetailsCDR.objects.filter(cdr=cdr).order_by('numero_cdr', 'created_at')
        
        serializer = DetailsCDRSerializer(details, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': details.count()
        }, status=status.HTTP_200_OK)
    except CDR.DoesNotExist:
        return Response({
            'error': 'CDR non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans details_cdr_by_cdr: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def details_cdr_create(request):
    """Créer un nouveau détail CDR"""
    try:
        logger.info("[details_cdr_create] Données reçues: %s", request.data)
        
        # Vérifier si la CDR est validée avant la création
        if 'cdr' in request.data:
            try:
                cdr = CDR.objects.get(uuid=request.data['cdr'])
                logger.info("[details_cdr_create] CDR trouvée: %s, validée: %s", cdr.uuid, cdr.is_validated)
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, cdr.processus.uuid):
                    return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                # ========== PERMISSION CRÉATION DÉTAIL CDR (Security by Design) ==========
                has_permission, error_response = check_cdr_action_or_403(
                    user=request.user,
                    processus_uuid=cdr.processus.uuid,
                    action='create_detail_cdr',
                )
                if not has_permission:
                    return error_response
                # ========== FIN PERMISSION ==========
                
                if cdr.is_validated:
                    return Response({
                        'error': 'Cette CDR est validée. Impossible de créer un nouveau détail.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except CDR.DoesNotExist:
                logger.error("[details_cdr_create] CDR non trouvée avec UUID: %s", request.data['cdr'])
                pass  # La validation du serializer gérera cette erreur
        
        serializer = DetailsCDRCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            detail = serializer.save()
            logger.info("[details_cdr_create] ✅ Détail créé avec succès: %s", detail.uuid)
            return Response(DetailsCDRSerializer(detail).data, status=status.HTTP_201_CREATED)
        
        logger.error("[details_cdr_create] Erreurs de validation: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création du détail CDR: %s", str(e))
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        
        # En mode développement, renvoyer plus de détails
        from django.conf import settings
        error_response = {'error': CDR_500_MESSAGE}
        if settings.DEBUG:
            error_response['details'] = str(e)
            error_response['traceback'] = error_traceback
        return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evaluations_by_detail_cdr(request, detail_cdr_uuid):
    """Récupérer toutes les évaluations pour un détail CDR spécifique"""
    try:
        detail = DetailsCDR.objects.select_related('cdr__processus').get(uuid=detail_cdr_uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, detail.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les évaluations
        evaluations = EvaluationRisque.objects.filter(
            details_cdr=detail
        ).select_related('frequence', 'gravite', 'criticite', 'risque').order_by('created_at')
        
        serializer = EvaluationRisqueSerializer(evaluations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except DetailsCDR.DoesNotExist:
        return Response({
            'error': 'Détail CDR non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans evaluations_by_detail_cdr: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def plans_action_by_detail_cdr(request, detail_cdr_uuid):
    """Récupérer tous les plans d'action pour un détail CDR spécifique"""
    try:
        detail = DetailsCDR.objects.select_related('cdr', 'cdr__processus').get(uuid=detail_cdr_uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, detail.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les plans d'action
        plans = PlanAction.objects.filter(
            details_cdr=detail
        ).select_related('responsable', 'details_cdr').order_by('delai_realisation', 'created_at')
        
        serializer = PlanActionSerializer(plans, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': plans.count()
        }, status=status.HTTP_200_OK)
    except DetailsCDR.DoesNotExist:
        return Response({
            'error': 'Détail CDR non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans plans_action_by_detail_cdr: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_action_detail(request, uuid):
    """Récupérer un suivi d'action par son UUID"""
    try:
        suivi = SuiviAction.objects.select_related(
            'plan_action__details_cdr__cdr__processus', 
            'element_preuve'
        ).prefetch_related('element_preuve__medias').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, suivi.plan_action.details_cdr.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        serializer = SuiviActionSerializer(suivi)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except SuiviAction.DoesNotExist:
        return Response({
            'error': 'Suivi d\'action non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans suivi_action_detail: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivis_by_plan_action(request, plan_action_uuid):
    """Récupérer tous les suivis pour un plan d'action spécifique"""
    try:
        plan = PlanAction.objects.select_related('details_cdr__cdr__processus').get(uuid=plan_action_uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, plan.details_cdr.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les suivis
        suivis = SuiviAction.objects.filter(
            plan_action=plan
        ).select_related('plan_action', 'element_preuve').order_by('-date_realisation', 'created_at')
        
        serializer = SuiviActionSerializer(suivis, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except PlanAction.DoesNotExist:
        return Response({
            'error': 'Plan d\'action non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans suivis_by_plan_action: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS DE MISE À JOUR ====================

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def details_cdr_update(request, uuid):
    """Mettre à jour un détail CDR"""
    try:
        detail = DetailsCDR.objects.select_related('cdr', 'cdr__processus').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, detail.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION MODIFICATION DÉTAIL CDR (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=detail.cdr.processus.uuid,
            action='update_detail_cdr',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========
        
        # Protection : empêcher la modification si la CDR est validée
        if detail.cdr.is_validated:
            return Response({
                'error': 'Cette CDR est validée. Les champs de détail ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DetailsCDRUpdateSerializer(detail, data=request.data, partial=True)
        if serializer.is_valid():
            detail = serializer.save()
            return Response(DetailsCDRSerializer(detail).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except DetailsCDR.DoesNotExist:
        return Response({
            'error': 'Détail CDR non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour du détail CDR: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def details_cdr_delete(request, uuid):
    """Supprimer un détail CDR avec toutes ses données associées (cascade)"""
    try:
        detail = DetailsCDR.objects.select_related('cdr', 'cdr__processus').get(uuid=uuid)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, detail.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION SUPPRESSION DÉTAIL CDR (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=detail.cdr.processus.uuid,
            action='delete_detail_cdr',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========

        # Supprimer le détail (cascade automatique vers évaluations, plans, suivis)
        detail.delete()

        return Response({
            'success': True,
            'message': 'Ligne supprimée avec succès'
        }, status=status.HTTP_200_OK)
    except DetailsCDR.DoesNotExist:
        return Response({
            'error': 'Détail CDR non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la suppression du détail CDR: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


