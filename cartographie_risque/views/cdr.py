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

def cartographie_risque_home(request):
    """Endpoint de base pour la cartographie de risque"""
    try:
        return Response({
            'success': True,
            'message': 'API Cartographie de Risque',
            'data': {
                'version': '1.0.0',
                'description': 'Application de cartographie de risque'
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans cartographie_risque_home: {str(e)}')
        from django.conf import settings
        return Response({
            'success': False,
            'message': CDR_500_MESSAGE,
            **({'error': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cdr_list(request):
    """Liste toutes les CDR de l'utilisateur connecté"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # None = super admin (accès à tous les processus), [] = aucun processus
        user_processus_uuids = get_user_processus_list(request.user)

        if user_processus_uuids is not None and len(user_processus_uuids) == 0:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucune CDR trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)

        # Super admin (None) : toutes les CDR. Sinon : filtrer par processus.
        if user_processus_uuids is None:
            cdrs = CDR.objects.select_related(
                'processus', 'cree_par', 'valide_par'
            ).order_by('-annee', 'processus__numero_processus')
        else:
            cdrs = CDR.objects.filter(processus__uuid__in=user_processus_uuids).select_related(
                'processus', 'cree_par', 'valide_par'
            ).order_by('-annee', 'processus__numero_processus')
        # ========== FIN FILTRAGE ==========
        
        serializer = CDRSerializer(cdrs, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': cdrs.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans cdr_list: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATISTIQUES CDR ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cdr_stats(request):
    """Statistiques des CDR de l'utilisateur connecté (compatible super admin)"""
    try:
        logger.info(f"[cdr_stats] Début pour l'utilisateur: {request.user.username}")
        scope = request.query_params.get('scope', 'tous')

        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)

        # Si user_processus_uuids est None, l'utilisateur est super admin
        if user_processus_uuids is None:
            cdrs_base = CDR.objects.all()
            processus_filter = request.query_params.get('processus')
            if processus_filter and str(processus_filter).upper() != 'ALL':
                try:
                    from uuid import UUID
                    UUID(str(processus_filter))
                    cdrs_base = cdrs_base.filter(processus__uuid=processus_filter)
                except (ValueError, TypeError):
                    pass
        elif not user_processus_uuids:
            logger.info(f"[cdr_stats] Aucun processus assigné pour l'utilisateur {request.user.username}")
            return Response({
                'total_cdrs': 0,
                'cdrs_valides': 0,
                'total_amendements': 0,
                'cdrs_en_cours': 0,
                'total_details': 0,
                'total_plans_action': 0,
            }, status=status.HTTP_200_OK)
        else:
            cdrs_base = CDR.objects.filter(processus__uuid__in=user_processus_uuids)
        # ========== FIN FILTRAGE ==========

        # Filtrer selon le scope
        if scope == 'dernier':
            from django.db.models import Case, When, IntegerField, Max
            type_priority = Case(
                When(num_amendement=2, then=3),
                When(num_amendement=1, then=2),
                When(num_amendement=0, then=1),
                default=0, output_field=IntegerField()
            )
            annotated = cdrs_base.filter(num_amendement__gte=0).annotate(priority=type_priority)
            last_uuids = []
            for proc_uuid in annotated.values_list('processus', flat=True).distinct():
                max_p = annotated.filter(processus=proc_uuid).aggregate(max_p=Max('priority'))['max_p']
                last = annotated.filter(processus=proc_uuid, priority=max_p).first()
                if last:
                    last_uuids.append(last.uuid)
            cdrs_initiaux = cdrs_base.filter(uuid__in=last_uuids)
        else:
            cdrs_initiaux = cdrs_base.filter(num_amendement=0)

        total_cdrs = cdrs_initiaux.count()
        cdrs_valides = cdrs_initiaux.filter(is_validated=True).count()
        cdrs_en_cours = cdrs_initiaux.filter(is_validated=False).count()

        # Amendements (AMENDEMENT_1, AMENDEMENT_2)
        total_amendements = cdrs_base.filter(
            num_amendement__gt=0
        ).count()

        total_details = DetailsCDR.objects.filter(cdr__in=cdrs_base).count()
        total_plans_action = PlanAction.objects.filter(details_cdr__cdr__in=cdrs_base).count()

        stats = {
            'total_cdrs': total_cdrs,
            'cdrs_valides': cdrs_valides,
            'total_amendements': total_amendements,
            'cdrs_en_cours': cdrs_en_cours,
            'total_details': total_details,
            'total_plans_action': total_plans_action,
        }
        logger.info(f"[cdr_stats] Statistiques calculées: {stats}")
        return Response(stats, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques CDR: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des statistiques',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cdr_detail(request, uuid):
    """Détails d'une CDR spécifique"""
    try:
        cdr = CDR.objects.select_related(
            'processus', 'cree_par', 'valide_par'
        ).get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, cdr.processus.uuid):
            return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        # ========== PERMISSION LECTURE CDR (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=cdr.processus.uuid,
            action='read_cdr',
        )
        if not has_permission:
            return error_response
        # ========== FIN PERMISSION ==========
        
        serializer = CDRSerializer(cdr)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except CDR.DoesNotExist:
        return Response({
            'error': 'CDR non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans cdr_detail: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cdr_get_or_create(request):
    """
    Récupérer ou créer une CDR unique pour (processus, annee, num_amendement).
    """
    try:
        logger.info(f"[cdr_get_or_create] Début - données reçues: {request.data}")
        data = request.data.copy()
        annee = data.get('annee')
        processus_uuid = data.get('processus')

        # Convertir annee en entier si c'est une chaîne
        if annee:
            try:
                annee = int(annee)
            except (ValueError, TypeError):
                return Response({
                    'error': "Le champ 'annee' doit être un nombre entier"
                }, status=status.HTTP_400_BAD_REQUEST)

        # Déterminer num_amendement : utiliser la valeur fournie ou l'attribuer automatiquement
        num_amendement_raw = data.get('num_amendement')
        if num_amendement_raw is None and annee and processus_uuid:
            try:
                num_amendement_value = _get_next_num_amendement_for_cdr(request.user, annee, processus_uuid)
                data['num_amendement'] = num_amendement_value
            except Exception as tt_error:
                logger.error(f"[cdr_get_or_create] Erreur détermination automatique num_amendement: {tt_error}")
                num_amendement_value = 0
                data['num_amendement'] = 0
        else:
            try:
                num_amendement_value = int(num_amendement_raw) if num_amendement_raw is not None else 0
            except (ValueError, TypeError):
                num_amendement_value = 0
            data['num_amendement'] = num_amendement_value

        # Gérer initial_ref automatiquement pour les amendements
        if num_amendement_value > 0 and not data.get('initial_ref'):
            cdr_initial = CDR.objects.filter(
                cree_par=request.user,
                annee=annee,
                processus_id=processus_uuid,
                num_amendement=0
            ).first()
            if cdr_initial:
                if not cdr_initial.is_validated:
                    return Response({
                        'error': 'Le CDR initial doit être validé avant de pouvoir créer un amendement.',
                        'initial_cdr_uuid': str(cdr_initial.uuid)
                    }, status=status.HTTP_400_BAD_REQUEST)
                data['initial_ref'] = str(cdr_initial.uuid)
                logger.info(f"[cdr_get_or_create] CDR initial trouvé automatiquement: {cdr_initial.uuid}")
            else:
                return Response({
                    'error': 'Aucun CDR initial trouvé pour créer cet amendement. Veuillez d\'abord créer et valider un CDR initial.'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif num_amendement_value == 0:
            # CDR initial : pas d'initial_ref
            data.pop('initial_ref', None)

        logger.info(f"[cdr_get_or_create] annee={annee}, processus_uuid={processus_uuid}, num_amendement={num_amendement_value}")

        if not (annee and processus_uuid):
            logger.warning("[cdr_get_or_create] annee ou processus manquant")
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ========== VÉRIFICATION DES PERMISSIONS (Security by Design) ==========
        has_permission, error_response = check_cdr_action_or_403(
            user=request.user,
            processus_uuid=processus_uuid,
            action='create_cdr',
        )
        if not has_permission:
            return error_response
        # ========== FIN VÉRIFICATION DES PERMISSIONS ==========

        # Vérifier si une CDR existe déjà avec ce (processus, annee, num_amendement)
        try:
            cdr = CDR.objects.get(
                processus__uuid=processus_uuid,
                annee=annee,
                num_amendement=num_amendement_value,
                cree_par=request.user
            )
            logger.info(f"[cdr_get_or_create] CDR existante trouvée: {cdr.uuid}")

            # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
            if not user_has_access_to_processus(request.user, cdr.processus.uuid):
                return Response({'error': CDR_403_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
            # ========== FIN VÉRIFICATION ==========

            serializer = CDRSerializer(cdr)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except CDR.DoesNotExist:
            logger.info(f"[cdr_get_or_create] Aucune CDR existante, création d'une nouvelle CDR")

            # Créer une nouvelle CDR
            serializer = CDRCreateSerializer(data=data, context={'request': request})

            if serializer.is_valid():
                logger.info(f"[cdr_get_or_create] Serializer valide, données validées: {serializer.validated_data}")
                cdr = serializer.save()
                logger.info(f"[cdr_get_or_create] CDR créée avec succès: {cdr.uuid}")

                # Log de l'activité
                try:
                    ip_address = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    log_cdr_creation(request.user, cdr, ip_address, user_agent)
                except Exception as log_error:
                    logger.error(f"Erreur lors du logging de la création de la CDR: {log_error}")

                # Sérialiser la CDR créée pour la réponse
                response_serializer = CDRSerializer(cdr)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)

            logger.error(f"[cdr_get_or_create] Erreurs de validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except CDR.MultipleObjectsReturned:
            logger.warning("[cdr_get_or_create] Plusieurs CDR trouvées, utilisation de la première")
            cdr = CDR.objects.filter(
                processus__uuid=processus_uuid,
                annee=annee,
                num_amendement=num_amendement_value,
                cree_par=request.user
            ).first()
            serializer = CDRSerializer(cdr)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"[cdr_get_or_create] Erreur exception non gérée: {str(e)}")
        import traceback
        logger.error(f"[cdr_get_or_create] Traceback: {traceback.format_exc()}")
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


