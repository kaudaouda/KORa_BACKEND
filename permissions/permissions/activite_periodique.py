from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
import logging
from permissions.services.permission_service import PermissionService
from .base import AppActionPermission

logger = logging.getLogger(__name__)

# ==================== ACTIVITÃ‰ PÃ‰RIODIQUE ====================

class ActivitePeriodiqueCreatePermission(AppActionPermission):
    """Permission pour crÃ©er une ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'create_activite_periodique'


class ActivitePeriodiqueUpdatePermission(AppActionPermission):
    """Permission pour modifier une ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'update_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est une ActivitePeriodique)"""
        # Si obj est fourni et c'est un objet ActivitePeriodique
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grÃ¢ce Ã  select_related)
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
                # Si c'est une chaÃ®ne (cas improbable mais gÃ©rÃ©)
                elif isinstance(obj.processus, str):
                    return obj.processus
        
        # Depuis view.kwargs si uuid fourni (pour compatibilitÃ© avec les autres mÃ©thodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            ap_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import ActivitePeriodique
                ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                if ap.processus:
                    return str(ap.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueUpdatePermission] Erreur extraction processus depuis ap %s: %s", ap_uuid, e)
        
        # Fallback sur la mÃ©thode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDeletePermission(AppActionPermission):
    """Permission pour supprimer une ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'delete_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est une ActivitePeriodique)"""
        # Si obj est fourni et c'est un objet ActivitePeriodique
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grÃ¢ce Ã  select_related)
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
                # Si c'est une chaÃ®ne (cas improbable mais gÃ©rÃ©)
                elif isinstance(obj.processus, str):
                    return obj.processus
        
        # Depuis view.kwargs si uuid fourni (pour compatibilitÃ© avec les autres mÃ©thodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            ap_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import ActivitePeriodique
                ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                if ap.processus:
                    return str(ap.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueDeletePermission] Erreur extraction processus depuis ap %s: %s", ap_uuid, e)
        
        # Fallback sur la mÃ©thode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueValidatePermission(AppActionPermission):
    """Permission pour valider une ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'validate_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est une ActivitePeriodique)"""
        # Si obj est fourni et c'est un objet ActivitePeriodique
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            ap_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import ActivitePeriodique
                ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                if ap.processus:
                    return str(ap.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueValidatePermission] Erreur extraction processus depuis ap %s: %s", ap_uuid, e)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueReadPermission(AppActionPermission):
    """Permission pour lire une ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'read_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est une ActivitePeriodique)"""
        # Si obj est fourni et c'est un objet ActivitePeriodique
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            ap_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import ActivitePeriodique
                ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                if ap.processus:
                    return str(ap.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueReadPermission] Erreur extraction processus depuis ap %s: %s", ap_uuid, e)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDetailPermission(BasePermission):
    """
    Permission pour activite_periodique_detail qui gÃ¨re GET, PATCH et DELETE
    GET : ActivitePeriodiqueReadPermission
    PATCH : ActivitePeriodiqueUpdatePermission
    DELETE : ActivitePeriodiqueDeletePermission
    
    Security by Design : Refus par dÃ©faut, vÃ©rifie l'authentification puis les permissions
    GÃ¨re automatiquement les super admins via user_has_access_to_processus
    
    Note: Pour les @api_view, DRF ne passe pas automatiquement par has_object_permission.
    On doit donc vÃ©rifier dans has_permission en extrayant l'objet depuis view.kwargs.
    """
    def has_permission(self, request, view):
        """
        Security by Design : VÃ©rifie les permissions AVANT toute requÃªte DB
        Refus par dÃ©faut si l'objet n'existe pas ou si les permissions Ã©chouent
        """
        if not request.user or not request.user.is_authenticated:
            logger.warning("[ActivitePeriodiqueDetailPermission] Utilisateur non authentifiÃ©")
            raise PermissionDenied("Authentification requise")
        
        # Extraire l'UUID depuis les kwargs de la vue
        ap_uuid = view.kwargs.get('uuid')
        if not ap_uuid:
            logger.warning("[ActivitePeriodiqueDetailPermission] UUID de l'AP manquant pour user=%s", request.user.username)
            raise PermissionDenied("UUID de l'ActivitÃ© PÃ©riodique manquant")
        
        logger.info(
            "[ActivitePeriodiqueDetailPermission] ðŸ” DÃ©but vÃ©rification permission: user=%s, method=%s, ap_uuid=%s", request.user.username, request.method, ap_uuid
        )
        
        # RÃ©cupÃ©rer l'objet ActivitePeriodique pour avoir le processus_uuid
        # Security by Design : On doit rÃ©cupÃ©rer l'objet pour vÃ©rifier les permissions
        try:
            from activite_periodique.models import ActivitePeriodique
            from shared.permissions import user_has_access_to_processus
            ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
            logger.info(
                "[ActivitePeriodiqueDetailPermission] âœ… AP trouvÃ©: uuid=%s, processus_uuid=%s", ap.uuid, ap.processus.uuid if ap.processus else None
            )
        except ActivitePeriodique.DoesNotExist:
            # Security by Design : Refus par dÃ©faut - ne pas rÃ©vÃ©ler si l'objet existe ou non
            logger.warning("[ActivitePeriodiqueDetailPermission] âŒ AP non trouvÃ©: uuid=%s", ap_uuid)
            raise PermissionDenied("AccÃ¨s refusÃ© Ã  cette ActivitÃ© PÃ©riodique")
        
        # ========== VÃ‰RIFICATION D'ACCÃˆS AU PROCESSUS (Security by Design) ==========
        if not ap.processus:
            logger.warning("[ActivitePeriodiqueDetailPermission] âŒ AP sans processus: uuid=%s", ap_uuid)
            raise PermissionDenied("Cette ActivitÃ© PÃ©riodique n'est associÃ©e Ã  aucun processus")
        
        processus_uuid = str(ap.processus.uuid)
        has_access = user_has_access_to_processus(request.user, processus_uuid)
        logger.info(
            "[ActivitePeriodiqueDetailPermission] ðŸ” VÃ©rification accÃ¨s processus: user=%s, processus_uuid=%s, has_access=%s", request.user.username, processus_uuid, has_access
        )
        
        if not has_access:
            logger.warning(
                "[ActivitePeriodiqueDetailPermission] âŒ AccÃ¨s refusÃ© au processus: user=%s, processus_uuid=%s", request.user.username, processus_uuid
            )
            raise PermissionDenied("Vous n'avez pas accÃ¨s au processus de cette ActivitÃ© PÃ©riodique")
        # ========== FIN VÃ‰RIFICATION ==========
        
        # VÃ©rifier selon la mÃ©thode HTTP
        try:
            if request.method == 'GET':
                logger.info("[ActivitePeriodiqueDetailPermission] ðŸ” VÃ©rification permission read_activite_periodique pour user=%s", request.user.username)
                permission = ActivitePeriodiqueReadPermission()
                permission.has_object_permission(request, view, ap)
                logger.info("[ActivitePeriodiqueDetailPermission] âœ… Permission read_activite_periodique accordÃ©e")
            elif request.method in ['PATCH', 'PUT']:
                logger.info("[ActivitePeriodiqueDetailPermission] ðŸ” VÃ©rification permission update_activite_periodique pour user=%s", request.user.username)
                permission = ActivitePeriodiqueUpdatePermission()
                permission.has_object_permission(request, view, ap)
                logger.info("[ActivitePeriodiqueDetailPermission] âœ… Permission update_activite_periodique accordÃ©e")
            elif request.method == 'DELETE':
                logger.info("[ActivitePeriodiqueDetailPermission] ðŸ” VÃ©rification permission delete_activite_periodique pour user=%s", request.user.username)
                permission = ActivitePeriodiqueDeletePermission()
                permission.has_object_permission(request, view, ap)
                logger.info("[ActivitePeriodiqueDetailPermission] âœ… Permission delete_activite_periodique accordÃ©e")
            else:
                logger.warning("[ActivitePeriodiqueDetailPermission] âŒ MÃ©thode HTTP non autorisÃ©e: %s", request.method)
                raise PermissionDenied(f"MÃ©thode HTTP '{request.method}' non autorisÃ©e")
        except PermissionDenied as e:
            # Re-lever l'exception pour que DRF la gÃ¨re correctement
            logger.warning("[ActivitePeriodiqueDetailPermission] âŒ Permission refusÃ©e: %s", e)
            raise
        except Exception as e:
            # Logger l'erreur et refuser l'accÃ¨s par sÃ©curitÃ©
            logger.error("[ActivitePeriodiqueDetailPermission] âŒ Erreur lors de la vÃ©rification de permission: %s", e, exc_info=True)
            raise PermissionDenied("Erreur lors de la vÃ©rification des permissions")
        
        logger.info("[ActivitePeriodiqueDetailPermission] âœ… Permission accordÃ©e pour user=%s, method=%s", request.user.username, request.method)
        return True


