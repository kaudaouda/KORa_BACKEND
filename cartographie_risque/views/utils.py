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
        logger.info("[_get_next_num_amendement_for_cdr] user=%s, annee=%s, processus_uuid=%s", user, annee, processus_uuid)
        existing = CDR.objects.filter(
            cree_par=user,
            annee=annee,
            processus_id=processus_uuid
        ).order_by('-num_amendement').first()
        if not existing:
            logger.info("[_get_next_num_amendement_for_cdr] Aucun CDR existant, retourne 0 (initial)")
            return 0
        next_num = existing.num_amendement + 1
        logger.info("[_get_next_num_amendement_for_cdr] Retourne %s", next_num)
        return next_num
    except Exception as e:
        logger.error("[_get_next_num_amendement_for_cdr] Erreur: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        raise


# ==================== ENDPOINTS API ====================

