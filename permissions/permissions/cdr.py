from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
import logging
from permissions.services.permission_service import PermissionService
from .base import AppActionPermission

logger = logging.getLogger(__name__)

# ==================== CLASSES SPÉCIALISÉES PAR APP ====================

# ==================== CDR (Cartographie des Risques) ====================

class CDRCreatePermission(AppActionPermission):
    """Permission pour créer une CDR"""
    app_name = 'cdr'
    action = 'create_cdr'


class CDRUpdatePermission(AppActionPermission):
    """Permission pour modifier une CDR"""
    app_name = 'cdr'
    action = 'update_cdr'


class CDRDeletePermission(AppActionPermission):
    """Permission pour supprimer une CDR"""
    app_name = 'cdr'
    action = 'delete_cdr'


class CDRValidatePermission(AppActionPermission):
    """Permission pour valider une CDR"""
    app_name = 'cdr'
    action = 'validate_cdr'


class CDRReadPermission(AppActionPermission):
    """Permission pour lire une CDR"""
    app_name = 'cdr'
    action = 'read_cdr'


class CDRDetailCreatePermission(AppActionPermission):
    """Permission pour créer un détail CDR"""
    app_name = 'cdr'
    action = 'create_detail_cdr'


class CDRDetailUpdatePermission(AppActionPermission):
    """Permission pour modifier un détail CDR"""
    app_name = 'cdr'
    action = 'update_detail_cdr'


class CDRDetailDeletePermission(AppActionPermission):
    """Permission pour supprimer un détail CDR"""
    app_name = 'cdr'
    action = 'delete_detail_cdr'


class CDREvaluationCreatePermission(AppActionPermission):
    """Permission pour créer une évaluation de risque"""
    app_name = 'cdr'
    action = 'create_evaluation_risque'


class CDREvaluationUpdatePermission(AppActionPermission):
    """Permission pour modifier une évaluation de risque"""
    app_name = 'cdr'
    action = 'update_evaluation_risque'


class CDREvaluationDeletePermission(AppActionPermission):
    """Permission pour supprimer une évaluation de risque"""
    app_name = 'cdr'
    action = 'delete_evaluation_risque'


class CDRPlanActionCreatePermission(AppActionPermission):
    """Permission pour créer un plan d'action"""
    app_name = 'cdr'
    action = 'create_plan_action'


class CDRPlanActionUpdatePermission(AppActionPermission):
    """Permission pour modifier un plan d'action"""
    app_name = 'cdr'
    action = 'update_plan_action'


class CDRPlanActionDeletePermission(AppActionPermission):
    """Permission pour supprimer un plan d'action"""
    app_name = 'cdr'
    action = 'delete_plan_action'


class CDRSuiviCreatePermission(AppActionPermission):
    """Permission pour créer un suivi d'action"""
    app_name = 'cdr'
    action = 'create_suivi_action'


class CDRSuiviUpdatePermission(AppActionPermission):
    """Permission pour modifier un suivi d'action"""
    app_name = 'cdr'
    action = 'update_suivi_action'


class CDRSuiviDeletePermission(AppActionPermission):
    """Permission pour supprimer un suivi d'action"""
    app_name = 'cdr'
    action = 'delete_suivi_action'


# ==================== DASHBOARD ====================
