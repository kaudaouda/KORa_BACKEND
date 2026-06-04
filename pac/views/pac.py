"""
Vues API pour l'application PAC
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from shared.throttles import KoraSensitiveThrottle
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime, timedelta
from pac.services.pac_service import check_pac_completude
from ..models import Pac, TraitementPac, PacSuivi, DetailsPac
from parametre.models import Processus, Media, Preuve, Notification, FailedLoginAttempt, LoginSecurityConfig, LoginBlock
from parametre.views import log_pac_creation, log_pac_update, log_traitement_creation, log_suivi_creation, log_user_login, log_user_logout, get_client_ip, log_activity
from parametre.utils.email_security import EmailValidator, EmailContentSanitizer, EmailRateLimiter, SecureEmailLogger
from parametre.utils.email_config import load_email_settings_into_django
from parametre.permissions import (
    check_permission_or_403,
    user_can_create_objectives_amendements,
    user_can_create_for_processus,
    get_user_processus_list,
    user_has_access_to_processus,
)
# Import des classes de permissions génériques PAC
from permissions.permissions import (
    PacListPermission,
    PacDetailPermission,
    PACCreatePermission,
    PACUpdatePermission,
    PACDeletePermission,
    PACValidatePermission,
    PACUnvalidatePermission,
    PACReadPermission,
    PACAmendementCreatePermission,
    PACDetailCreatePermission,
    PACDetailUpdatePermission,
    PACDetailDeletePermission,
    PACTraitementCreatePermission,
    PACTraitementUpdatePermission,
    PACTraitementDeletePermission,
    PACSuiviCreatePermission,
    PACSuiviUpdatePermission,
    PACSuiviDeletePermission,
)
from ..serializers import (
    UserSerializer, ProcessusSerializer, ProcessusCreateSerializer,
    PacSerializer, PacCreateSerializer, PacUpdateSerializer, PacCompletSerializer,
    TraitementPacSerializer, TraitementPacCreateSerializer, TraitementPacUpdateSerializer, 
    PacSuiviSerializer, PacSuiviCreateSerializer, PacSuiviUpdateSerializer,
    DetailsPacSerializer, DetailsPacCreateSerializer, DetailsPacUpdateSerializer
)
from shared.authentication import AuthService
from shared.services.recaptcha_service import recaptcha_service, RecaptchaValidationError
import json
import logging

logger = logging.getLogger(__name__)


from .utils import AllowAnyWithJWT, _get_next_num_amendement_for_pac

def processus_list(request):
    """Liste des processus de l'utilisateur connecté"""
    try:
        processus = Processus.objects.filter(cree_par=request.user).order_by('-created_at')
        serializer = ProcessusSerializer(processus, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des processus: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les processus'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def processus_create(request):
    """Créer un nouveau processus"""
    try:
        serializer = ProcessusCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            processus = serializer.save()
            return Response(ProcessusSerializer(processus).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du processus: {str(e)}")
        return Response({
            'error': 'Impossible de créer le processus'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processus_detail(request, uuid):
    """Détails d'un processus"""
    try:
        processus = Processus.objects.get(uuid=uuid)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus.uuid):
            return Response({
                'error': 'Vous n\'avez pas accès à ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        serializer = ProcessusSerializer(processus)
        return Response(serializer.data)
    except Processus.DoesNotExist:
        return Response({
            'error': 'Processus non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du processus: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le processus'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, PacListPermission])
def pac_list(request):
    """Liste des PACs de l'utilisateur connecté avec leurs détails"""
    try:
        logger.info(f"[pac_list] Utilisateur connecté: {request.user.username} (ID: {request.user.id})")

        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les PACs sans filtre
            pacs = Pac.objects.all().select_related(
            'processus', 'cree_par', 'annee', 'validated_by'
        ).prefetch_related(
            'details__dysfonctionnement_recommandation',
            'details__nature',
            'details__categorie',
            'details__source'
        )
        elif not user_processus_uuids:
            logger.info(f"[pac_list] Aucun processus assigné pour l'utilisateur {request.user.username}")
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun PAC trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Filtrer les PACs par les processus où l'utilisateur a un rôle actif
            pacs = Pac.objects.filter(processus__uuid__in=user_processus_uuids).select_related(
                'processus', 'cree_par', 'annee', 'validated_by'
            ).prefetch_related(
                'details__dysfonctionnement_recommandation',
                'details__nature',
                'details__categorie',
                'details__source'
            )
        # ========== FIN FILTRAGE ==========

        logger.info(f"[pac_list] Nombre de PACs pour l'utilisateur {request.user.username}: {pacs.count()}")

        # Utiliser PacCompletSerializer pour inclure les détails
        serializer = PacCompletSerializer(pacs, many=True)
        logger.info(f"[pac_list] Données sérialisées: {len(serializer.data)} PACs")
        return Response({
            'success': True,
            'data': serializer.data,
            'count': pacs.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des PACs: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les PACs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACCreatePermission])
def pac_create(request):
    """
    Créer un nouveau PAC.
    Validation stricte: un seul PAC par (processus, annee, num_amendement).
    Retourne 400 si doublon.
    """
    try:
        logger.info(f"[pac_create] Données reçues: {request.data}")
        data = request.data.copy()
        clone = str(data.pop('clone', 'false')).lower() in ['1', 'true', 'yes', 'on']

        annee_uuid = data.get('annee')
        processus_uuid = data.get('processus')
        try:
            num_amendement = int(data.get('num_amendement', 0))
        except (ValueError, TypeError):
            num_amendement = 0

        if not annee_uuid or not processus_uuid:
            return Response({
                'success': False,
                'error': "Les champs 'annee' et 'processus' sont requis."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': "Vous n'avez pas accès à ce processus. Vous n'avez pas de rôle actif pour ce processus."
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # VALIDATION 1 : Si INITIAL (num_amendement == 0), vérifier qu'il n'existe pas déjà
        if num_amendement == 0:
            existing = Pac.objects.filter(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=0
            ).exists()
            if existing:
                return Response({
                    'success': False,
                    'error': "Un PAC initial existe déjà pour cette année et ce processus. Vous ne pouvez créer que des amendements."
                }, status=status.HTTP_400_BAD_REQUEST)

        # VALIDATION 2 : Si amendement, vérifier que le précédent existe et est validé
        else:
            prev_num = num_amendement - 1
            try:
                pac_prev = Pac.objects.get(
                    annee_id=annee_uuid,
                    processus_id=processus_uuid,
                    num_amendement=prev_num
                )
            except Pac.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f"Impossible de créer l'amendement {num_amendement} : l'amendement {prev_num} n'existe pas pour cette année et ce processus."
                }, status=status.HTTP_400_BAD_REQUEST)
            if not pac_prev.is_validated:
                return Response({
                    'success': False,
                    'error': f"Impossible de créer l'amendement {num_amendement} : l'amendement {prev_num} doit être validé d'abord."
                }, status=status.HTTP_400_BAD_REQUEST)
            existing_num = Pac.objects.filter(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=num_amendement
            ).exists()
            if existing_num:
                return Response({
                    'success': False,
                    'error': f"L'amendement {num_amendement} existe déjà pour cette année et ce processus."
                }, status=status.HTTP_400_BAD_REQUEST)
            # initial_ref = le PAC initial (num_amendement == 0)
            pac_initial = Pac.objects.get(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=0
            )
            data['initial_ref'] = str(pac_initial.uuid)

        data['num_amendement'] = num_amendement

        # ========== CRÉATION ==========
        serializer = PacCreateSerializer(data=data, context={'request': request})
        if not serializer.is_valid():
            logger.error(f"[pac_create] Erreurs de validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pac = serializer.save()
        logger.info(f"[pac_create] PAC créé: {pac.uuid}")

        log_pac_creation(
            user=request.user,
            pac=pac,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        # Clone des détails si amendement et clone demandé
        if num_amendement > 0 and clone:
            # Source = PAC du numéro précédent
            source_pac = Pac.objects.filter(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=num_amendement - 1
            ).first()
            if source_pac:
                details_with_suivi = source_pac.details.select_related(
                    'traitement', 'traitement__suivi',
                    'traitement__suivi__etat_mise_en_oeuvre', 'traitement__suivi__appreciation',
                    'traitement__suivi__preuve', 'traitement__suivi__statut'
                ).all()
                clone_count = 0
                for detail in details_with_suivi:
                    new_detail = DetailsPac.objects.create(
                        pac=pac,
                        numero_pac=detail.numero_pac,
                        libelle=detail.libelle,
                        dysfonctionnement_recommandation=detail.dysfonctionnement_recommandation,
                        nature=detail.nature,
                        categorie=detail.categorie,
                        source=detail.source,
                        periode_de_realisation=detail.periode_de_realisation,
                    )
                    if hasattr(detail, 'traitement') and detail.traitement:
                        t = detail.traitement
                        new_traitement = TraitementPac.objects.create(
                            details_pac=new_detail,
                            action=t.action,
                            type_action=t.type_action,
                            delai_realisation=t.delai_realisation,
                            responsable_direction=t.responsable_direction,
                            responsable_sous_direction=t.responsable_sous_direction,
                        )
                        if hasattr(t, 'responsables_directions'):
                            new_traitement.responsables_directions.set(t.responsables_directions.all())
                        if hasattr(t, 'responsables_sous_directions'):
                            new_traitement.responsables_sous_directions.set(t.responsables_sous_directions.all())
                        # Copier le suivi si présent
                        if hasattr(t, 'suivi') and t.suivi:
                            s = t.suivi
                            if s.etat_mise_en_oeuvre and s.appreciation:
                                # Chaque amendement repart avec sa propre preuve vide :
                                # partager s.preuve ferait apparaître les médias ajoutés
                                # sur le nouvel amendement dans tous les précédents.
                                PacSuivi.objects.create(
                                    traitement=new_traitement,
                                    etat_mise_en_oeuvre=s.etat_mise_en_oeuvre,
                                    resultat=s.resultat,
                                    appreciation=s.appreciation,
                                    preuve=None,
                                    statut=s.statut,
                                    date_mise_en_oeuvre_effective=s.date_mise_en_oeuvre_effective,
                                    date_cloture=s.date_cloture,
                                    cree_par=request.user,
                                )
                    clone_count += 1
                # Audit: log du clonage (Security by Design)
                if clone_count > 0:
                    try:
                        log_activity(
                            user=request.user,
                            action='clone',
                            entity_type='pac',
                            entity_id=str(pac.uuid),
                            entity_name=f"PAC {pac.uuid}",
                            description=f"Clonage d'amendement depuis {source_pac.uuid} (amendement {num_amendement - 1}) - {clone_count} détails copiés",
                            ip_address=get_client_ip(request),
                            user_agent=request.META.get('HTTP_USER_AGENT')
                        )
                    except Exception as log_err:
                        logger.warning(f"[pac_create] Erreur log clonage: {log_err}")

        return Response({
            'success': True,
            'message': 'PAC créé avec succès',
            'data': PacSerializer(pac).data
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        import traceback
        logger.error(f"[pac_create] Erreur: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'success': False,
            'error': 'Impossible de créer le PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PacDetailPermission])
def pac_detail(request, uuid):
    """Détails d'un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid)
        
        serializer = PacSerializer(pac)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'success': False,
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du PAC: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer le PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PacDetailPermission])
def pac_complet(request, uuid):
    """Récupérer un PAC complet avec tous ses traitements et suivis"""
    try:
        pac = Pac.objects.select_related(
            'processus', 'cree_par', 'annee'
        ).prefetch_related(
            'details__dysfonctionnement_recommandation',
            'details__nature',
            'details__categorie',
            'details__source',
            'details__traitement__type_action',
            'details__traitement__responsable_direction',
            'details__traitement__responsable_sous_direction',
            'details__traitement__preuve__medias',
            'details__traitement__suivi__etat_mise_en_oeuvre',
            'details__traitement__suivi__appreciation',
            'details__traitement__suivi__statut',
            'details__traitement__suivi__cree_par',
            'details__traitement__suivi__preuve__medias'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par PacDetailPermission
        # via le décorateur @permission_classes
        
        serializer = PacCompletSerializer(pac)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'success': False,
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du PAC complet: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer le PAC complet'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACCreatePermission])
def pac_get_or_create(request):
    """
    Récupérer ou créer un PAC unique pour (processus, annee, num_amendement).
    Si num_amendement est absent, le calcule automatiquement.
    """
    try:
        logger.info(f"[pac_get_or_create] Début - données reçues: {request.data}")
        data = request.data

        def _to_uuid(val):
            if val is None:
                return None
            if isinstance(val, str) and val.strip():
                return val.strip()
            if hasattr(val, 'uuid'):
                return str(getattr(val, 'uuid'))
            if isinstance(val, dict) and val.get('uuid'):
                return str(val['uuid'])
            return str(val) if val else None

        annee_uuid = _to_uuid(data.get('annee'))
        processus_uuid = _to_uuid(data.get('processus'))
        initial_ref_uuid = _to_uuid(data.get('initial_ref'))

        # Résoudre num_amendement
        raw_num = data.get('num_amendement')
        if raw_num is not None:
            try:
                num_amendement = int(raw_num)
            except (ValueError, TypeError):
                num_amendement = None
        else:
            num_amendement = None

        logger.info(f"[pac_get_or_create] annee_uuid={annee_uuid}, processus_uuid={processus_uuid}, num_amendement={num_amendement}")

        if not (annee_uuid and processus_uuid):
            logger.warning("[pac_get_or_create] annee ou processus manquant")
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis. 'num_amendement' peut être omis et sera déterminé automatiquement."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': "Vous n'avez pas accès à ce processus. Vous n'avez pas de rôle actif pour ce processus."
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Auto-calculer num_amendement si absent
        if num_amendement is None:
            logger.info("[pac_get_or_create] num_amendement absent, calcul automatique")
            try:
                num_amendement = _get_next_num_amendement_for_pac(request.user, annee_uuid, processus_uuid)
                logger.info(f"[pac_get_or_create] num_amendement automatique: {num_amendement}")
            except Exception as tt_error:
                logger.error(f"[pac_get_or_create] Erreur calcul num_amendement: {tt_error}")
                import traceback
                logger.error(traceback.format_exc())
                return Response({
                    'error': 'Impossible de déterminer le numéro d\'amendement.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ========== VÉRIFICATION DES PERMISSIONS ==========
        is_creating_amendement = (num_amendement > 0) or bool(initial_ref_uuid)
        if is_creating_amendement:
            amendement_permission = PACAmendementCreatePermission()
            if not amendement_permission.has_permission(request, None):
                return Response({
                    'success': False,
                    'error': "Vous n'avez pas les permissions nécessaires pour créer un amendement PAC."
                }, status=status.HTTP_403_FORBIDDEN)
        else:
            try:
                pac_create_permission = PACCreatePermission()
                pac_create_permission.has_permission(request, None)
            except PermissionDenied as e:
                return Response({
                    'success': False,
                    'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un PAC."
                }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION DES PERMISSIONS ==========

        # Vérifier si un PAC existe déjà avec ce (processus, annee, num_amendement)
        try:
            pac = Pac.objects.get(
                processus__uuid=processus_uuid,
                annee__uuid=annee_uuid,
                num_amendement=num_amendement,
            )
            logger.info(f"[pac_get_or_create] PAC existant trouvé: {pac.uuid}")
            serializer = PacSerializer(pac)
            response_data = dict(serializer.data)
            response_data['created'] = False
            return Response(response_data, status=status.HTTP_200_OK)

        except Pac.DoesNotExist:
            logger.info(f"[pac_get_or_create] Aucun PAC existant, création d'un nouveau PAC")

            from django.http import QueryDict
            if isinstance(data, QueryDict):
                data = data.copy()
            elif not isinstance(data, dict):
                data = dict(data) if hasattr(data, 'items') else {}

            # Pour un amendement, trouver/valider l'initial_ref automatiquement
            if num_amendement > 0 and not initial_ref_uuid:
                pac_initial = Pac.objects.filter(
                    annee_id=annee_uuid,
                    processus_id=processus_uuid,
                    num_amendement=0
                ).first()
                if not pac_initial:
                    return Response({
                        'error': 'Aucun PAC initial trouvé pour créer cet amendement. Veuillez d\'abord créer et valider un PAC initial.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                if not pac_initial.is_validated:
                    return Response({
                        'error': 'Le PAC initial doit être validé avant de pouvoir créer un amendement.',
                        'initial_pac_uuid': str(pac_initial.uuid)
                    }, status=status.HTTP_400_BAD_REQUEST)
                initial_ref_uuid = str(pac_initial.uuid)
            elif num_amendement > 0 and initial_ref_uuid:
                try:
                    pac_initial = Pac.objects.get(uuid=initial_ref_uuid)
                    if not pac_initial.is_validated:
                        return Response({
                            'error': 'Le PAC initial doit être validé avant de pouvoir créer un amendement.',
                            'initial_pac_uuid': str(initial_ref_uuid)
                        }, status=status.HTTP_400_BAD_REQUEST)
                except Pac.DoesNotExist:
                    return Response({
                        'error': 'Le PAC initial spécifié n\'existe pas.'
                    }, status=status.HTTP_400_BAD_REQUEST)

            create_payload = {
                'processus': processus_uuid,
                'annee': annee_uuid,
                'num_amendement': num_amendement,
            }
            if initial_ref_uuid:
                create_payload['initial_ref'] = initial_ref_uuid
            logger.info(f"[pac_get_or_create] Payload création: {create_payload}")
            create_serializer = PacCreateSerializer(data=create_payload, context={'request': request})

            if create_serializer.is_valid():
                logger.info("[pac_get_or_create] Serializer valide, sauvegarde...")
                try:
                    pac = create_serializer.save()
                    logger.info(f"[pac_get_or_create] PAC créé avec succès: {pac.uuid}")
                except Exception as save_error:
                    logger.error(f"[pac_get_or_create] Erreur lors de la sauvegarde: {save_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    if 'UNIQUE constraint' in str(save_error):
                        try:
                            pac = Pac.objects.get(
                                processus__uuid=processus_uuid,
                                annee__uuid=annee_uuid,
                                num_amendement=num_amendement,
                            )
                            serializer = PacSerializer(pac)
                            response_data = dict(serializer.data)
                            response_data['created'] = False
                            return Response(response_data, status=status.HTTP_200_OK)
                        except Pac.DoesNotExist:
                            pass
                    return Response({
                        'error': 'Erreur lors de la sauvegarde du PAC',
                        'details': str(save_error)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                try:
                    log_pac_creation(
                        user=request.user,
                        pac=pac,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT')
                    )
                except Exception as log_error:
                    logger.error(f"[pac_get_or_create] Erreur log (non bloquant): {log_error}")

                try:
                    serializer = PacSerializer(pac)
                    response_data = dict(serializer.data)
                    response_data['created'] = True
                    return Response(response_data, status=status.HTTP_201_CREATED)
                except Exception as serializer_error:
                    logger.error(f"[pac_get_or_create] Erreur sérialisation: {serializer_error}")
                    return Response({
                        'error': 'Erreur lors de la sérialisation du PAC',
                        'details': str(serializer_error)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            logger.error(f"[pac_get_or_create] Erreurs de validation: {create_serializer.errors}")
            return Response(create_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"[pac_get_or_create] Erreur exception non gérée: {str(e)}")
        import traceback
        logger.error(f"[pac_get_or_create] Traceback: {traceback.format_exc()}")
        return Response({
            'error': 'Impossible de traiter la demande',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACUpdatePermission])
def pac_update(request, uuid):
    """Mettre à jour un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid)
        
        # Protection : empêcher la modification du processus après création
        if 'processus' in request.data:
            return Response({
                'error': 'Le processus ne peut pas être modifié après la création du PAC'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Protection : empêcher la modification si le PAC est validé
        if pac.is_validated:
            return Response({
                'error': 'Ce PAC est validé. Les champs ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = PacUpdateSerializer(pac, data=request.data, partial=True)
        if serializer.is_valid():
            updated_pac = serializer.save()
            
            # Log de l'activité
            log_pac_update(
                user=request.user,
                pac=updated_pac,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return Response(PacSerializer(updated_pac).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de mettre à jour le PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, PACDeletePermission])
def pac_delete(request, uuid):
    """Supprimer un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid)

        # Récupérer le premier détail pour avoir un libellé (si existant)
        premier_detail = pac.details.first()
        libelle = premier_detail.libelle if premier_detail else 'N/A'

        pac_info = {
            'uuid': str(pac.uuid),
            'libelle': libelle,
            'processus': pac.processus.nom if pac.processus else None
        }

        # Log de l'activité avant suppression
        logger.info(
            f"Suppression PAC - User: {request.user.email}, "
            f"PAC: {pac_info['libelle']}, UUID: {pac_info['uuid']}, "
            f"IP: {get_client_ip(request)}"
        )

        # Suppression du PAC (cascade sur traitements et suivis)
        pac.delete()

        return Response({
            'message': 'PAC supprimé avec succès',
            'pac': pac_info
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de supprimer le PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _check_pac_completude(pac, numero_pac_display=None):
    """Délègue au service métier. Retourne None si tout est OK, sinon un message d'erreur."""
    return check_pac_completude(pac)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACValidatePermission])
def pac_validate(request, uuid):
    """Valider un PAC (verrouille les champs PAC et Traitement)"""
    try:
        pac = Pac.objects.select_related('validated_by', 'cree_par').get(uuid=uuid)
        
        # Vérifier si le PAC est déjà validé
        if pac.is_validated:
            return Response({
                'error': 'Ce PAC est déjà validé',
                'validated_at': pac.validated_at,
                'validated_by': f"{pac.validated_by.first_name} {pac.validated_by.last_name}".strip() or pac.validated_by.username if pac.validated_by else None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que tous les champs obligatoires sont renseignés
        error_msg = _check_pac_completude(pac)
        if error_msg:
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        # Valider le PAC
        from django.utils import timezone
        pac.is_validated = True
        pac.validated_at = timezone.now()
        pac.validated_by = request.user
        pac.save()
        
        logger.info(
            f"PAC validé par {request.user.username}: "
            f"PAC UUID: {uuid}, "
            f"IP: {get_client_ip(request)}"
        )
        
        return Response(PacSerializer(pac).data, status=status.HTTP_200_OK)
        
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la validation du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de valider le PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACValidatePermission])
def pac_validate_by_type(request):
    """Valider tous les PACs d'un même amendement (processus, année, num_amendement)"""
    try:
        processus_uuid = request.data.get('processus')
        annee_uuid = request.data.get('annee')
        try:
            num_amendement = int(request.data.get('num_amendement', 0))
        except (ValueError, TypeError):
            num_amendement = 0

        if not all([processus_uuid, annee_uuid]):
            return Response({
                'error': 'processus et annee sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer tous les PACs du même contexte (processus, année, num_amendement)
        pacs_to_validate = Pac.objects.filter(
            processus__uuid=processus_uuid,
            annee__uuid=annee_uuid,
            num_amendement=num_amendement
        ).select_related('processus', 'annee').prefetch_related('details__traitement')
        
        if not pacs_to_validate.exists():
            return Response({
                'error': 'Aucun PAC trouvé pour ce contexte'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Vérifier que tous les PACs peuvent être validés
        errors = []
        for pac in pacs_to_validate:
            if pac.is_validated:
                continue  # Déjà validé, on continue

            first_detail = pac.details.first()
            numero_pac_display = first_detail.numero_pac if first_detail and first_detail.numero_pac else str(pac.uuid)

            error_msg = _check_pac_completude(pac, numero_pac_display)
            if error_msg:
                errors.append(error_msg)
        
        if errors:
            return Response({
                'error': 'Certains PACs ne peuvent pas être validés',
                'details': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider tous les PACs
        from django.utils import timezone
        validated_count = 0
        for pac in pacs_to_validate:
            if not pac.is_validated:
                pac.is_validated = True
                pac.validated_at = timezone.now()
                pac.validated_by = request.user
                pac.save()
                validated_count += 1
        
        logger.info(
            f"{validated_count} PAC(s) validé(s) par {request.user.username}: "
            f"processus={processus_uuid}, annee={annee_uuid}, num_amendement={num_amendement}, "
            f"IP: {get_client_ip(request)}"
        )
        
        return Response({
            'message': f'{validated_count} PAC(s) validé(s) avec succès',
            'validated_count': validated_count,
            'total_count': pacs_to_validate.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la validation par amendement: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de valider les PACs',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACUnvalidatePermission])
def pac_unvalidate(request, uuid):
    """Dévalider un PAC (déverrouille les champs)"""
    try:
        pac = Pac.objects.select_related('validated_by', 'cree_par').get(uuid=uuid)
        
        # Vérifier si le PAC n'est pas validé
        if not pac.is_validated:
            return Response({
                'error': 'Ce PAC n\'est pas validé'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dévalider le PAC (même s'il y a des suivis, l'utilisateur avec la permission peut dévalider)
        pac.is_validated = False
        pac.validated_at = None
        pac.validated_by = None
        pac.save()
        
        return Response(PacSerializer(pac).data, status=status.HTTP_200_OK)
        
    except Pac.DoesNotExist:
        logger.error(f"Tentative de dévalidation d'un PAC inexistant: {uuid} par {request.user.username}")
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la dévalidation du PAC {uuid}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de dévalider le PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

