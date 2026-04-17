"""
Vues API pour l'application Cartographie de Risque
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import CDR, DetailsCDR, EvaluationRisque, PlanAction, SuiviAction
from .serializers import (
    CDRSerializer, CDRCreateSerializer,
    DetailsCDRSerializer, DetailsCDRCreateSerializer, DetailsCDRUpdateSerializer,
    EvaluationRisqueSerializer, EvaluationRisqueCreateSerializer, EvaluationRisqueUpdateSerializer,
    PlanActionSerializer, PlanActionCreateSerializer, PlanActionUpdateSerializer,
    SuiviActionSerializer, SuiviActionCreateSerializer, SuiviActionUpdateSerializer
)

from parametre.views import (
    log_cdr_creation,
    log_cdr_validation,
    get_client_ip
)
from parametre.permissions import get_user_processus_list, user_has_access_to_processus
from permissions.services.permission_service import PermissionService
import logging

logger = logging.getLogger(__name__)

# Message d'erreur générique pour les 403 (Security by Design : pas de révélation d'infos)
CDR_403_MESSAGE = "Opération non autorisée."
CDR_500_MESSAGE = "Une erreur interne est survenue."


def check_cdr_action_or_403(user, processus_uuid, action, error_message=None):
    """
    Vérifie si l'utilisateur peut effectuer une action CDR (app_name='cdr').
    Utilise le système de permissions granulaire (PermissionService / seed_permissions).
    Retourne (True, None) si autorisé, (False, Response_403) sinon.
    Security by Design : message d'erreur générique, pas de détail exposé.
    """
    from rest_framework.response import Response
    from rest_framework import status
    can_perform, reason = PermissionService.can_perform_action(
        user=user,
        app_name='cdr',
        processus_uuid=str(processus_uuid),
        action=action,
    )
    if can_perform:
        return True, None
    message = error_message or CDR_403_MESSAGE
    return False, Response({'error': message}, status=status.HTTP_403_FORBIDDEN)


# ==================== UTILITAIRES TYPE TABLEAU ====================

def _get_next_num_amendement_for_cdr(user, annee, processus_uuid):
    """
    Retourne le prochain num_amendement pour (annee, processus, user).
    0 si aucun CDR n'existe encore, sinon max_existant + 1.
    """
    try:
        logger.info(f"[_get_next_num_amendement_for_cdr] user={user}, annee={annee}, processus_uuid={processus_uuid}")
        existing = CDR.objects.filter(
            cree_par=user,
            annee=annee,
            processus_id=processus_uuid
        ).order_by('-num_amendement').first()
        if not existing:
            logger.info("[_get_next_num_amendement_for_cdr] Aucun CDR existant, retourne 0 (initial)")
            return 0
        next_num = existing.num_amendement + 1
        logger.info(f"[_get_next_num_amendement_for_cdr] Retourne {next_num}")
        return next_num
    except Exception as e:
        logger.error(f"[_get_next_num_amendement_for_cdr] Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


# ==================== ENDPOINTS API ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
        logger.error(f'Erreur dans details_cdr_by_cdr: {str(e)}')
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
        logger.info(f"[details_cdr_create] Données reçues: {request.data}")
        
        # Vérifier si la CDR est validée avant la création
        if 'cdr' in request.data:
            try:
                cdr = CDR.objects.get(uuid=request.data['cdr'])
                logger.info(f"[details_cdr_create] CDR trouvée: {cdr.uuid}, validée: {cdr.is_validated}")
                
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
                logger.error(f"[details_cdr_create] CDR non trouvée avec UUID: {request.data['cdr']}")
                pass  # La validation du serializer gérera cette erreur
        
        serializer = DetailsCDRCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            detail = serializer.save()
            logger.info(f"[details_cdr_create] ✅ Détail créé avec succès: {detail.uuid}")
            return Response(DetailsCDRSerializer(detail).data, status=status.HTTP_201_CREATED)
        
        logger.error(f"[details_cdr_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du détail CDR: {str(e)}")
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
        logger.error(f'Erreur dans evaluations_by_detail_cdr: {str(e)}')
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
        logger.error(f'Erreur dans plans_action_by_detail_cdr: {str(e)}')
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
        logger.error(f'Erreur dans suivi_action_detail: {str(e)}')
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
        logger.error(f'Erreur dans suivis_by_plan_action: {str(e)}')
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
        logger.error(f"Erreur lors de la mise à jour du détail CDR: {str(e)}")
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
        logger.error(f"Erreur lors de la suppression du détail CDR: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        from django.conf import settings
        return Response({
            'error': CDR_500_MESSAGE,
            **({'details': str(e)} if settings.DEBUG else {})
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def evaluation_risque_create(request):
    """Créer une nouvelle évaluation de risque"""
    try:
        logger.info(f"[evaluation_risque_create] Données reçues: {request.data}")

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
                logger.info(f"[evaluation_risque_create] Version par défaut assignée: {version_initiale.nom}")
            except Exception as e:
                logger.error(f"[evaluation_risque_create] Erreur récupération version: {str(e)}")
                return Response({
                    'error': 'Erreur lors de la récupération de la version d\'évaluation.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = EvaluationRisqueCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            evaluation = serializer.save()
            logger.info(f"[evaluation_risque_create] ✅ Évaluation créée avec succès: {evaluation.uuid}")
            return Response(EvaluationRisqueSerializer(evaluation).data, status=status.HTTP_201_CREATED)

        logger.error(f"[evaluation_risque_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'évaluation: {str(e)}")
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
        current_type_code = getattr('num_amendement', None)

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
        logger.error(f"Erreur lors de la mise à jour de l'évaluation: {str(e)}")
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
        logger.info(f"[plan_action_create] Données reçues: {request.data}")
        
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
            logger.info(f"[plan_action_create] ✅ Plan d'action créé avec succès: {plan.uuid}")
            return Response(PlanActionSerializer(plan).data, status=status.HTTP_201_CREATED)
        
        logger.error(f"[plan_action_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du plan d'action: {str(e)}")
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
        logger.error(f"Erreurs de validation du serializer: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except PlanAction.DoesNotExist:
        return Response({
            'error': 'Plan d\'action non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du plan d'action: {str(e)}")
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
        logger.info(f"[suivi_action_create] Données reçues: {request.data}")
        
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
                    num_amendement=cdr_num + 1
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
            logger.info(f"[suivi_action_create] ✅ Suivi créé avec succès: {suivi.uuid}")
            return Response(SuiviActionSerializer(suivi).data, status=status.HTTP_201_CREATED)
        
        logger.error(f"[suivi_action_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du suivi: {str(e)}")
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
        logger.error(f"Erreur lors de la mise à jour du suivi: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de mettre à jour le suivi d\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
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

