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


class AllowAnyWithJWT(BasePermission):
    """
    Security by Design : permission dédiée aux endpoints de vérification de session.

    Permet aux requêtes anonymes d'atteindre la vue (pas de 401 bloquant)
    TOUT EN laissant le middleware JWT authentifier les requêtes portant un token valide.
    La vue est responsable de retourner des données différentes selon request.user.is_anonymous.

    Différence avec AllowAny :
    - AllowAny : usage générique, sans intention documentée.
    - AllowAnyWithJWT : intention explicite — endpoint public uniquement pour lire le statut auth.
      N'expose aucune donnée sensible pour les utilisateurs anonymes.
    """
    def has_permission(self, request, view):
        return True


# ==================== UTILITAIRES NUM AMENDEMENT ====================

def _get_next_num_amendement_for_pac(user, annee_uuid, processus_uuid):
    """
    Retourne le prochain num_amendement (entier) pour (annee, processus).
    0 = Initial (si aucun PAC n'existe encore), sinon max existant + 1.
    Unicité globale: on vérifie tous les PACs sans filtrer par utilisateur.
    """
    try:
        from django.db.models import Max
        logger.info("[_get_next_num_amendement_for_pac] annee_uuid=%s, processus_uuid=%s", annee_uuid, processus_uuid)
        result = Pac.objects.filter(
            annee_id=annee_uuid,
            processus_id=processus_uuid
        ).aggregate(max_num=Max('num_amendement'))
        max_num = result['max_num']
        next_num = 0 if max_num is None else max_num + 1
        logger.info("[_get_next_num_amendement_for_pac] next_num=%s", next_num)
        return next_num
    except Exception as e:
        logger.error("[_get_next_num_amendement_for_pac] Erreur: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        raise

