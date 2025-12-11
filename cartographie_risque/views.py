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
from parametre.models import Versions
from parametre.views import (
    log_cdr_creation,
    log_cdr_validation,
    get_client_ip
)
import logging

logger = logging.getLogger(__name__)


# ==================== UTILITAIRES TYPE TABLEAU ====================

def _get_next_type_tableau_for_cdr(user, annee, processus_uuid):
    """
    Retourne l'instance Versions à utiliser automatiquement pour (annee, processus) d'un user.
    Ordre: INITIAL -> AMENDEMENT_1 -> AMENDEMENT_2. Si tous existent déjà, retourne AMENDEMENT_2.
    """
    try:
        logger.info(f"[_get_next_type_tableau_for_cdr] user={user}, annee={annee}, processus_uuid={processus_uuid}")
        codes_order = ['INITIAL', 'AMENDEMENT_1', 'AMENDEMENT_2']
        existing_types = set(
            CDR.objects.filter(
                cree_par=user,
                annee=annee,
                processus_id=processus_uuid
            ).values_list('type_tableau__code', flat=True)
        )
        logger.info(f"[_get_next_type_tableau_for_cdr] existing_types={existing_types}")
        for code in codes_order:
            if code not in existing_types:
                version = Versions.objects.get(code=code)
                logger.info(f"[_get_next_type_tableau_for_cdr] Retourne version {code}: {version}")
                return version
        # Tous déjà présents: retourner le dernier
        version = Versions.objects.get(code=codes_order[-1])
        logger.info(f"[_get_next_type_tableau_for_cdr] Tous présents, retourne {version}")
        return version
    except Versions.DoesNotExist as e:
        logger.error(f"[_get_next_type_tableau_for_cdr] Versions.DoesNotExist: {e}")
        # En cas de configuration incomplète, fallback sur le premier disponible
        fallback = Versions.objects.order_by('nom').first()
        logger.info(f"[_get_next_type_tableau_for_cdr] Fallback sur {fallback}")
        return fallback
    except Exception as e:
        logger.error(f"[_get_next_type_tableau_for_cdr] Erreur: {e}")
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
        return Response({
            'success': False,
            'message': 'Erreur serveur',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cdr_list(request):
    """Liste toutes les CDR de l'utilisateur connecté"""
    try:
        cdrs = CDR.objects.filter(cree_par=request.user).select_related(
            'processus', 'type_tableau', 'cree_par', 'valide_par'
        ).order_by('-annee', 'processus__numero_processus')
        
        serializer = CDRSerializer(cdrs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans cdr_list: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des CDR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cdr_detail(request, uuid):
    """Détails d'une CDR spécifique"""
    try:
        cdr = CDR.objects.select_related(
            'processus', 'type_tableau', 'cree_par', 'valide_par'
        ).get(uuid=uuid, cree_par=request.user)
        
        serializer = CDRSerializer(cdr)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except CDR.DoesNotExist:
        return Response({
            'error': 'CDR non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans cdr_detail: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération de la CDR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cdr_get_or_create(request):
    """
    Récupérer ou créer une CDR unique pour (processus, annee, type_tableau).
    Un seul CDR peut exister pour une combinaison (processus, annee, type_tableau).
    """
    try:
        logger.info(f"[cdr_get_or_create] Début - données reçues: {request.data}")
        data = request.data.copy()
        annee = data.get('annee')
        processus_uuid = data.get('processus')
        type_tableau_uuid = data.get('type_tableau')

        # Convertir annee en entier si c'est une chaîne
        if annee:
            try:
                annee = int(annee)
            except (ValueError, TypeError):
                return Response({
                    'error': "Le champ 'annee' doit être un nombre entier"
                }, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"[cdr_get_or_create] annee={annee}, processus_uuid={processus_uuid}, type_tableau_uuid={type_tableau_uuid}")

        # Si type_tableau est absent mais annee + processus sont fournis, l'attribuer automatiquement
        initial_ref_uuid = data.get('initial_ref')  # Utiliser celui fourni si présent
        if annee and processus_uuid and not type_tableau_uuid:
            logger.info("[cdr_get_or_create] type_tableau absent, appel à _get_next_type_tableau_for_cdr")
            try:
                auto_tt = _get_next_type_tableau_for_cdr(request.user, annee, processus_uuid)
                if auto_tt:
                    data['type_tableau'] = str(auto_tt.uuid)
                    type_tableau_uuid = data['type_tableau']
                    logger.info(f"[cdr_get_or_create] type_tableau automatique défini: {type_tableau_uuid} (code: {auto_tt.code})")

                    # Si c'est un amendement (AMENDEMENT_1 ou AMENDEMENT_2), trouver le CDR initial
                    # Sauf si initial_ref a déjà été fourni dans la requête
                    if auto_tt.code in ['AMENDEMENT_1', 'AMENDEMENT_2']:
                        if not initial_ref_uuid:
                            try:
                                # Trouver le CDR initial pour ce processus/année
                                cdr_initial = CDR.objects.filter(
                                    cree_par=request.user,
                                    annee=annee,
                                    processus_id=processus_uuid,
                                    type_tableau__code='INITIAL'
                                ).first()

                                if cdr_initial:
                                    # Vérifier que le CDR initial est validé
                                    if not cdr_initial.is_validated:
                                        logger.warning(f"[cdr_get_or_create] ⚠️ Le CDR initial {cdr_initial.uuid} n'est pas validé. Impossible de créer un amendement.")
                                        return Response({
                                            'error': 'Le CDR initial doit être validé avant de pouvoir créer un amendement. Veuillez d\'abord valider tous les détails du CDR initial.',
                                            'initial_cdr_uuid': str(cdr_initial.uuid)
                                        }, status=status.HTTP_400_BAD_REQUEST)

                                    initial_ref_uuid = str(cdr_initial.uuid)
                                    data['initial_ref'] = initial_ref_uuid
                                    logger.info(f"[cdr_get_or_create] CDR initial trouvé automatiquement: {initial_ref_uuid} pour l'amendement {auto_tt.code}")
                                else:
                                    logger.warning(f"[cdr_get_or_create] ⚠️ Aucun CDR initial trouvé pour processus={processus_uuid}, annee={annee}. L'amendement sera créé sans initial_ref.")
                                    return Response({
                                        'error': 'Aucun CDR initial trouvé pour créer cet amendement. Veuillez d\'abord créer et valider un CDR initial.'
                                    }, status=status.HTTP_400_BAD_REQUEST)
                            except Exception as init_error:
                                logger.error(f"[cdr_get_or_create] Erreur lors de la recherche du CDR initial: {init_error}")
                                import traceback
                                logger.error(traceback.format_exc())
                        else:
                            logger.info(f"[cdr_get_or_create] initial_ref déjà fourni: {initial_ref_uuid}")
                    elif auto_tt.code == 'INITIAL':
                        # Pour un CDR INITIAL, initial_ref doit être null
                        if 'initial_ref' in data:
                            data.pop('initial_ref')
                            logger.info(f"[cdr_get_or_create] initial_ref retiré car c'est un CDR INITIAL")
            except Exception as tt_error:
                logger.error(f"[cdr_get_or_create] Erreur lors de la détermination automatique du type_tableau: {tt_error}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue sans type_tableau si erreur

        if not (annee and processus_uuid):
            logger.warning("[cdr_get_or_create] annee ou processus manquant")
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis. 'type_tableau' peut être omis et sera déterminé automatiquement."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier si une CDR existe déjà avec ce (processus, annee, type_tableau)
        try:
            cdr = CDR.objects.get(
                processus__uuid=processus_uuid,
                annee=annee,
                type_tableau__uuid=type_tableau_uuid,
                cree_par=request.user
            )
            logger.info(f"[cdr_get_or_create] CDR existante trouvée: {cdr.uuid}")
            
            # Sérialiser la CDR existante pour la réponse
            serializer = CDRSerializer(cdr)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except CDR.DoesNotExist:
            logger.info(f"[cdr_get_or_create] Aucune CDR existante, création d'une nouvelle CDR")

            # Si initial_ref n'est pas dans data mais qu'on doit créer un amendement, le trouver
            if 'initial_ref' not in data or not data.get('initial_ref'):
                # Vérifier si le type_tableau est un amendement
                if type_tableau_uuid:
                    try:
                        type_tableau_obj = Versions.objects.get(uuid=type_tableau_uuid)
                        if type_tableau_obj.code in ['AMENDEMENT_1', 'AMENDEMENT_2']:
                            # Trouver le CDR initial
                            cdr_initial = CDR.objects.filter(
                                cree_par=request.user,
                                annee=annee,
                                processus_id=processus_uuid,
                                type_tableau__code='INITIAL'
                            ).first()

                            if cdr_initial:
                                # Vérifier que le CDR initial est validé
                                if not cdr_initial.is_validated:
                                    logger.warning(f"[cdr_get_or_create] ⚠️ Le CDR initial {cdr_initial.uuid} n'est pas validé. Impossible de créer un amendement.")
                                    return Response({
                                        'error': 'Le CDR initial doit être validé avant de pouvoir créer un amendement. Veuillez d\'abord valider tous les détails du CDR initial.',
                                        'initial_cdr_uuid': str(cdr_initial.uuid)
                                    }, status=status.HTTP_400_BAD_REQUEST)

                                data['initial_ref'] = str(cdr_initial.uuid)
                                logger.info(f"[cdr_get_or_create] CDR initial ajouté automatiquement: {cdr_initial.uuid}")
                            else:
                                logger.warning(f"[cdr_get_or_create] ⚠️ Aucun CDR initial trouvé pour créer l'amendement {type_tableau_obj.code}")
                                return Response({
                                    'error': 'Aucun CDR initial trouvé pour créer cet amendement. Veuillez d\'abord créer et valider un CDR initial.'
                                }, status=status.HTTP_400_BAD_REQUEST)
                    except Versions.DoesNotExist:
                        logger.warning(f"[cdr_get_or_create] Type tableau {type_tableau_uuid} non trouvé")
                    except Exception as e:
                        logger.error(f"[cdr_get_or_create] Erreur lors de la recherche du CDR initial: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
            else:
                logger.info(f"[cdr_get_or_create] initial_ref fourni: {data.get('initial_ref')}")
                # Vérifier que le CDR initial fourni est validé
                initial_ref_uuid = data.get('initial_ref')
                if initial_ref_uuid:
                    try:
                        cdr_initial = CDR.objects.get(uuid=initial_ref_uuid, cree_par=request.user)
                        if not cdr_initial.is_validated:
                            logger.warning(f"[cdr_get_or_create] ⚠️ Le CDR initial {initial_ref_uuid} n'est pas validé. Impossible de créer un amendement.")
                            return Response({
                                'error': 'Le CDR initial doit être validé avant de pouvoir créer un amendement. Veuillez d\'abord valider tous les détails du CDR initial.',
                                'initial_cdr_uuid': str(initial_ref_uuid)
                            }, status=status.HTTP_400_BAD_REQUEST)
                    except CDR.DoesNotExist:
                        logger.error(f"[cdr_get_or_create] CDR initial {initial_ref_uuid} non trouvé")
                        return Response({
                            'error': 'CDR initial non trouvé.'
                        }, status=status.HTTP_404_NOT_FOUND)

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
                type_tableau__uuid=type_tableau_uuid,
                cree_par=request.user
            ).first()
            serializer = CDRSerializer(cdr)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"[cdr_get_or_create] Erreur exception non gérée: {str(e)}")
        import traceback
        logger.error(f"[cdr_get_or_create] Traceback: {traceback.format_exc()}")
        return Response({
            'error': 'Erreur lors de la création/récupération de la CDR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def details_cdr_by_cdr(request, cdr_uuid):
    """Récupérer tous les détails CDR pour une CDR spécifique"""
    try:
        # Vérifier que la CDR existe et appartient à l'utilisateur
        cdr = CDR.objects.get(uuid=cdr_uuid, cree_par=request.user)
        
        # Récupérer les détails CDR
        details = DetailsCDR.objects.filter(cdr=cdr).order_by('numero_cdr', 'created_at')
        
        serializer = DetailsCDRSerializer(details, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except CDR.DoesNotExist:
        return Response({
            'error': 'CDR non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans details_cdr_by_cdr: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des détails CDR',
            'details': str(e)
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
        error_response = {
            'error': 'Impossible de créer le détail CDR',
            'details': str(e)
        }
        if settings.DEBUG:
            error_response['traceback'] = error_traceback
        
        return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evaluations_by_detail_cdr(request, detail_cdr_uuid):
    """Récupérer toutes les évaluations pour un détail CDR spécifique"""
    try:
        # Vérifier que le détail CDR existe et appartient à l'utilisateur
        detail = DetailsCDR.objects.select_related('cdr').get(uuid=detail_cdr_uuid)
        if detail.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        return Response({
            'error': 'Erreur lors de la récupération des évaluations',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def plans_action_by_detail_cdr(request, detail_cdr_uuid):
    """Récupérer tous les plans d'action pour un détail CDR spécifique"""
    try:
        # Vérifier que le détail CDR existe et appartient à l'utilisateur
        detail = DetailsCDR.objects.select_related('cdr').get(uuid=detail_cdr_uuid)
        if detail.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Récupérer les plans d'action
        plans = PlanAction.objects.filter(
            details_cdr=detail
        ).select_related('responsable', 'details_cdr').order_by('delai_realisation', 'created_at')
        
        serializer = PlanActionSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except DetailsCDR.DoesNotExist:
        return Response({
            'error': 'Détail CDR non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans plans_action_by_detail_cdr: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des plans d\'action',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_action_detail(request, uuid):
    """Récupérer un suivi d'action par son UUID"""
    try:
        suivi = SuiviAction.objects.select_related(
            'plan_action__details_cdr__cdr', 
            'element_preuve'
        ).prefetch_related('element_preuve__medias').get(uuid=uuid)
        
        # Vérifier que le suivi appartient à l'utilisateur connecté
        if suivi.plan_action.details_cdr.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        return Response({
            'error': 'Erreur lors de la récupération du suivi',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivis_by_plan_action(request, plan_action_uuid):
    """Récupérer tous les suivis pour un plan d'action spécifique"""
    try:
        # Vérifier que le plan d'action existe et appartient à l'utilisateur
        plan = PlanAction.objects.select_related('details_cdr__cdr').get(uuid=plan_action_uuid)
        if plan.details_cdr.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        return Response({
            'error': 'Erreur lors de la récupération des suivis',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS DE MISE À JOUR ====================

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def details_cdr_update(request, uuid):
    """Mettre à jour un détail CDR"""
    try:
        detail = DetailsCDR.objects.select_related('cdr').get(uuid=uuid)
        
        # Vérifier que la CDR du détail appartient à l'utilisateur connecté
        if detail.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        return Response({
            'error': 'Impossible de mettre à jour le détail CDR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def details_cdr_delete(request, uuid):
    """Supprimer un détail CDR avec toutes ses données associées (cascade)"""
    try:
        detail = DetailsCDR.objects.select_related('cdr').get(uuid=uuid)

        # Vérifier que la CDR du détail appartient à l'utilisateur connecté
        if detail.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)

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
        return Response({
            'error': 'Impossible de supprimer le détail CDR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def evaluation_risque_create(request):
    """Créer une nouvelle évaluation de risque"""
    try:
        logger.info(f"[evaluation_risque_create] Données reçues: {request.data}")

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
        evaluation = EvaluationRisque.objects.select_related('details_cdr__cdr').get(uuid=uuid)
        
        # Vérifier que la CDR appartient à l'utilisateur connecté
        if evaluation.details_cdr.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Protection : empêcher la modification si un amendement supérieur existe
        current_cdr = evaluation.details_cdr.cdr
        current_type_code = getattr(current_cdr.type_tableau, 'code', None) if current_cdr.type_tableau else None

        # Vérifier si un amendement supérieur existe
        has_superior_amendment = False
        if current_type_code in ['INITIAL', 'AMENDEMENT_1']:
            superior_types = ['AMENDEMENT_1', 'AMENDEMENT_2'] if current_type_code == 'INITIAL' else ['AMENDEMENT_2']
            has_superior_amendment = CDR.objects.filter(
                cree_par=request.user,
                annee=current_cdr.annee,
                processus=current_cdr.processus,
                type_tableau__code__in=superior_types
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
        return Response({
            'error': 'Impossible de créer le plan d\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def plan_action_update(request, uuid):
    """Mettre à jour un plan d'action"""
    try:
        plan = PlanAction.objects.select_related('details_cdr__cdr').get(uuid=uuid)
        
        # Vérifier que la CDR appartient à l'utilisateur connecté
        if plan.details_cdr.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
            'error': f'Impossible de mettre à jour le plan d\'action: {str(e)}',
            'details': error_traceback if settings.DEBUG else None
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
                    'details_cdr__cdr__type_tableau',
                    'details_cdr__cdr__processus'
                ).get(uuid=plan_action_uuid)
                cdr = plan_action.details_cdr.cdr
                cdr_type_code = cdr.type_tableau.code if cdr.type_tableau else None
                
                # Si c'est un CDR INITIAL, vérifier si un AMENDEMENT_1 existe
                if cdr_type_code == 'INITIAL':
                    has_amendment = CDR.objects.filter(
                        initial_ref=cdr,
                        type_tableau__code__in=['AMENDEMENT_1', 'AMENDEMENT_2'],
                        cree_par=request.user
                    ).exists()
                    if has_amendment:
                        return Response({
                            'error': 'Les suivis d\'actions ne peuvent plus être créés car un amendement a été créé pour cette CDR.'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Si c'est un AMENDEMENT_1, vérifier si un AMENDEMENT_2 existe
                elif cdr_type_code == 'AMENDEMENT_1':
                    initial_cdr = cdr.initial_ref
                    if initial_cdr:
                        has_amendment2 = CDR.objects.filter(
                            initial_ref=initial_cdr,
                            type_tableau__code='AMENDEMENT_2',
                            cree_par=request.user
                        ).exists()
                        if has_amendment2:
                            return Response({
                                'error': 'Les suivis d\'actions ne peuvent plus être créés car un amendement 2 a été créé pour cette CDR.'
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
            'plan_action__details_cdr__cdr__type_tableau',
            'plan_action__details_cdr__cdr__processus'
        ).get(uuid=uuid)
        
        cdr = suivi.plan_action.details_cdr.cdr
        
        # Vérifier que la CDR appartient à l'utilisateur connecté
        if cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Les suivis d'actions ne peuvent être modifiés que si la CDR est validée
        if not cdr.is_validated:
            return Response({
                'error': 'Les suivis d\'actions ne peuvent être modifiés qu\'après validation de la CDR.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si un amendement existe pour ce CDR (bloquer l'édition des suivis du tableau précédent)
        cdr_type_code = cdr.type_tableau.code if cdr.type_tableau else None
        
        # Si c'est un CDR INITIAL, vérifier si un AMENDEMENT_1 existe
        if cdr_type_code == 'INITIAL':
            has_amendment = CDR.objects.filter(
                initial_ref=cdr,
                type_tableau__code__in=['AMENDEMENT_1', 'AMENDEMENT_2'],
                cree_par=request.user
            ).exists()
            if has_amendment:
                return Response({
                    'error': 'Les suivis d\'actions ne peuvent plus être modifiés car un amendement a été créé pour cette CDR.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Si c'est un AMENDEMENT_1, vérifier si un AMENDEMENT_2 existe
        elif cdr_type_code == 'AMENDEMENT_1':
            # Trouver le CDR initial
            initial_cdr = cdr.initial_ref
            if initial_cdr:
                has_amendment2 = CDR.objects.filter(
                    initial_ref=initial_cdr,
                    type_tableau__code='AMENDEMENT_2',
                    cree_par=request.user
                ).exists()
                if has_amendment2:
                    return Response({
                        'error': 'Les suivis d\'actions ne peuvent plus être modifiés car un amendement 2 a été créé pour cette CDR.'
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
        
        cdr = CDR.objects.get(uuid=uuid)
        
        # Vérifier que la CDR appartient à l'utilisateur connecté
        if cdr.cree_par != request.user:
            return Response({
                'success': False,
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        return Response({
            'success': False,
            'error': 'Erreur lors de la validation',
            'details': str(e) if settings.DEBUG else None
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
        detail_cdr = DetailsCDR.objects.select_related('cdr').get(uuid=detail_cdr_uuid)

        # Vérifier que la CDR appartient à l'utilisateur connecté
        if detail_cdr.cdr.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)

        # Vérifier que la CDR EST validée (réévaluation possible seulement après validation)
        if not detail_cdr.cdr.is_validated:
            return Response({
                'error': 'La CDR doit être validée avant de pouvoir créer une réévaluation.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier qu'un amendement supérieur n'existe pas
        current_cdr = detail_cdr.cdr
        current_type_code = getattr(current_cdr.type_tableau, 'code', None) if current_cdr.type_tableau else None

        if current_type_code in ['INITIAL', 'AMENDEMENT_1']:
            superior_types = ['AMENDEMENT_1', 'AMENDEMENT_2'] if current_type_code == 'INITIAL' else ['AMENDEMENT_2']
            has_superior_amendment = CDR.objects.filter(
                cree_par=request.user,
                annee=current_cdr.annee,
                processus=current_cdr.processus,
                type_tableau__code__in=superior_types
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
    Récupérer le dernier CDR (INITIAL, AMENDEMENT_1 ou AMENDEMENT_2) de l'année précédente
    pour un processus donné.

    Query params:
    - annee: année actuelle (pour calculer l'année précédente)
    - processus: UUID du processus

    Retourne le dernier type de tableau (ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL)
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

        # Chercher tous les CDR de l'année précédente pour ce processus
        # Ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL
        codes_order = ['AMENDEMENT_2', 'AMENDEMENT_1', 'INITIAL']

        for code in codes_order:
            cdr = CDR.objects.filter(
                cree_par=request.user,
                annee=annee_precedente,
                processus__uuid=processus_uuid,
                type_tableau__code=code
            ).select_related('processus', 'type_tableau', 'cree_par', 'valide_par').first()

            if cdr:
                logger.info(f"[get_last_cdr_previous_year] CDR trouvé: {cdr.uuid} (type: {code})")
                serializer = CDRSerializer(cdr)
                return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun CDR trouvé pour l'année précédente
        logger.info(f"[get_last_cdr_previous_year] Aucun CDR trouvé pour l'année {annee_precedente}")
        return Response({
            'message': f'Aucune cartographie trouvée pour l\'année {annee_precedente}',
            'found': False
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier CDR de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération du CDR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

