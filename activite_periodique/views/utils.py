from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from ..models import ActivitePeriodique, DetailsAP, SuivisAP
from permissions.permissions import (
    ActivitePeriodiqueListPermission,
    ActivitePeriodiqueCreatePermission,
    ActivitePeriodiqueUpdatePermission,
    ActivitePeriodiqueDeletePermission,
    ActivitePeriodiqueValidatePermission,
    ActivitePeriodiqueUnvalidatePermission,
    ActivitePeriodiqueReadPermission,
    ActivitePeriodiqueDetailPermission,
    ActivitePeriodiqueAmendementCreatePermission,
    ActivitePeriodiqueDetailCreatePermission,
    ActivitePeriodiqueDetailUpdatePermission,
    ActivitePeriodiqueDetailDeletePermission,
    ActivitePeriodiqueSuiviCreatePermission,
    ActivitePeriodiqueSuiviUpdatePermission,
    ActivitePeriodiqueSuiviDeletePermission,
)
from ..serializers import (
    ActivitePeriodiqueSerializer,
    ActivitePeriodiqueCompletSerializer,
    DetailsAPSerializer,
    DetailsAPCreateSerializer,
    SuivisAPSerializer,
    SuivisAPCreateSerializer,
    MediaLivrableSerializer,
    MediaLivrableCreateSerializer,
    MediaLivrableUpdateSerializer,
)
from parametre.models import Media
try:
    from parametre.models import MediaLivrable
except (ImportError, AttributeError):
    MediaLivrable = None
from parametre.models import Processus, Annee
from parametre.views import (
    log_activite_periodique_creation,
    log_activite_periodique_update,
    log_activite_periodique_validation,
    get_client_ip,
)
from parametre.permissions import check_permission_or_403, get_user_processus_list, user_has_access_to_processus
import logging

logger = logging.getLogger(__name__)

# ==================== UTILITAIRES TYPE TABLEAU ====================

def _has_amendements_following(ap):
    """Vérifier si un AP a un amendement suivant (num_amendement + 1 existe)."""
    try:
        return ActivitePeriodique.objects.filter(
            processus=ap.processus,
            annee=ap.annee,
            cree_par=ap.cree_par,
            num_amendement=ap.num_amendement + 1
        ).exists()
    except Exception as e:
        logger.error("Erreur dans _has_amendements_following: %s", str(e))
        return False


def _get_next_num_amendement_for_ap(user, annee, processus_uuid):
    """
    Retourne le prochain num_amendement à utiliser pour (annee, processus, user).
    0 si aucun AP n'existe encore, sinon max_existant + 1.
    """
    try:
        logger.info("[_get_next_num_amendement_for_ap] user=%s, annee=%s, processus_uuid=%s", user, annee, processus_uuid)
        existing = ActivitePeriodique.objects.filter(
            cree_par=user,
            annee__annee=annee,
            processus_id=processus_uuid
        ).order_by('-num_amendement').first()
        if not existing:
            logger.info("[_get_next_num_amendement_for_ap] Aucun AP existant, retourne 0 (initial)")
            return 0
        next_num = existing.num_amendement + 1
        logger.info("[_get_next_num_amendement_for_ap] Retourne %s", next_num)
        return next_num
    except Exception as e:
        logger.error("[_get_next_num_amendement_for_ap] Erreur: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        raise


# ==================== ENDPOINTS API ACTIVITE PERIODIQUE ====================

