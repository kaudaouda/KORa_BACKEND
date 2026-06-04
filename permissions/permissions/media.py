from rest_framework.permissions import BasePermission
import logging
from permissions.services.permission_service import PermissionService
from .base import AppActionPermission

logger = logging.getLogger(__name__)

class DashboardPreuveUpdatePermission(AppActionPermission):
    """Permission pour modifier les mÃ©dias d'une preuve existante (ajout/suppression)."""
    app_name = 'dashboard'
    action = 'update_periodicite'

    def _extract_processus_uuid(self, request, view, obj=None):
        preuve_uuid = view.kwargs.get('uuid') if hasattr(view, 'kwargs') else None
        if preuve_uuid:
            try:
                from parametre.models import Periodicite
                periodicite = Periodicite.objects.select_related(
                    'indicateur_id__objective_id__tableau_bord__processus'
                ).filter(preuve__uuid=preuve_uuid).first()
                if (periodicite and periodicite.indicateur_id
                        and periodicite.indicateur_id.objective_id
                        and periodicite.indicateur_id.objective_id.tableau_bord
                        and periodicite.indicateur_id.objective_id.tableau_bord.processus):
                    return str(periodicite.indicateur_id.objective_id.tableau_bord.processus.uuid)
            except Exception as e:
                logger.error("[DashboardPreuveUpdatePermission] Erreur extraction processus: %s", e)
        return super()._extract_processus_uuid(request, view, obj)


class DashboardMediaUpdatePermission(BasePermission):
    """
    Permission pour modifier la description d'un mÃ©dia de preuve.
    VÃ©rifie que l'utilisateur a update_periodicite (dashboard), update_traitement
    ou update_suivi (pac) dans AU MOINS UN de ses processus actifs.
    CohÃ©rent avec DashboardMediaCreatePermission (mÃªme pattern any-processus).
    La sÃ©curitÃ© objet est dÃ©jÃ  garantie par les vues parentes (dashboard / PAC)
    qui contrÃ´lent l'accÃ¨s au processus avant que l'utilisateur atteigne cette vue.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if PermissionService._is_super_admin(request.user):
            return True
        from shared.permissions import is_supervisor_smi
        if is_supervisor_smi(request.user):
            return True
        try:
            from parametre.models import UserProcessusRole
            processus_uuids = list(
                UserProcessusRole.objects.filter(
                    user=request.user, is_active=True, processus__isnull=False
                ).values_list('processus__uuid', flat=True).distinct()
            )
            for proc_uuid in processus_uuids:
                proc_uuid_str = str(proc_uuid)
                can, _ = PermissionService.can_perform_action(
                    request.user, 'dashboard', proc_uuid_str, 'update_periodicite'
                )
                if can:
                    return True
                can, _ = PermissionService.can_perform_action(
                    request.user, 'pac', proc_uuid_str, 'update_traitement'
                )
                if can:
                    return True
                can, _ = PermissionService.can_perform_action(
                    request.user, 'pac', proc_uuid_str, 'update_suivi'
                )
                if can:
                    return True
        except Exception as e:
            logger.error("[DashboardMediaUpdatePermission] Erreur: %s", e)
        return False


class DashboardMediaCreatePermission(BasePermission):
    """
    Permission pour crÃ©er un mÃ©dia ou une preuve.
    Pas de contexte de processus disponible Ã  la crÃ©ation â€” vÃ©rifie que l'utilisateur
    a update_periodicite dans AU MOINS UN de ses processus.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if PermissionService._is_super_admin(request.user):
            return True
        from shared.permissions import is_supervisor_smi
        if is_supervisor_smi(request.user):
            return True
        try:
            from parametre.models import UserProcessusRole
            processus_uuids = UserProcessusRole.objects.filter(
                user=request.user
            ).values_list('processus__uuid', flat=True).distinct()
            for processus_uuid in processus_uuids:
                if processus_uuid:
                    can, _ = PermissionService.can_perform_action(
                        request.user, 'dashboard', str(processus_uuid), 'update_periodicite'
                    )
                    if can:
                        return True
        except Exception as e:
            logger.error("[DashboardMediaCreatePermission] Erreur: %s", e)
        logger.warning(
            "[DashboardMediaCreatePermission] \u274c Refus: user=%s n'a pas update_periodicite dans aucun processus", request.user.username
        )
        return False

