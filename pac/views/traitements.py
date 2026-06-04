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

def traitement_list(request):
    """Liste des traitements"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les traitements sans filtre
            traitements = TraitementPac.objects.all().order_by('-delai_realisation')
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun traitement trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            traitements = TraitementPac.objects.filter(
                details_pac__pac__processus__uuid__in=user_processus_uuids
            ).order_by('-delai_realisation')
        # ========== FIN FILTRAGE ==========
        
        serializer = TraitementPacSerializer(traitements, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': traitements.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des traitements: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer les traitements'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACTraitementCreatePermission])
def traitement_create(request):
    """Créer un nouveau traitement"""
    try:
        logger.info(f"[traitement_create] Données reçues: {request.data}")
        
        # Vérifier si le PAC est validé avant la création
        if 'details_pac' in request.data:
            details_pac_uuid = request.data['details_pac']
            logger.info(f"[traitement_create] Recherche du DetailsPac avec UUID: {details_pac_uuid}")
            
            try:
                details_pac = DetailsPac.objects.select_related('pac').get(uuid=details_pac_uuid)
                logger.info(f"[traitement_create] DetailsPac trouvé: {details_pac.uuid}, PAC validé: {details_pac.pac.is_validated}")
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, details_pac.pac.processus.uuid):
                    return Response({
                        'success': False,
                        'error': 'Vous n\'avez pas accès à ce traitement. Vous n\'avez pas de rôle actif pour ce processus.'
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                # ========== VÉRIFICATION PERMISSION CREATE_TRAITEMENT (Security by Design) ==========
                # La permission est déjà vérifiée par le décorateur @permission_classes([PACTraitementCreatePermission])
                # Mais on vérifie explicitement ici aussi pour être sûr
                try:
                    traitement_create_permission = PACTraitementCreatePermission()
                    traitement_create_permission.has_permission(request, None)
                except PermissionDenied as e:
                    return Response({
                        'success': False,
                        'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un traitement."
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                # Vérifier si un traitement existe déjà pour ce détail
                existing_traitement = TraitementPac.objects.filter(details_pac=details_pac).first()
                if existing_traitement:
                    logger.warning(f"[traitement_create] Un traitement existe déjà pour ce détail: {existing_traitement.uuid}")
                    return Response({
                        'details_pac': ["Un traitement existe déjà pour ce détail PAC. Un détail ne peut avoir qu'un seul traitement."]
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if details_pac.pac.is_validated:
                    return Response({
                        'details_pac': ['Ce PAC est validé. Impossible de créer un nouveau traitement.']
                    }, status=status.HTTP_400_BAD_REQUEST)
            except DetailsPac.DoesNotExist:
                logger.error(f"[traitement_create] DetailsPac non trouvé avec UUID: {details_pac_uuid}")
                return Response({
                    'details_pac': [f'Aucun détail PAC trouvé avec l\'UUID fourni: {details_pac_uuid}']
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TraitementPacCreateSerializer(data=request.data)
        if serializer.is_valid():
            traitement = serializer.save()

            # Log de l'activité
            try:
                log_traitement_creation(
                    user=request.user,
                    traitement=traitement,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
            except Exception as log_error:
                logger.error(f"Erreur lors du log de création du traitement: {str(log_error)}")
                # Continue même si le log échoue

            # Sérialiser la réponse
            try:
                response_data = TraitementPacSerializer(traitement).data
                return Response(response_data, status=status.HTTP_201_CREATED)
            except Exception as serializer_error:
                logger.error(f"Erreur lors de la sérialisation du traitement créé: {str(serializer_error)}")
                import traceback
                logger.error(traceback.format_exc())
                # Le traitement a été créé, retourner au moins l'UUID
                return Response({
                    'uuid': str(traitement.uuid),
                    'action': traitement.action
                }, status=status.HTTP_201_CREATED)

        logger.error(f"[traitement_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du traitement: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer le traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def pac_traitements(request, uuid):
    """Récupérer les traitements d'un PAC spécifique"""
    try:
        pac = Pac.objects.select_related('processus').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce PAC. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les traitements du PAC via les détails (OneToOne)
        traitements = TraitementPac.objects.filter(details_pac__pac=pac).order_by('-delai_realisation')
        serializer = TraitementPacSerializer(traitements, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': traitements.count()
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'success': False,
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des traitements du PAC: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer les traitements'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def traitement_detail(request, uuid):
    """Récupérer un traitement spécifique"""
    try:
        traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, traitement.details_pac.pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce traitement. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        serializer = TraitementPacSerializer(traitement)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except TraitementPac.DoesNotExist:
        return Response({
            'error': 'Traitement non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACTraitementUpdatePermission])
def traitement_update(request, uuid):
    """Mettre à jour un traitement"""
    try:
        traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=uuid)
        
        # Protection : empêcher la modification si le PAC est validé
        if traitement.details_pac.pac.is_validated:
            return Response({
                'error': 'Ce PAC est validé. Les champs de traitement ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TraitementPacUpdateSerializer(traitement, data=request.data, partial=True)
        if serializer.is_valid():
            traitement = serializer.save()
            return Response(TraitementPacSerializer(traitement).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except TraitementPac.DoesNotExist:
        return Response({
            'error': 'Traitement non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de mettre à jour le traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API SUIVIS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_list(request):
    """Liste des suivis"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les suivis sans filtre
            suivis = PacSuivi.objects.all().order_by('-created_at')
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun suivi trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            suivis = PacSuivi.objects.filter(
                traitement__details_pac__pac__processus__uuid__in=user_processus_uuids
            ).order_by('-created_at')
        # ========== FIN FILTRAGE ==========
        
        serializer = PacSuiviSerializer(suivis, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': suivis.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des suivis: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer les suivis'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def traitement_suivis(request, uuid):
    """Récupérer les suivis d'un traitement PAC"""
    try:
        # Charger les relations nécessaires (OneToOne : un seul suivi par traitement)
        try:
            traitement = TraitementPac.objects.select_related('suivi', 'details_pac', 'details_pac__pac', 'details_pac__pac__processus').get(uuid=uuid)
            
            # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
            if not user_has_access_to_processus(request.user, traitement.details_pac.pac.processus.uuid):
                return Response({
                    'success': False,
                    'error': 'Vous n\'avez pas accès à ce traitement. Vous n\'avez pas de rôle actif pour ce processus.'
                }, status=status.HTTP_403_FORBIDDEN)
            # ========== FIN VÉRIFICATION ==========
            
            if hasattr(traitement, 'suivi') and traitement.suivi:
                suivi = traitement.suivi
                serializer = PacSuiviSerializer(suivi)
                return Response(serializer.data)
            else:
                return Response({
                    'message': 'Aucun suivi pour ce traitement',
                    'suivi': None
                }, status=status.HTTP_200_OK)
        except TraitementPac.DoesNotExist:
            return Response({
                'error': 'Traitement non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des suivis du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les suivis du traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACSuiviCreatePermission])
def suivi_create(request):
    """Créer un nouveau suivi"""
    try:
        # Permettre la création de suivi lors de la copie d'amendement (from_amendment_copy=True)
        from_amendment_copy = request.data.get('from_amendment_copy', False)
        
        # Vérifier si le traitement est dans un PAC validé avant la création
        # SAUF si c'est une copie d'amendement (dans ce cas, on permet la création même si le PAC n'est pas validé)
        if 'traitement' in request.data:
            try:
                traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=request.data['traitement'])
                if not traitement.details_pac.pac.is_validated and not from_amendment_copy:
                    return Response({
                        'error': 'Le PAC doit être validé avant de pouvoir créer un suivi. Veuillez d\'abord valider tous les détails et traitements du PAC.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except TraitementPac.DoesNotExist:
                pass  # La validation du serializer gérera cette erreur
        
        serializer = PacSuiviCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            statut = serializer.validated_data.get('statut')
            date_cloture = serializer.validated_data.get('date_cloture')
            if statut and statut.nom and 'clôtur' in statut.nom.lower() and not date_cloture:
                return Response({
                    'date_cloture': 'La date de clôture est requise lorsque le statut indique une clôture.'
                }, status=status.HTTP_400_BAD_REQUEST)

            suivi = serializer.save()

            # Log de l'activité
            try:
                log_suivi_creation(
                    user=request.user,
                    suivi=suivi,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
            except Exception as log_error:
                logger.error(f"Erreur lors du log de création du suivi: {str(log_error)}")
                # Continue même si le log échoue

            # Sérialiser la réponse
            try:
                response_data = PacSuiviSerializer(suivi).data
                return Response(response_data, status=status.HTTP_201_CREATED)
            except Exception as serializer_error:
                logger.error(f"Erreur lors de la sérialisation du suivi créé: {str(serializer_error)}")
                import traceback
                logger.error(traceback.format_exc())
                # Le suivi a été créé, retourner au moins l'UUID
                return Response({
                    'uuid': str(suivi.uuid),
                    'resultat': suivi.resultat
                }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du suivi: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer le suivi'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_detail(request, uuid):
    """Récupérer le détail d'un suivi"""
    try:
        suivi = PacSuivi.objects.select_related(
            'traitement', 'traitement__details_pac', 'traitement__details_pac__pac',
            'etat_mise_en_oeuvre', 'appreciation', 'preuve', 'statut'
        ).prefetch_related(
            'preuve__medias'
        ).get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, suivi.traitement.details_pac.pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce suivi. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        return Response({
            'success': True,
            'data': PacSuiviSerializer(suivi).data
        }, status=status.HTTP_200_OK)
    except PacSuivi.DoesNotExist:
        return Response({'error': 'Suivi non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du suivi: {str(e)}")
        return Response({'error': "Impossible de récupérer le suivi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACSuiviUpdatePermission])
def suivi_update(request, uuid):
    """Mettre à jour un suivi"""
    try:
        suivi = PacSuivi.objects.select_related('traitement', 'traitement__details_pac', 'traitement__details_pac__pac').get(uuid=uuid)
        
        # Protection : empêcher la modification si le PAC n'est pas validé
        if not suivi.traitement.details_pac.pac.is_validated:
            return Response({
                'error': 'Le PAC doit être validé avant de pouvoir modifier un suivi.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = PacSuiviUpdateSerializer(suivi, data=request.data, partial=True)
        if serializer.is_valid():
            statut = serializer.validated_data.get('statut', suivi.statut)
            date_cloture = serializer.validated_data.get('date_cloture')
            if statut and statut.nom and 'clôtur' in statut.nom.lower() and not (date_cloture or suivi.date_cloture):
                return Response({
                    'date_cloture': 'La date de clôture est requise lorsque le statut indique une clôture.'
                }, status=status.HTTP_400_BAD_REQUEST)

            suivi = serializer.save()
            return Response(PacSuiviSerializer(suivi).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        # DRF retournera automatiquement une réponse 403 avec le message approprié
        raise
    except PacSuivi.DoesNotExist:
        return Response({'error': 'Suivi non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du suivi: {str(e)}")
        return Response({'error': "Impossible de mettre à jour le suivi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API DETAILS PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def details_pac_list(request, uuid):
    """Liste des détails d'un PAC spécifique"""
    try:
        pac = Pac.objects.get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce PAC. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les détails du PAC
        details = DetailsPac.objects.filter(pac=pac).select_related(
            'pac', 'dysfonctionnement_recommandation', 'nature', 'categorie', 'source'
        ).order_by('periode_de_realisation')
        
        serializer = DetailsPacSerializer(details, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': details.count()
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les détails'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACDetailCreatePermission])
def details_pac_create(request):
    """Créer un nouveau détail de PAC"""
    try:
        logger.info(f"[details_pac_create] Données reçues: {request.data}")
        
        # Vérifier si le PAC est validé avant la création
        if 'pac' in request.data:
            try:
                pac = Pac.objects.get(uuid=request.data['pac'])
                logger.info(f"[details_pac_create] PAC trouvé: {pac.uuid}, validé: {pac.is_validated}")
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, pac.processus.uuid):
                    return Response({
                        'success': False,
                        'error': 'Vous n\'avez pas accès à ce PAC. Vous n\'avez pas de rôle actif pour ce processus.'
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                # ========== VÉRIFICATION PERMISSION CREATE_DETAIL_PAC (Security by Design) ==========
                # La permission est déjà vérifiée par le décorateur @permission_classes([PACDetailCreatePermission])
                # Mais on vérifie explicitement ici aussi pour être sûr
                try:
                    detail_create_permission = PACDetailCreatePermission()
                    detail_create_permission.has_permission(request, None)
                except PermissionDenied as e:
                    return Response({
                        'success': False,
                        'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un détail PAC."
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                if pac.is_validated:
                    return Response({
                        'error': 'Ce PAC est validé. Impossible de créer un nouveau détail.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except Pac.DoesNotExist:
                logger.error(f"[details_pac_create] PAC non trouvé avec UUID: {request.data['pac']}")
                pass  # La validation du serializer gérera cette erreur
        
        serializer = DetailsPacCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            detail = serializer.save()
            logger.info(f"[details_pac_create] ✅ Détail créé avec succès: {detail.uuid}")
            return Response(DetailsPacSerializer(detail).data, status=status.HTTP_201_CREATED)
        
        logger.error(f"[details_pac_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du détail: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def details_pac_detail(request, uuid):
    """Récupérer un détail spécifique"""
    try:
        detail = DetailsPac.objects.select_related(
            'pac', 'dysfonctionnement_recommandation', 'nature', 'categorie', 'source'
        ).get(uuid=uuid)
        
        serializer = DetailsPacSerializer(detail)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except DetailsPac.DoesNotExist:
        return Response({
            'error': 'Détail non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du détail: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACDetailUpdatePermission])
def details_pac_update(request, uuid):
    """Mettre à jour un détail de PAC"""
    try:
        detail = DetailsPac.objects.select_related('pac').get(uuid=uuid)
        
        # Protection : empêcher la modification si le PAC est validé
        if detail.pac.is_validated:
            return Response({
                'error': 'Ce PAC est validé. Les champs de détail ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DetailsPacUpdateSerializer(detail, data=request.data, partial=True)
        if serializer.is_valid():
            detail = serializer.save()
            return Response(DetailsPacSerializer(detail).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except DetailsPac.DoesNotExist:
        return Response({
            'error': 'Détail non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du détail: {str(e)}")
        return Response({
            'error': 'Impossible de mettre à jour le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, PACDetailDeletePermission])
def details_pac_delete(request, uuid):
    """Supprimer un détail de PAC"""
    try:
        detail = DetailsPac.objects.select_related('pac').get(uuid=uuid)

        # Vérifier que le PAC n'est pas validé
        if detail.pac.is_validated:
            return Response({
                'error': 'Impossible de supprimer un détail d\'un PAC validé'
            }, status=status.HTTP_400_BAD_REQUEST)

        detail_info = {
            'uuid': str(detail.uuid),
            'libelle': detail.libelle,
            'pac': detail.pac.uuid if detail.pac else None
        }

        # Suppression du détail
        detail.delete()
        
        return Response({
            'message': 'Détail supprimé avec succès',
            'detail': detail_info
        }, status=status.HTTP_200_OK)
    except DetailsPac.DoesNotExist:
        return Response({
            'error': 'Détail non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du détail: {str(e)}")
        return Response({
            'error': 'Impossible de supprimer le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

