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

def evaluation_risque_create(request):
    """Créer une nouvelle évaluation de risque"""
    try:
        logger.info("[evaluation_risque_create] Données reçues: %s", request.data)

        # Vérifier l'accès au processus et la permission "ecrire"
        if 'details_cdr' in request.data:
            try:
                detail_cdr = DetailsCDR.objects.select_related('cdr__processus').get(uuid=request.data['details_cdr'])
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, detail_cdr.cdr.processus.uuid):
                    return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                # ========== PERMISSION CRÉATION ÉVALUATION (Security by Design) ==========
                has_permission, error_response = check_cdr_action_or_403(
                    user=request.user,
                    processus_uuid=detail_cdr.cdr.processus.uuid,
                    action='create_evaluation_risque',
                )
                if not has_permission:
                    return error_response
                # ========== FIN PERMISSION ==========
            except DetailsCDR.DoesNotExist:
                pass  # La validation du serializer gérera cette erreur

        # Ajouter la version par défaut si non fournie
        if 'version_evaluation' not in request.data or not request.data['version_evaluation']:
            from parametre.models import VersionEvaluationCDR
            try:
                # Récupérer la première version active (la plus ancienne = évaluation initiale)
                version_initiale = VersionEvaluationCDR.objects.filter(is_active=True).order_by('created_at').first()
                if not version_initiale:
                    logger.error("[evaluation_risque_create] Aucune version d'évaluation active trouvée")
                    return Response({
                        'error': 'Aucune version d\'évaluation disponible. Veuillez initialiser les versions.'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                request.data['version_evaluation'] = str(version_initiale.uuid)
                logger.info("[evaluation_risque_create] Version par défaut assignée: %s", version_initiale.nom)
            except Exception as e:
                logger.error("[evaluation_risque_create] Erreur récupération version: %s", str(e))
                return Response({
                    'error': 'Erreur lors de la récupération de la version d\'évaluation.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = EvaluationRisqueCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            evaluation = serializer.save()
            logger.info("[evaluation_risque_create] ✅ Évaluation créée avec succès: %s", evaluation.uuid)
            return Response(EvaluationRisqueSerializer(evaluation).data, status=status.HTTP_201_CREATED)

        logger.error("[evaluation_risque_create] Erreurs de validation: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création de l'évaluation: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer l\'évaluation de risque'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def evaluation_risque_update(request, uuid):
    """Mettre à jour une évaluation de risque"""
    try:
        evaluation = EvaluationRisque.objects.select_related('details_cdr__cdr__processus').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, evaluation.details_cdr.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION MODIFICATION ÉVALUATION (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=evaluation.details_cdr.cdr.processus.uuid,
            action='update_evaluation_risque',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========
        
        # Protection : empêcher la modification si un amendement supérieur existe
        current_cdr = evaluation.details_cdr.cdr
        current_type_code = getattr(current_cdr, 'num_amendement', None)

        # Vérifier si un amendement supérieur existe
        has_superior_amendment = False
        if current_cdr.num_amendement < 2:
            superior_num = current_cdr.num_amendement + 1
            has_superior_amendment = CDR.objects.filter(
                cree_par=request.user,
                annee=current_cdr.annee,
                processus=current_cdr.processus,
                num_amendement=superior_num
            ).exists()

        if has_superior_amendment:
            return Response({
                'error': 'Un amendement supérieur existe. Les évaluations de ce tableau ne peuvent plus être modifiées.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Protection : empêcher la modification de l'évaluation initiale si la CDR est validée
        # Les réévaluations peuvent être modifiées après validation
        if current_cdr.is_validated:
            is_initial = False
            if evaluation.version_evaluation:
                version_code = getattr(evaluation.version_evaluation, 'code', None)
                version_nom = getattr(evaluation.version_evaluation, 'nom', '')
                is_initial = version_code == 'INITIAL' or 'initial' in version_nom.lower()
            else:
                is_initial = True

            if is_initial:
                return Response({
                    'error': 'Cette CDR est validée. L\'évaluation initiale ne peut plus être modifiée.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = EvaluationRisqueUpdateSerializer(evaluation, data=request.data, partial=True)
        if serializer.is_valid():
            evaluation = serializer.save()
            return Response(EvaluationRisqueSerializer(evaluation).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except EvaluationRisque.DoesNotExist:
        return Response({
            'error': 'Évaluation de risque non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour de l'évaluation: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de mettre à jour l\'évaluation de risque'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def plan_action_create(request):
    """Créer un nouveau plan d'action"""
    try:
        logger.info("[plan_action_create] Données reçues: %s", request.data)
        
        # Vérifier l'accès au processus et la permission "ecrire"
        if 'details_cdr' in request.data:
            try:
                detail_cdr = DetailsCDR.objects.select_related('cdr__processus').get(uuid=request.data['details_cdr'])
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, detail_cdr.cdr.processus.uuid):
                    return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                # ========== PERMISSION CRÉATION PLAN D'ACTION (Security by Design) ==========
                has_permission, error_response = check_cdr_action_or_403(
                    user=request.user,
                    processus_uuid=detail_cdr.cdr.processus.uuid,
                    action='create_plan_action',
                )
                if not has_permission:
                    return error_response
                # ========== FIN PERMISSION ==========
            except DetailsCDR.DoesNotExist:
                pass  # La validation du serializer gérera cette erreur
        
        serializer = PlanActionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            plan = serializer.save()
            logger.info("[plan_action_create] ✅ Plan d'action créé avec succès: %s", plan.uuid)
            return Response(PlanActionSerializer(plan).data, status=status.HTTP_201_CREATED)
        
        logger.error("[plan_action_create] Erreurs de validation: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création du plan d'action: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def plan_action_update(request, uuid):
    """Mettre à jour un plan d'action"""
    try:
        plan = PlanAction.objects.select_related('details_cdr__cdr__processus').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, plan.details_cdr.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION MODIFICATION PLAN D'ACTION (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=plan.details_cdr.cdr.processus.uuid,
            action='update_plan_action',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========
        
        # Protection : empêcher la modification si la CDR est validée
        if plan.details_cdr.cdr.is_validated:
            return Response({
                'error': 'Cette CDR est validée. Les champs du plan d\'action ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = PlanActionUpdateSerializer(plan, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            plan = serializer.save()
            return Response(PlanActionSerializer(plan).data)
        logger.error("Erreurs de validation du serializer: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except PlanAction.DoesNotExist:
        return Response({
            'error': 'Plan d\'action non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour du plan d'action: %s", str(e))
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e), 'traceback': error_traceback} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suivi_action_create(request):
    """Créer un nouveau suivi d'action"""
    try:
        logger.info("[suivi_action_create] Données reçues: %s", request.data)
        
        # Vérifier si un amendement existe avant de créer un suivi (bloquer la création de suivis dans le tableau précédent)
        # SAUF lors d'une copie d'amendement (from_amendment_copy=True)
        from_amendment_copy = request.data.get('from_amendment_copy', False) or \
                             request.data.get('from_amendment_copy') == 'true' or \
                             request.data.get('from_amendment_copy') == True
        
        plan_action_uuid = request.data.get('plan_action')
        if plan_action_uuid and not from_amendment_copy:
            try:
                plan_action = PlanAction.objects.select_related(
                    
                    'details_cdr__cdr__processus'
                ).get(uuid=plan_action_uuid)
                cdr = plan_action.details_cdr.cdr
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, cdr.processus.uuid):
                    return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                # ========== PERMISSION CRÉATION SUIVI (Security by Design) ==========
                has_permission, error_response = check_cdr_action_or_403(
                    user=request.user,
                    processus_uuid=cdr.processus.uuid,
                    action='create_suivi_action',
                )
                if not has_permission:
                    return error_response
                # ========== FIN PERMISSION ==========
                # Vérifier si un amendement supérieur existe pour ce CDR
                has_superior = CDR.objects.filter(
                    processus=cdr.processus,
                    annee=cdr.annee,
                    cree_par=request.user,
                    num_amendement=cdr.num_amendement + 1
                ).exists()
                if has_superior:
                    return Response({
                        'error': 'Les suivis d\'actions ne peuvent plus être créés car un amendement a été créé pour cette CDR.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except PlanAction.DoesNotExist:
                pass  # La validation du serializer gérera cette erreur
        
        serializer = SuiviActionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            suivi = serializer.save()
            logger.info("[suivi_action_create] ✅ Suivi créé avec succès: %s", suivi.uuid)
            return Response(SuiviActionSerializer(suivi).data, status=status.HTTP_201_CREATED)
        
        logger.error("[suivi_action_create] Erreurs de validation: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création du suivi: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer le suivi d\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def suivi_action_update(request, uuid):
    """Mettre à jour un suivi d'action"""
    try:
        suivi = SuiviAction.objects.select_related(
            
            'plan_action__details_cdr__cdr__processus'
        ).get(uuid=uuid)
        
        cdr = suivi.plan_action.details_cdr.cdr
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION MODIFICATION SUIVI (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=cdr.processus.uuid,
            action='update_suivi_action',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========
        
        # Les suivis d'actions ne peuvent être modifiés que si la CDR est validée
        if not cdr.is_validated:
            return Response({
                'error': 'Les suivis d\'actions ne peuvent être modifiés qu\'après validation de la CDR.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si un amendement supérieur existe pour ce CDR (bloquer l'édition des suivis du tableau précédent)
        cdr_num = cdr.num_amendement
        has_superior = CDR.objects.filter(
            processus=cdr.processus,
            annee=cdr.annee,
            cree_par=request.user,
            num_amendement=cdr_num + 1
        ).exists()
        if has_superior:
            return Response({
                'error': 'Les suivis d\'actions ne peuvent plus être modifiés car un amendement a été créé pour cette CDR.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SuiviActionUpdateSerializer(suivi, data=request.data, partial=True)
        if serializer.is_valid():
            suivi = serializer.save()
            return Response(SuiviActionSerializer(suivi).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except SuiviAction.DoesNotExist:
        return Response({
            'error': 'Suivi d\'action non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour du suivi: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de mettre à jour le suivi d\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


