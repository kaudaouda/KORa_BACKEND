from rest_framework.permissions import BasePermission
import logging
from permissions.services.permission_service import PermissionService
from .base import AppActionPermission

logger = logging.getLogger(__name__)

class DashboardPreuveUpdatePermission(AppActionPermission):
    """Permission pour modifier les médias d'une preuve existante (ajout/suppression)."""
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
                logger.error(f"[DashboardPreuveUpdatePermission] Erreur extraction processus: {e}")
        return super()._extract_processus_uuid(request, view, obj)


class DashboardMediaUpdatePermission(BasePermission):
    """
    Permission pour modifier la description d'un média de preuve.
    Vérifie que l'utilisateur a update_periodicite (dashboard), update_traitement
    ou update_suivi (pac) dans AU MOINS UN de ses processus actifs.
    Cohérent avec DashboardMediaCreatePermission (même pattern any-processus).
    La sécurité objet est déjà garantie par les vues parentes (dashboard / PAC)
    qui contrôlent l'accès au processus avant que l'utilisateur atteigne cette vue.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if PermissionService._is_super_admin(request.user):
            return True
        from parametre.permissions import is_supervisor_smi
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
            logger.error(f"[DashboardMediaUpdatePermission] Erreur: {e}")
        return False


class DashboardMediaCreatePermission(BasePermission):
    """
    Permission pour créer un média ou une preuve.
    Pas de contexte de processus disponible à la création — vérifie que l'utilisateur
    a update_periodicite dans AU MOINS UN de ses processus.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if PermissionService._is_super_admin(request.user):
            return True
        from parametre.permissions import is_supervisor_smi
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
            logger.error(f"[DashboardMediaCreatePermission] Erreur: {e}")
        logger.warning(
            f"[DashboardMediaCreatePermission] ❌ Refus: user={request.user.username} "
            f"n'a pas update_periodicite dans aucun processus"
        )
        return False
