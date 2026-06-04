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

def validate_cdr(request, uuid):
    """Valider une CDR pour permettre la saisie des suivis d'action"""
    try:
        from django.utils import timezone
        from django.conf import settings
        
        cdr = CDR.objects.select_related('processus').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION VALIDATION CDR (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=cdr.processus.uuid,
            action='validate_cdr',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========
        
        # Vérifier que la CDR n'est pas déjà validée
        if cdr.is_validated:
            return Response({
                'success': False,
                'error': 'Cette CDR est déjà validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier qu'il y a au moins un détail CDR
        details = DetailsCDR.objects.filter(cdr=cdr)
        if details.count() == 0:
            return Response({
                'success': False,
                'error': 'La CDR doit contenir au moins un détail pour être validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        errors = []
        
        # Vérifier chaque détail CDR
        for detail in details:
            detail_errors = []
            
            # Vérifier les champs requis du détail CDR
            if not detail.numero_cdr or detail.numero_cdr.strip() == '':
                detail_errors.append('Le numéro CDR est requis')
            if not detail.activites or detail.activites.strip() == '':
                detail_errors.append('Les activités sont requises')
            if not detail.objectifs or detail.objectifs.strip() == '':
                detail_errors.append('Les objectifs sont requis')
            if not detail.evenements_indesirables_risques or detail.evenements_indesirables_risques.strip() == '':
                detail_errors.append('Les événements indésirables et risques sont requis')
            if not detail.causes or detail.causes.strip() == '':
                detail_errors.append('Les causes sont requises')
            if not detail.consequences or detail.consequences.strip() == '':
                detail_errors.append('Les conséquences sont requises')
            
            # Vérifier qu'il y a une évaluation de risque initiale (version INITIAL)
            # On ne vérifie que l'évaluation initiale, pas les réévaluations
            evaluations = EvaluationRisque.objects.filter(details_cdr=detail).select_related('version_evaluation').order_by('created_at')
            if evaluations.count() == 0:
                detail_errors.append('Une évaluation de risque est requise')
            else:
                # Vérifier que l'évaluation initiale (première créée) a tous les champs requis
                evaluation = evaluations.first()
                if not evaluation.frequence:
                    detail_errors.append('La fréquence du risque est requise dans l\'évaluation initiale')
                if not evaluation.gravite:
                    detail_errors.append('La gravité du risque est requise dans l\'évaluation initiale')
                if not evaluation.criticite:
                    detail_errors.append('La criticité du risque est requise dans l\'évaluation initiale')
                if not evaluation.risque:
                    detail_errors.append('Le type de risque est requis dans l\'évaluation initiale')
            
            # Vérifier qu'il y a au moins un plan d'action
            from .models import PlanActionResponsable
            plans = PlanAction.objects.filter(details_cdr=detail)
            if plans.count() == 0:
                detail_errors.append('Au moins un plan d\'action est requis')
            else:
                # Vérifier que chaque plan d'action a tous les champs requis
                for plan in plans:
                    plan_errors = []
                    if not plan.actions_mesures or plan.actions_mesures.strip() == '':
                        plan_errors.append('Les actions/mesures sont requises')
                    # Vérifier les responsables (nouveau modèle PlanActionResponsable ou ancien champ responsable)
                    has_responsable = plan.responsable is not None or PlanActionResponsable.objects.filter(plan_action=plan).exists()
                    if not has_responsable:
                        plan_errors.append('Le responsable est requis')
                    if not plan.delai_realisation:
                        plan_errors.append('Le délai de réalisation est requis')

                    if plan_errors:
                        detail_errors.append(f'Plan d\'action: {", ".join(plan_errors)}')
            
            if detail_errors:
                errors.append({
                    'detail': detail.numero_cdr or f'Détail sans numéro (UUID: {detail.uuid})',
                    'errors': detail_errors
                })
        
        # Si des erreurs sont trouvées, les retourner
        if errors:
            return Response({
                'success': False,
                'error': 'Des champs obligatoires sont manquants',
                'details': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider la CDR
        cdr.is_validated = True
        cdr.date_validation = timezone.now()
        cdr.valide_par = request.user
        cdr.save()

        logger.info(f"CDR {cdr.uuid} validée par {request.user.username}")

        # Log de l'activité
        try:
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            log_cdr_validation(request.user, cdr, ip_address, user_agent)
        except Exception as log_error:
            logger.error(f"Erreur lors du logging de la validation de la CDR: {log_error}")

        return Response({
            'success': True,
            'message': 'CDR validée avec succès',
            'data': {
                'uuid': str(cdr.uuid),
                'is_validated': cdr.is_validated,
                'date_validation': cdr.date_validation.isoformat() if cdr.date_validation else None,
                'valide_par': request.user.username
            }
        }, status=status.HTTP_200_OK)
        
    except CDR.DoesNotExist:
        return Response({
            'success': False,
            'error': 'CDR non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur validation CDR: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'success': False,
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unvalidate_cdr(request, uuid):
    """Dévalider une CDR (retour en brouillon)"""
    try:
        cdr = CDR.objects.select_related('processus').get(uuid=uuid)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # ========== PERMISSION DÉVALIDATION CDR (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=cdr.processus.uuid,
            action='unvalidate_cdr',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========

        if not cdr.is_validated:
            return Response({
                'success': False,
                'error': 'Cette CDR n\'est pas validée'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier qu'aucun amendement validé ne dépend de cette CDR
        code = cdr.num_amendement
        if code == 0:
            amendements_valides = CDR.objects.filter(
                initial_ref=cdr,
                is_validated=True
            ).exists()
            if amendements_valides:
                return Response({
                    'success': False,
                    'error': 'Impossible de dévalider cette CDR : il existe des amendements validés qui en dépendent'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif code == 1:
            amendement_2_valide = CDR.objects.filter(
                annee=cdr.annee,
                processus=cdr.processus,
                num_amendement=2,
                is_validated=True
            ).exists()
            if amendement_2_valide:
                return Response({
                    'success': False,
                    'error': 'Impossible de dévalider cet amendement : l\'amendement 2 est validé'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Dévalider la CDR
        cdr.is_validated = False
        cdr.date_validation = None
        cdr.valide_par = None
        cdr.save()

        logger.info(f"CDR {cdr.uuid} dévalidée par {request.user.username}")

        return Response({
            'success': True,
            'message': 'CDR dévalidée avec succès',
            'data': CDRSerializer(cdr).data
        }, status=status.HTTP_200_OK)

    except CDR.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cartographie des risques non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur dévalidation CDR: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'success': False,
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS VERSIONS ÉVALUATION CDR ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def versions_evaluation_list(request):
    """Liste toutes les versions d'évaluation actives triées par date de création"""
    try:
        from parametre.models import VersionEvaluationCDR
        from .serializers import VersionEvaluationCDRSerializer

        versions = VersionEvaluationCDR.objects.filter(is_active=True).order_by('created_at')
        serializer = VersionEvaluationCDRSerializer(versions, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur lors de la récupération des versions: {str(e)}')
        return Response({
            'error': 'Impossible de récupérer les versions d\'évaluation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_reevaluation(request, detail_cdr_uuid):
    """
    Créer une nouvelle réévaluation pour un détail CDR
    Trouve automatiquement la prochaine version disponible et pré-remplit avec la dernière évaluation
    """
    try:
        from parametre.models import VersionEvaluationCDR
        from .serializers import EvaluationRisqueCreateSerializer, EvaluationRisqueSerializer

        # Récupérer le détail CDR
        detail_cdr = DetailsCDR.objects.select_related('cdr__processus').get(uuid=detail_cdr_uuid)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, detail_cdr.cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION CRÉATION RÉÉVALUATION (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=detail_cdr.cdr.processus.uuid,
            action='create_evaluation_risque',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========

        # Vérifier que la CDR EST validée (réévaluation possible seulement après validation)
        if not detail_cdr.cdr.is_validated:
            return Response({
                'error': 'La CDR doit être validée avant de pouvoir créer une réévaluation.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier qu'un amendement supérieur n'existe pas
        current_cdr = detail_cdr.cdr
        superior_num = current_cdr.num_amendement + 1
        has_superior_amendment = CDR.objects.filter(
            cree_par=request.user,
            annee=current_cdr.annee,
            processus=current_cdr.processus,
            num_amendement=superior_num
        ).exists()
        if has_superior_amendment:
            return Response({
                'error': 'Un amendement supérieur existe. Impossible de créer une réévaluation sur ce tableau.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer toutes les versions déjà utilisées pour ce détail
        versions_utilisees_ids = EvaluationRisque.objects.filter(
            details_cdr=detail_cdr
        ).values_list('version_evaluation__uuid', flat=True)

        # Trouver la prochaine version disponible (ordre chronologique par created_at)
        version = VersionEvaluationCDR.objects.filter(
            is_active=True
        ).exclude(
            uuid__in=versions_utilisees_ids
        ).order_by('created_at').first()

        if not version:
            return Response({
                'error': 'Toutes les versions d\'évaluation disponibles ont été utilisées pour ce détail CDR'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Créer une réévaluation vide (sans copier les valeurs de l'évaluation précédente)
        data = {
            'details_cdr': str(detail_cdr.uuid),
            'version_evaluation': str(version.uuid),
            'frequence': None,
            'gravite': None,
            'criticite': None,
            'risque': None,
        }

        serializer = EvaluationRisqueCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            reevaluation = serializer.save()
            logger.info(f"✅ Réévaluation créée: {version.nom} pour détail CDR {detail_cdr.numero_cdr}")
            return Response(EvaluationRisqueSerializer(reevaluation).data, status=status.HTTP_201_CREATED)

        logger.error(f"Erreurs validation réévaluation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except DetailsCDR.DoesNotExist:
        return Response({
            'error': 'Détail CDR non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur création réévaluation: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer la réévaluation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_cdr_previous_year(request):
    """
    Récupérer le dernier CDR de l'année précédente pour un processus donné.
    Retourne le CDR avec le num_amendement le plus élevé (le plus récent).

    Query params:
    - annee: année actuelle (pour calculer l'année précédente)
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

        logger.info(f"[get_last_cdr_previous_year] Recherche du dernier CDR pour processus={processus_uuid}, année={annee_precedente}")

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Récupérer le CDR avec le num_amendement le plus élevé (le plus récent)
        cdr = CDR.objects.filter(
            annee=annee_precedente,
            processus__uuid=processus_uuid,
        ).select_related('processus', 'cree_par', 'valide_par').order_by('-num_amendement').first()

        if cdr:
            logger.info(f"[get_last_cdr_previous_year] CDR trouvé: {cdr.uuid} (num_amendement={cdr.num_amendement})")
            serializer = CDRSerializer(cdr)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun CDR trouvé pour l'année précédente
        logger.info(f"[get_last_cdr_previous_year] Aucun CDR trouvé pour l'année {annee_precedente}")
        return Response({
            'message': f'Aucune cartographie trouvée pour l\'année {annee_precedente}',
            'found': False
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier CDR de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
