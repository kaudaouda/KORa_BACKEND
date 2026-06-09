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
from pac.services.pac_service import get_upcoming_notifications_data
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_upcoming_notifications(request):
    """Récupérer les traitements bientôt à terme pour les notifications."""
    try:
        data = get_upcoming_notifications_data(request.user)
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des notifications PAC: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        return Response(
            {'success': False, 'notifications': [], 'error': 'Erreur lors de la récupération des notifications'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== STATISTIQUES PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_stats(request):
    """Statistiques des PACs de l'utilisateur connecté"""
    try:
        from django.db.models import Q, Exists, OuterRef, Max

        scope = request.query_params.get('scope', 'tous')

        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)

        if user_processus_uuids is None:
            # Super admin : tous les PACs, filtre processus optionnel
            pacs_base = Pac.objects.all()
            processus_filter = request.query_params.get('processus')
            if processus_filter and str(processus_filter).upper() != 'ALL':
                try:
                    from uuid import UUID
                    UUID(str(processus_filter))
                    pacs_base = pacs_base.filter(processus__uuid=processus_filter)
                except (ValueError, TypeError):
                    pass
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': {
                    'total_pacs': 0, 'pacs_valides': 0,
                    'pacs_avec_traitement': 0, 'pacs_avec_suivi': 0,
                    'total_traitements': 0, 'total_suivis': 0,
                    'traitements_arrives_termes': 0, 'traitements_bientot_termes': 0,
                },
                'message': 'Aucune donnée de PAC trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            pacs_base = Pac.objects.filter(processus__uuid__in=user_processus_uuids)
            processus_uuid_filter = request.query_params.get('processus_uuid')
            if processus_uuid_filter and str(processus_uuid_filter) in [str(u) for u in user_processus_uuids]:
                pacs_base = pacs_base.filter(processus__uuid=processus_uuid_filter)
        # ========== FIN FILTRAGE ==========

        # Scope : dernier amendement par processus ou PAC initial uniquement
        if scope == 'dernier':
            last_uuids = []
            for proc_uuid in pacs_base.values_list('processus', flat=True).distinct():
                max_num = pacs_base.filter(processus=proc_uuid).aggregate(m=Max('num_amendement'))['m']
                last = pacs_base.filter(processus=proc_uuid, num_amendement=max_num).first()
                if last:
                    last_uuids.append(last.uuid)
            pacs_initiaux_base = pacs_base.filter(uuid__in=last_uuids)
        else:
            pacs_initiaux_base = pacs_base.filter(num_amendement=0)

        total_pacs = pacs_initiaux_base.count()

        # Security by Design — Fail Secure : comptage ORM pur, pas de boucle Python.
        # Q(is_validated=True) couvre le cas normal.
        # Q(validated_at__isnull=False) couvre les PACs validés avant l'ajout du booléen
        # (défense en profondeur contre toute incohérence de migration).
        pacs_valides = pacs_initiaux_base.filter(
            Q(is_validated=True) | Q(validated_at__isnull=False)
        ).count()

        # PACs avec au moins un traitement — sous-requête EXISTS, O(1) en DB
        pacs_avec_traitement = pacs_base.filter(
            Exists(
                DetailsPac.objects.filter(
                    pac=OuterRef('pk'),
                    traitement__isnull=False,
                )
            )
        ).count()

        # PACs avec au moins un suivi — idem
        pacs_avec_suivi = pacs_base.filter(
            Exists(
                DetailsPac.objects.filter(
                    pac=OuterRef('pk'),
                    traitement__suivi__isnull=False,
                )
            )
        ).count()

        pacs_initiaux_uuids = list(pacs_initiaux_base.values_list('uuid', flat=True))

        if not pacs_initiaux_uuids:
            total_traitements = 0
            total_suivis = 0
            traitements_arrives_termes = 0
            traitements_bientot_termes = 0
        else:
            today = timezone.now().date()
            base_filter = dict(
                details_pac__isnull=False,
                details_pac__pac__uuid__in=pacs_initiaux_uuids,
            )

            total_traitements = TraitementPac.objects.filter(**base_filter).count()

            total_suivis = PacSuivi.objects.filter(
                traitement__isnull=False,
                traitement__details_pac__isnull=False,
                traitement__details_pac__pac__uuid__in=pacs_initiaux_uuids,
            ).count()

            # Deux COUNT(*) WHERE au lieu d'une boucle Python sur N traitements
            traitements_arrives_termes = TraitementPac.objects.filter(
                **base_filter,
                delai_realisation__isnull=False,
                delai_realisation__lt=today,
            ).count()

            traitements_bientot_termes = TraitementPac.objects.filter(
                **base_filter,
                delai_realisation__isnull=False,
                delai_realisation__gte=today,
                delai_realisation__lte=today + timedelta(days=7),
            ).count()

        return Response({
            'success': True,
            'data': {
                'total_pacs': total_pacs,
                'pacs_valides': pacs_valides,
                'pacs_avec_traitement': pacs_avec_traitement,
                'pacs_avec_suivi': pacs_avec_suivi,
                'total_traitements': total_traitements,
                'total_suivis': total_suivis,
                'traitements_arrives_termes': traitements_arrives_termes,
                'traitements_bientot_termes': traitements_bientot_termes,
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        logger.error("Erreur lors de la récupération des statistiques PAC: %s\n%s", str(e), traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des statistiques PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_dashboard_stats(request):
    """
    Statistiques agrégées pour le dashboard — 4 requêtes DB au lieu de 51+.
    Remplace les appels séquentiels de dashboardSlice.js (N+1 sur PACs/traitements/suivis).
    """
    try:
        from parametre.models import NotificationSettings
        from datetime import timedelta

        notif_settings = NotificationSettings.get_solo()
        delai_jours = notif_settings.traitement_delai_notice_days
        today = timezone.now().date()
        date_limite = today + timedelta(days=delai_jours)

        # Security by Design : même logique de filtrage que pac_list
        user_processus_uuids = get_user_processus_list(request.user)

        if user_processus_uuids is None:
            pacs_qs = Pac.objects.filter(num_amendement=0)
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': {
                    'pac_count': 0,
                    'traitements_arrives_terme': 0,
                    'traitements_bientot_terme': 0,
                    'suivis_count': 0,
                    'delai_alerte_jours': delai_jours,
                }
            }, status=status.HTTP_200_OK)
        else:
            pacs_qs = Pac.objects.filter(
                processus__uuid__in=user_processus_uuids,
                num_amendement=0
            )

        pacs_uuids = list(pacs_qs.values_list('uuid', flat=True))
        pac_count = len(pacs_uuids)

        if not pacs_uuids:
            return Response({
                'success': True,
                'data': {
                    'pac_count': 0,
                    'traitements_arrives_terme': 0,
                    'traitements_bientot_terme': 0,
                    'suivis_count': 0,
                    'delai_alerte_jours': delai_jours,
                }
            }, status=status.HTTP_200_OK)

        base_filter = {
            'details_pac__isnull': False,
            'details_pac__pac__uuid__in': pacs_uuids,
            'delai_realisation__isnull': False,
        }

        traitements_arrives_terme = TraitementPac.objects.filter(
            **base_filter,
            delai_realisation__lt=today
        ).count()

        traitements_bientot_terme = TraitementPac.objects.filter(
            **base_filter,
            delai_realisation__gte=today,
            delai_realisation__lte=date_limite
        ).count()

        suivis_count = PacSuivi.objects.filter(
            traitement__isnull=False,
            traitement__details_pac__isnull=False,
            traitement__details_pac__pac__uuid__in=pacs_uuids,
        ).count()

        return Response({
            'success': True,
            'data': {
                'pac_count': pac_count,
                'traitements_arrives_terme': traitements_arrives_terme,
                'traitements_bientot_terme': traitements_bientot_terme,
                'suivis_count': suivis_count,
                'delai_alerte_jours': delai_jours,
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("[pac_dashboard_stats] Erreur: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors du calcul des statistiques dashboard'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_pac_previous_year(request):
    """
    Récupérer le dernier PAC (INITIAL, AMENDEMENT_1 ou AMENDEMENT_2) de l'année précédente
    pour un processus donné.

    Query params:
    - annee: UUID de l'année actuelle
    - processus: UUID du processus

    Retourne le dernier type de tableau (ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL)
    """
    try:
        from parametre.models import Annee

        annee_uuid = request.query_params.get('annee')
        processus_uuid = request.query_params.get('processus')

        if not annee_uuid or not processus_uuid:
            return Response({
                'error': 'Les paramètres annee et processus sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer l'année actuelle et calculer l'année précédente
        try:
            annee_actuelle = Annee.objects.get(uuid=annee_uuid)
            annee_precedente_valeur = annee_actuelle.annee - 1
            annee_precedente = Annee.objects.get(annee=annee_precedente_valeur)
        except Annee.DoesNotExist:
            logger.info("[get_last_pac_previous_year] Année précédente %s non trouvée", (annee_precedente_valeur if 'annee_precedente_valeur' in locals() else 'N/A'))
            return Response({
                'message': f'Aucune année {annee_precedente_valeur if "annee_precedente_valeur" in locals() else "précédente"} trouvée dans le système',
                'found': False,
                'data': None
            }, status=status.HTTP_200_OK)

        logger.info("[get_last_pac_previous_year] Recherche du dernier PAC pour processus=%s, année=%s", processus_uuid, annee_precedente.annee)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce processus. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Récupérer le PAC avec le num_amendement le plus élevé pour l'année précédente
        pac = Pac.objects.filter(
            annee=annee_precedente,
            processus__uuid=processus_uuid,
        ).select_related('processus', 'annee', 'cree_par', 'validated_by').order_by('-num_amendement').first()

        if pac:
            logger.info("[get_last_pac_previous_year] PAC trouvé: %s (num_amendement=%s)", pac.uuid, pac.num_amendement)
            serializer = PacSerializer(pac)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun PAC trouvé pour l'année précédente (200 pour que le frontend ne voit pas 404)
        logger.info("[get_last_pac_previous_year] Aucun PAC trouvé pour l'année %s", annee_precedente.annee)
        return Response({
            'message': f'Aucun Plan d\'Action de Conformité trouvé pour l\'année {annee_precedente.annee}',
            'found': False,
            'data': None
        }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        logger.error("Erreur lors de la récupération du dernier PAC de l'année précédente: %s\n%s", str(e), traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération du PAC',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