class ActivitePeriodiqueUnvalidatePermission(AppActionPermission):
    """Permission pour dÃ©valider une ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'unvalidate_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est une ActivitePeriodique)"""
        # Si obj est fourni et c'est un objet ActivitePeriodique
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            ap_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import ActivitePeriodique
                ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                if ap.processus:
                    return str(ap.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueUnvalidatePermission] Erreur extraction processus depuis ap %s: %s", ap_uuid, e)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueListPermission(BasePermission):
    """
    Permission pour activites_periodiques_list qui gÃ¨re GET
    GET : VÃ©rifie que l'utilisateur a la permission read_activite_periodique pour au moins un processus
    Security by Design : Refus par dÃ©faut si l'utilisateur n'a pas la permission
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning("[ActivitePeriodiqueListPermission] Utilisateur non authentifiÃ©")
            return False
        
        if request.method != 'GET':
            return False
        
        # ========== SUPER ADMIN / SUPERVISEUR SMI : AccÃ¨s complet ==========
        from shared.permissions import can_manage_users, is_supervisor_smi
        if can_manage_users(request.user) or is_supervisor_smi(request.user):
            logger.info(
                "[ActivitePeriodiqueListPermission] âœ… Bypass autorisÃ©: %s", request.user.username
            )
            return True
        # ========== FIN BYPASS ==========
        
        # RÃ©cupÃ©rer la liste des processus de l'utilisateur
        from shared.permissions import get_user_processus_list
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (dÃ©jÃ  gÃ©rÃ© ci-dessus)
        if user_processus_uuids is None:
            return True
        
        # Si aucun processus assignÃ©, refuser l'accÃ¨s
        if not user_processus_uuids:
            logger.warning(
                "[ActivitePeriodiqueListPermission] âŒ Aucun processus assignÃ© pour user=%s", request.user.username
            )
            return False
        
        # VÃ©rifier que l'utilisateur a la permission read_activite_periodique pour au moins un processus
        for processus_uuid in user_processus_uuids:
            try:
                can_perform, reason = PermissionService.can_perform_action(
                    user=request.user,
                    app_name='activite_periodique',
                    action='read_activite_periodique',
                    processus_uuid=str(processus_uuid)
                )
                if can_perform:
                    logger.info(
                        "[ActivitePeriodiqueListPermission] âœ… Permission read_activite_periodique accordÃ©e pour user=%s, processus_uuid=%s", request.user.username, processus_uuid
                    )
                    return True
            except Exception as e:
                logger.error(
                    "[ActivitePeriodiqueListPermission] âŒ Erreur lors de la vÃ©rification de permission pour processus_uuid=%s: %s", processus_uuid, e,
                    exc_info=True
                )
                # En cas d'erreur, continuer avec le processus suivant (refus par dÃ©faut)
                continue
        
        # Si aucune permission trouvÃ©e pour aucun processus, refuser l'accÃ¨s
        logger.warning(
            "[ActivitePeriodiqueListPermission] âŒ Aucune permission read_activite_periodique pour user=%s sur aucun processus", request.user.username
        )
        return False


class ActivitePeriodiqueAmendementCreatePermission(AppActionPermission):
    """Permission pour crÃ©er un amendement d'ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'create_amendement_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """
        Extrait le processus_uuid depuis initial_ref ou depuis le processus fourni dans request.data
        Pour crÃ©er un amendement, on doit rÃ©cupÃ©rer l'AP initiale pour obtenir son processus
        """
        # 1. Depuis l'objet (si fourni)
        if obj:
            if hasattr(obj, 'processus'):
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
        
        # 2. Depuis request.data : initial_ref (cas spÃ©cifique pour create_amendement_activite_periodique)
        if hasattr(request, 'data') and request.data:
            initial_ref_uuid = request.data.get('initial_ref')
            if initial_ref_uuid:
                # RÃ©cupÃ©rer l'AP initiale pour obtenir son processus
                try:
                    from activite_periodique.models import ActivitePeriodique
                    initial_ap = ActivitePeriodique.objects.select_related('processus').get(uuid=initial_ref_uuid)
                    if initial_ap.processus:
                        return str(initial_ap.processus.uuid)
                except Exception as e:
                    logger.warning(
                        "[ActivitePeriodiqueAmendementCreatePermission] Erreur lors de la rÃ©cupÃ©ration de l'AP initiale %s: %s", initial_ref_uuid, str(e)
                    )
        
        # 3. Depuis request.data : processus (si fourni directement)
        if hasattr(request, 'data') and request.data:
            processus_uuid = request.data.get('processus') or request.data.get('processus_uuid')
            if processus_uuid:
                return str(processus_uuid)
        
        # 4. Depuis query params
        if hasattr(request, 'query_params'):
            processus_uuid = request.query_params.get('processus_uuid') or request.query_params.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDetailCreatePermission(AppActionPermission):
    """Permission pour crÃ©er un dÃ©tail d'ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'create_detail_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (activite_periodique) ou depuis obj.activite_periodique.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'activite_periodique') and obj.activite_periodique:
                if hasattr(obj.activite_periodique, 'processus') and obj.activite_periodique.processus:
                    return str(obj.activite_periodique.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            ap_uuid = request.data.get('activite_periodique')
            if ap_uuid:
                try:
                    from activite_periodique.models import ActivitePeriodique
                    ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                    if ap.processus:
                        return str(ap.processus.uuid)
                except Exception as e:
                    logger.warning("[ActivitePeriodiqueDetailCreatePermission] Erreur extraction processus depuis ap %s: %s", ap_uuid, e)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import DetailsAP
                detail = DetailsAP.objects.select_related('activite_periodique__processus').get(uuid=detail_uuid)
                if detail.activite_periodique and detail.activite_periodique.processus:
                    return str(detail.activite_periodique.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueDetailCreatePermission] Erreur extraction processus depuis detail %s: %s", detail_uuid, e)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDetailUpdatePermission(AppActionPermission):
    """Permission pour modifier un dÃ©tail d'ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'update_detail_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.activite_periodique.processus"""
        if obj:
            if hasattr(obj, 'activite_periodique') and obj.activite_periodique:
                if hasattr(obj.activite_periodique, 'processus') and obj.activite_periodique.processus:
                    return str(obj.activite_periodique.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import DetailsAP
                detail = DetailsAP.objects.select_related('activite_periodique__processus').get(uuid=detail_uuid)
                if detail.activite_periodique and detail.activite_periodique.processus:
                    return str(detail.activite_periodique.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueDetailUpdatePermission] Erreur extraction processus depuis detail %s: %s", detail_uuid, e)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDetailDeletePermission(AppActionPermission):
    """Permission pour supprimer un dÃ©tail d'ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'delete_detail_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.activite_periodique.processus"""
        if obj:
            if hasattr(obj, 'activite_periodique') and obj.activite_periodique:
                if hasattr(obj.activite_periodique, 'processus') and obj.activite_periodique.processus:
                    return str(obj.activite_periodique.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import DetailsAP
                detail = DetailsAP.objects.select_related('activite_periodique__processus').get(uuid=detail_uuid)
                if detail.activite_periodique and detail.activite_periodique.processus:
                    return str(detail.activite_periodique.processus.uuid)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueDetailDeletePermission] Erreur extraction processus depuis detail %s: %s", detail_uuid, e)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueSuiviCreatePermission(AppActionPermission):
    """Permission pour crÃ©er un suivi d'ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'create_suivi_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (details_ap) ou depuis obj.details_ap.activite_periodique.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'details_ap') and obj.details_ap:
                if hasattr(obj.details_ap, 'activite_periodique') and obj.details_ap.activite_periodique:
                    if hasattr(obj.details_ap.activite_periodique, 'processus') and obj.details_ap.activite_periodique.processus:
                        return str(obj.details_ap.activite_periodique.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            details_ap_uuid = request.data.get('details_ap')
            if details_ap_uuid:
                try:
                    from activite_periodique.models import DetailsAP
                    detail = DetailsAP.objects.select_related('activite_periodique__processus').get(uuid=details_ap_uuid)
                    if detail.activite_periodique and detail.activite_periodique.processus:
                        return str(detail.activite_periodique.processus.uuid)
                except Exception as e:
                    logger.warning("[ActivitePeriodiqueSuiviCreatePermission] Erreur extraction processus depuis details_ap %s: %s", details_ap_uuid, e)
        
        return super()._extract_processus_uuid(request, view, obj)
    
    def has_permission(self, request, view):
        """
        VÃ©rifie la permission pour crÃ©er un suivi
        Accepte aussi update_suivi_activite_periodique comme fallback (logique mÃ©tier : si on peut modifier, on peut crÃ©er)
        """
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Extraire le processus_uuid
            processus_uuid = self._extract_processus_uuid(request, view)
            
            if not processus_uuid:
                raise PermissionDenied(
                    f"Impossible de dÃ©terminer le processus pour vÃ©rifier la permission '{self.action}'"
                )
            
            # VÃ©rifier d'abord create_suivi_activite_periodique
            can_perform, reason = PermissionService.can_perform_action(
                user=request.user,
                app_name=self.app_name,
                processus_uuid=processus_uuid,
                action=self.action
            )
            
            if can_perform:
                return True
            
            # Fallback : vÃ©rifier update_suivi_activite_periodique
            # Logique mÃ©tier : si on peut modifier un suivi, on devrait pouvoir le crÃ©er
            logger.warning(
                "[ActivitePeriodiqueSuiviCreatePermission] create_suivi refusÃ©, vÃ©rification update_suivi comme fallback: user=%s, processus_uuid=%s", request.user.username, processus_uuid
            )
            
            can_update, update_reason = PermissionService.can_perform_action(
                user=request.user,
                app_name=self.app_name,
                processus_uuid=processus_uuid,
                action='update_suivi_activite_periodique'
            )
            
            if can_update:
                logger.warning(
                    "[ActivitePeriodiqueSuiviCreatePermission] âœ… Permission accordÃ©e via update_suivi fallback: user=%s, processus_uuid=%s", request.user.username, processus_uuid
                )
                return True
            
            # Les deux permissions sont refusÃ©es
            logger.error(
                "[ActivitePeriodiqueSuiviCreatePermission] âŒ PERMISSION REFUSÃ‰E: user=%s, processus_uuid=%s, create_reason=%s, update_reason=%s", request.user.username, processus_uuid, reason, update_reason
            )
            raise PermissionDenied(
                reason or f"Action '{self.action}' non autorisÃ©e. "
                f"Permission 'update_suivi_activite_periodique' Ã©galement refusÃ©e."
            )
            
        except PermissionDenied:
            raise
        except Exception as e:
            logger.error(
                "[ActivitePeriodiqueSuiviCreatePermission] Erreur lors de la vÃ©rification de permission: %s", e,
                exc_info=True
            )
            raise PermissionDenied(
                f"Erreur lors de la vÃ©rification de la permission '{self.action}': {str(e)}"
            )


class ActivitePeriodiqueSuiviUpdatePermission(AppActionPermission):
    """Permission pour modifier un suivi d'ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'update_suivi_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.details_ap.activite_periodique.processus ou request.data"""
        # 1. Depuis obj (si fourni, pour update/delete)
        if obj:
            if hasattr(obj, 'details_ap') and obj.details_ap:
                if hasattr(obj.details_ap, 'activite_periodique') and obj.details_ap.activite_periodique:
                    if hasattr(obj.details_ap.activite_periodique, 'processus') and obj.details_ap.activite_periodique.processus:
                        return str(obj.details_ap.activite_periodique.processus.uuid)
        
        # 2. Depuis request.data (pour create, quand suivi_ap est dans le body)
        if hasattr(request, 'data') and request.data:
            suivi_uuid = request.data.get('suivi_ap')
            if suivi_uuid:
                try:
                    from activite_periodique.models import SuivisAP
                    suivi = SuivisAP.objects.select_related('details_ap__activite_periodique__processus').get(uuid=suivi_uuid)
                    if suivi.details_ap and suivi.details_ap.activite_periodique and suivi.details_ap.activite_periodique.processus:
                        return str(suivi.details_ap.activite_periodique.processus.uuid)
                except Exception as e:
                    logger.warning("[ActivitePeriodiqueSuiviUpdatePermission] Erreur extraction processus depuis suivi_ap dans request.data %s: %s", suivi_uuid, e)
        
        # 3. Depuis view.kwargs si uuid fourni (pour update/delete avec UUID dans l'URL)
        # Peut Ãªtre un SuivisAP ou un MediaLivrable
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            uuid_value = view.kwargs['uuid']
            
            # Essayer d'abord avec SuivisAP
            try:
                from activite_periodique.models import SuivisAP
                suivi = SuivisAP.objects.select_related('details_ap__activite_periodique__processus').get(uuid=uuid_value)
                if suivi.details_ap and suivi.details_ap.activite_periodique and suivi.details_ap.activite_periodique.processus:
                    return str(suivi.details_ap.activite_periodique.processus.uuid)
            except SuivisAP.DoesNotExist:
                # Si ce n'est pas un SuivisAP, essayer avec MediaLivrable
                try:
                    from parametre.models import MediaLivrable
                    if MediaLivrable is not None:
                        media_livrable = MediaLivrable.objects.select_related(
                            'suivi_ap__details_ap__activite_periodique__processus'
                        ).get(uuid=uuid_value)
                        if (media_livrable.suivi_ap and 
                            media_livrable.suivi_ap.details_ap and 
                            media_livrable.suivi_ap.details_ap.activite_periodique and 
                            media_livrable.suivi_ap.details_ap.activite_periodique.processus):
                            return str(media_livrable.suivi_ap.details_ap.activite_periodique.processus.uuid)
                except Exception as e:
                    logger.warning("[ActivitePeriodiqueSuiviUpdatePermission] Erreur extraction processus depuis MediaLivrable %s: %s", uuid_value, e)
            except Exception as e:
                logger.warning("[ActivitePeriodiqueSuiviUpdatePermission] Erreur extraction processus depuis suivi %s: %s", uuid_value, e)
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueSuiviDeletePermission(AppActionPermission):
    """Permission pour supprimer un suivi d'ActivitÃ© PÃ©riodique"""
    app_name = 'activite_periodique'
    action = 'delete_suivi_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.details_ap.activite_periodique.processus"""
        # Log immÃ©diat pour confirmer que la mÃ©thode est appelÃ©e
        import sys
        print(f"[ActivitePeriodiqueSuiviDeletePermission._extract_processus_uuid] ðŸ” MÃ‰THODE APPELÃ‰E", file=sys.stderr, flush=True)
        logger.error(
            "[ActivitePeriodiqueSuiviDeletePermission._extract_processus_uuid] ðŸ” DÃ‰BUT EXTRACTION: has_obj=%s, has_view=%s, view_kwargs=%s", obj is not None, view is not None, view.kwargs if view and hasattr(view, 'kwargs') else 'N/A'
        )
        
        # 1. Depuis obj (si fourni, pour delete)
        if obj:
            logger.warning("[ActivitePeriodiqueSuiviDeletePermission] Tentative extraction depuis obj: %s", type(obj))
            if hasattr(obj, 'details_ap') and obj.details_ap:
                if hasattr(obj.details_ap, 'activite_periodique') and obj.details_ap.activite_periodique:
                    if hasattr(obj.details_ap.activite_periodique, 'processus') and obj.details_ap.activite_periodique.processus:
                        processus_uuid = str(obj.details_ap.activite_periodique.processus.uuid)
                        logger.info("[ActivitePeriodiqueSuiviDeletePermission] âœ… Processus UUID extrait depuis obj: %s", processus_uuid)
                        return processus_uuid
        
        # 2. Depuis view.kwargs si uuid fourni (pour delete avec UUID dans l'URL)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            suivi_uuid = view.kwargs['uuid']
            logger.warning("[ActivitePeriodiqueSuiviDeletePermission] ðŸ” Tentative extraction depuis view.kwargs: suivi_uuid=%s", suivi_uuid)
            try:
                from activite_periodique.models import SuivisAP
                
                # Utiliser select_related pour optimiser et Ã©viter les requÃªtes multiples
                try:
                    suivi = SuivisAP.objects.select_related(
                        'details_ap__activite_periodique__processus'
                    ).get(uuid=suivi_uuid)
                    
                    # Extraire le processus UUID depuis le suivi
                    if (suivi.details_ap and 
                        suivi.details_ap.activite_periodique and 
                        suivi.details_ap.activite_periodique.processus):
                        processus_uuid = str(suivi.details_ap.activite_periodique.processus.uuid)
                        logger.warning("[ActivitePeriodiqueSuiviDeletePermission] âœ…âœ…âœ… Processus UUID extrait: %s", processus_uuid)
                        return processus_uuid
                    else:
                        logger.error("[ActivitePeriodiqueSuiviDeletePermission] âŒ ChaÃ®ne de relations incomplÃ¨te pour suivi %s", suivi_uuid)
                except SuivisAP.DoesNotExist:
                    logger.error("[ActivitePeriodiqueSuiviDeletePermission] âŒ SuivisAP %s non trouvÃ© (DoesNotExist)", suivi_uuid)
                except Exception as e:
                    logger.error("[ActivitePeriodiqueSuiviDeletePermission] âŒ Erreur lors de l'extraction: %s", e)
                    import traceback
                    logger.error(traceback.format_exc())
            except Exception as e:
                logger.error("[ActivitePeriodiqueSuiviDeletePermission] âŒ Erreur gÃ©nÃ©rale extraction processus depuis suivi %s: %s", suivi_uuid, e)
                import traceback
                logger.error(traceback.format_exc())
        
        logger.warning("[ActivitePeriodiqueSuiviDeletePermission] âš ï¸ Aucun processus UUID trouvÃ©, appel de super()._extract_processus_uuid")
        result = super()._extract_processus_uuid(request, view, obj)
        logger.warning("[ActivitePeriodiqueSuiviDeletePermission] RÃ©sultat super()._extract_processus_uuid: %s", result)
        return result

