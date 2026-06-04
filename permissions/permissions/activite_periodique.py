from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
import logging
from permissions.services.permission_service import PermissionService
from .base import AppActionPermission

logger = logging.getLogger(__name__)

# ==================== ACTIVITÉ PÉRIODIQUE ====================

class ActivitePeriodiqueCreatePermission(AppActionPermission):
    """Permission pour créer une Activité Périodique"""
    app_name = 'activite_periodique'
    action = 'create_activite_periodique'


class ActivitePeriodiqueUpdatePermission(AppActionPermission):
    """Permission pour modifier une Activité Périodique"""
    app_name = 'activite_periodique'
    action = 'update_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est une ActivitePeriodique)"""
        # Si obj est fourni et c'est un objet ActivitePeriodique
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grâce à select_related)
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
                # Si c'est une chaîne (cas improbable mais géré)
                elif isinstance(obj.processus, str):
                    return obj.processus
        
        # Depuis view.kwargs si uuid fourni (pour compatibilité avec les autres méthodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            ap_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import ActivitePeriodique
                ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                if ap.processus:
                    return str(ap.processus.uuid)
            except Exception as e:
                logger.warning(f"[ActivitePeriodiqueUpdatePermission] Erreur extraction processus depuis ap {ap_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDeletePermission(AppActionPermission):
    """Permission pour supprimer une Activité Périodique"""
    app_name = 'activite_periodique'
    action = 'delete_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est une ActivitePeriodique)"""
        # Si obj est fourni et c'est un objet ActivitePeriodique
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grâce à select_related)
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
                # Si c'est une chaîne (cas improbable mais géré)
                elif isinstance(obj.processus, str):
                    return obj.processus
        
        # Depuis view.kwargs si uuid fourni (pour compatibilité avec les autres méthodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            ap_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import ActivitePeriodique
                ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
                if ap.processus:
                    return str(ap.processus.uuid)
            except Exception as e:
                logger.warning(f"[ActivitePeriodiqueDeletePermission] Erreur extraction processus depuis ap {ap_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueValidatePermission(AppActionPermission):
    """Permission pour valider une Activité Périodique"""
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
                logger.warning(f"[ActivitePeriodiqueValidatePermission] Erreur extraction processus depuis ap {ap_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueReadPermission(AppActionPermission):
    """Permission pour lire une Activité Périodique"""
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
                logger.warning(f"[ActivitePeriodiqueReadPermission] Erreur extraction processus depuis ap {ap_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDetailPermission(BasePermission):
    """
    Permission pour activite_periodique_detail qui gère GET, PATCH et DELETE
    GET : ActivitePeriodiqueReadPermission
    PATCH : ActivitePeriodiqueUpdatePermission
    DELETE : ActivitePeriodiqueDeletePermission
    
    Security by Design : Refus par défaut, vérifie l'authentification puis les permissions
    Gère automatiquement les super admins via user_has_access_to_processus
    
    Note: Pour les @api_view, DRF ne passe pas automatiquement par has_object_permission.
    On doit donc vérifier dans has_permission en extrayant l'objet depuis view.kwargs.
    """
    def has_permission(self, request, view):
        """
        Security by Design : Vérifie les permissions AVANT toute requête DB
        Refus par défaut si l'objet n'existe pas ou si les permissions échouent
        """
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"[ActivitePeriodiqueDetailPermission] Utilisateur non authentifié")
            raise PermissionDenied("Authentification requise")
        
        # Extraire l'UUID depuis les kwargs de la vue
        ap_uuid = view.kwargs.get('uuid')
        if not ap_uuid:
            logger.warning(f"[ActivitePeriodiqueDetailPermission] UUID de l'AP manquant pour user={request.user.username}")
            raise PermissionDenied("UUID de l'Activité Périodique manquant")
        
        logger.info(
            f"[ActivitePeriodiqueDetailPermission] 🔍 Début vérification permission: "
            f"user={request.user.username}, method={request.method}, ap_uuid={ap_uuid}"
        )
        
        # Récupérer l'objet ActivitePeriodique pour avoir le processus_uuid
        # Security by Design : On doit récupérer l'objet pour vérifier les permissions
        try:
            from activite_periodique.models import ActivitePeriodique
            from parametre.permissions import user_has_access_to_processus
            ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
            logger.info(
                f"[ActivitePeriodiqueDetailPermission] ✅ AP trouvé: uuid={ap.uuid}, processus_uuid={ap.processus.uuid if ap.processus else None}"
            )
        except ActivitePeriodique.DoesNotExist:
            # Security by Design : Refus par défaut - ne pas révéler si l'objet existe ou non
            logger.warning(f"[ActivitePeriodiqueDetailPermission] ❌ AP non trouvé: uuid={ap_uuid}")
            raise PermissionDenied("Accès refusé à cette Activité Périodique")
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not ap.processus:
            logger.warning(f"[ActivitePeriodiqueDetailPermission] ❌ AP sans processus: uuid={ap_uuid}")
            raise PermissionDenied("Cette Activité Périodique n'est associée à aucun processus")
        
        processus_uuid = str(ap.processus.uuid)
        has_access = user_has_access_to_processus(request.user, processus_uuid)
        logger.info(
            f"[ActivitePeriodiqueDetailPermission] 🔍 Vérification accès processus: "
            f"user={request.user.username}, processus_uuid={processus_uuid}, has_access={has_access}"
        )
        
        if not has_access:
            logger.warning(
                f"[ActivitePeriodiqueDetailPermission] ❌ Accès refusé au processus: "
                f"user={request.user.username}, processus_uuid={processus_uuid}"
            )
            raise PermissionDenied("Vous n'avez pas accès au processus de cette Activité Périodique")
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier selon la méthode HTTP
        try:
            if request.method == 'GET':
                logger.info(f"[ActivitePeriodiqueDetailPermission] 🔍 Vérification permission read_activite_periodique pour user={request.user.username}")
                permission = ActivitePeriodiqueReadPermission()
                permission.has_object_permission(request, view, ap)
                logger.info(f"[ActivitePeriodiqueDetailPermission] ✅ Permission read_activite_periodique accordée")
            elif request.method in ['PATCH', 'PUT']:
                logger.info(f"[ActivitePeriodiqueDetailPermission] 🔍 Vérification permission update_activite_periodique pour user={request.user.username}")
                permission = ActivitePeriodiqueUpdatePermission()
                permission.has_object_permission(request, view, ap)
                logger.info(f"[ActivitePeriodiqueDetailPermission] ✅ Permission update_activite_periodique accordée")
            elif request.method == 'DELETE':
                logger.info(f"[ActivitePeriodiqueDetailPermission] 🔍 Vérification permission delete_activite_periodique pour user={request.user.username}")
                permission = ActivitePeriodiqueDeletePermission()
                permission.has_object_permission(request, view, ap)
                logger.info(f"[ActivitePeriodiqueDetailPermission] ✅ Permission delete_activite_periodique accordée")
            else:
                logger.warning(f"[ActivitePeriodiqueDetailPermission] ❌ Méthode HTTP non autorisée: {request.method}")
                raise PermissionDenied(f"Méthode HTTP '{request.method}' non autorisée")
        except PermissionDenied as e:
            # Re-lever l'exception pour que DRF la gère correctement
            logger.warning(f"[ActivitePeriodiqueDetailPermission] ❌ Permission refusée: {e}")
            raise
        except Exception as e:
            # Logger l'erreur et refuser l'accès par sécurité
            logger.error(f"[ActivitePeriodiqueDetailPermission] ❌ Erreur lors de la vérification de permission: {e}", exc_info=True)
            raise PermissionDenied("Erreur lors de la vérification des permissions")
        
        logger.info(f"[ActivitePeriodiqueDetailPermission] ✅ Permission accordée pour user={request.user.username}, method={request.method}")
        return True


class ActivitePeriodiqueUnvalidatePermission(AppActionPermission):
    """Permission pour dévalider une Activité Périodique"""
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
                logger.warning(f"[ActivitePeriodiqueUnvalidatePermission] Erreur extraction processus depuis ap {ap_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueListPermission(BasePermission):
    """
    Permission pour activites_periodiques_list qui gère GET
    GET : Vérifie que l'utilisateur a la permission read_activite_periodique pour au moins un processus
    Security by Design : Refus par défaut si l'utilisateur n'a pas la permission
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"[ActivitePeriodiqueListPermission] Utilisateur non authentifié")
            return False
        
        if request.method != 'GET':
            return False
        
        # ========== SUPER ADMIN / SUPERVISEUR SMI : Accès complet ==========
        from parametre.permissions import can_manage_users, is_supervisor_smi
        if can_manage_users(request.user) or is_supervisor_smi(request.user):
            logger.info(
                f"[ActivitePeriodiqueListPermission] ✅ Bypass autorisé: {request.user.username}"
            )
            return True
        # ========== FIN BYPASS ==========
        
        # Récupérer la liste des processus de l'utilisateur
        from parametre.permissions import get_user_processus_list
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (déjà géré ci-dessus)
        if user_processus_uuids is None:
            return True
        
        # Si aucun processus assigné, refuser l'accès
        if not user_processus_uuids:
            logger.warning(
                f"[ActivitePeriodiqueListPermission] ❌ Aucun processus assigné pour user={request.user.username}"
            )
            return False
        
        # Vérifier que l'utilisateur a la permission read_activite_periodique pour au moins un processus
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
                        f"[ActivitePeriodiqueListPermission] ✅ Permission read_activite_periodique accordée "
                        f"pour user={request.user.username}, processus_uuid={processus_uuid}"
                    )
                    return True
            except Exception as e:
                logger.error(
                    f"[ActivitePeriodiqueListPermission] ❌ Erreur lors de la vérification de permission "
                    f"pour processus_uuid={processus_uuid}: {e}",
                    exc_info=True
                )
                # En cas d'erreur, continuer avec le processus suivant (refus par défaut)
                continue
        
        # Si aucune permission trouvée pour aucun processus, refuser l'accès
        logger.warning(
            f"[ActivitePeriodiqueListPermission] ❌ Aucune permission read_activite_periodique "
            f"pour user={request.user.username} sur aucun processus"
        )
        return False


class ActivitePeriodiqueAmendementCreatePermission(AppActionPermission):
    """Permission pour créer un amendement d'Activité Périodique"""
    app_name = 'activite_periodique'
    action = 'create_amendement_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """
        Extrait le processus_uuid depuis initial_ref ou depuis le processus fourni dans request.data
        Pour créer un amendement, on doit récupérer l'AP initiale pour obtenir son processus
        """
        # 1. Depuis l'objet (si fourni)
        if obj:
            if hasattr(obj, 'processus'):
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
        
        # 2. Depuis request.data : initial_ref (cas spécifique pour create_amendement_activite_periodique)
        if hasattr(request, 'data') and request.data:
            initial_ref_uuid = request.data.get('initial_ref')
            if initial_ref_uuid:
                # Récupérer l'AP initiale pour obtenir son processus
                try:
                    from activite_periodique.models import ActivitePeriodique
                    initial_ap = ActivitePeriodique.objects.select_related('processus').get(uuid=initial_ref_uuid)
                    if initial_ap.processus:
                        return str(initial_ap.processus.uuid)
                except Exception as e:
                    logger.warning(
                        f"[ActivitePeriodiqueAmendementCreatePermission] Erreur lors de la récupération "
                        f"de l'AP initiale {initial_ref_uuid}: {str(e)}"
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
    """Permission pour créer un détail d'Activité Périodique"""
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
                    logger.warning(f"[ActivitePeriodiqueDetailCreatePermission] Erreur extraction processus depuis ap {ap_uuid}: {e}")
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from activite_periodique.models import DetailsAP
                detail = DetailsAP.objects.select_related('activite_periodique__processus').get(uuid=detail_uuid)
                if detail.activite_periodique and detail.activite_periodique.processus:
                    return str(detail.activite_periodique.processus.uuid)
            except Exception as e:
                logger.warning(f"[ActivitePeriodiqueDetailCreatePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDetailUpdatePermission(AppActionPermission):
    """Permission pour modifier un détail d'Activité Périodique"""
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
                logger.warning(f"[ActivitePeriodiqueDetailUpdatePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueDetailDeletePermission(AppActionPermission):
    """Permission pour supprimer un détail d'Activité Périodique"""
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
                logger.warning(f"[ActivitePeriodiqueDetailDeletePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueSuiviCreatePermission(AppActionPermission):
    """Permission pour créer un suivi d'Activité Périodique"""
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
                    logger.warning(f"[ActivitePeriodiqueSuiviCreatePermission] Erreur extraction processus depuis details_ap {details_ap_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)
    
    def has_permission(self, request, view):
        """
        Vérifie la permission pour créer un suivi
        Accepte aussi update_suivi_activite_periodique comme fallback (logique métier : si on peut modifier, on peut créer)
        """
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Extraire le processus_uuid
            processus_uuid = self._extract_processus_uuid(request, view)
            
            if not processus_uuid:
                raise PermissionDenied(
                    f"Impossible de déterminer le processus pour vérifier la permission '{self.action}'"
                )
            
            # Vérifier d'abord create_suivi_activite_periodique
            can_perform, reason = PermissionService.can_perform_action(
                user=request.user,
                app_name=self.app_name,
                processus_uuid=processus_uuid,
                action=self.action
            )
            
            if can_perform:
                return True
            
            # Fallback : vérifier update_suivi_activite_periodique
            # Logique métier : si on peut modifier un suivi, on devrait pouvoir le créer
            logger.warning(
                f"[ActivitePeriodiqueSuiviCreatePermission] create_suivi refusé, vérification update_suivi comme fallback: "
                f"user={request.user.username}, processus_uuid={processus_uuid}"
            )
            
            can_update, update_reason = PermissionService.can_perform_action(
                user=request.user,
                app_name=self.app_name,
                processus_uuid=processus_uuid,
                action='update_suivi_activite_periodique'
            )
            
            if can_update:
                logger.warning(
                    f"[ActivitePeriodiqueSuiviCreatePermission] ✅ Permission accordée via update_suivi fallback: "
                    f"user={request.user.username}, processus_uuid={processus_uuid}"
                )
                return True
            
            # Les deux permissions sont refusées
            logger.error(
                f"[ActivitePeriodiqueSuiviCreatePermission] ❌ PERMISSION REFUSÉE: "
                f"user={request.user.username}, processus_uuid={processus_uuid}, "
                f"create_reason={reason}, update_reason={update_reason}"
            )
            raise PermissionDenied(
                reason or f"Action '{self.action}' non autorisée. "
                f"Permission 'update_suivi_activite_periodique' également refusée."
            )
            
        except PermissionDenied:
            raise
        except Exception as e:
            logger.error(
                f"[ActivitePeriodiqueSuiviCreatePermission] Erreur lors de la vérification de permission: {e}",
                exc_info=True
            )
            raise PermissionDenied(
                f"Erreur lors de la vérification de la permission '{self.action}': {str(e)}"
            )


class ActivitePeriodiqueSuiviUpdatePermission(AppActionPermission):
    """Permission pour modifier un suivi d'Activité Périodique"""
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
                    logger.warning(f"[ActivitePeriodiqueSuiviUpdatePermission] Erreur extraction processus depuis suivi_ap dans request.data {suivi_uuid}: {e}")
        
        # 3. Depuis view.kwargs si uuid fourni (pour update/delete avec UUID dans l'URL)
        # Peut être un SuivisAP ou un MediaLivrable
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
                    logger.warning(f"[ActivitePeriodiqueSuiviUpdatePermission] Erreur extraction processus depuis MediaLivrable {uuid_value}: {e}")
            except Exception as e:
                logger.warning(f"[ActivitePeriodiqueSuiviUpdatePermission] Erreur extraction processus depuis suivi {uuid_value}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class ActivitePeriodiqueSuiviDeletePermission(AppActionPermission):
    """Permission pour supprimer un suivi d'Activité Périodique"""
    app_name = 'activite_periodique'
    action = 'delete_suivi_activite_periodique'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.details_ap.activite_periodique.processus"""
        # Log immédiat pour confirmer que la méthode est appelée
        import sys
        print(f"[ActivitePeriodiqueSuiviDeletePermission._extract_processus_uuid] 🔍 MÉTHODE APPELÉE", file=sys.stderr, flush=True)
        logger.error(
            f"[ActivitePeriodiqueSuiviDeletePermission._extract_processus_uuid] 🔍 DÉBUT EXTRACTION: "
            f"has_obj={obj is not None}, has_view={view is not None}, "
            f"view_kwargs={view.kwargs if (view and hasattr(view, 'kwargs')) else 'N/A'}"
        )
        
        # 1. Depuis obj (si fourni, pour delete)
        if obj:
            logger.warning(f"[ActivitePeriodiqueSuiviDeletePermission] Tentative extraction depuis obj: {type(obj)}")
            if hasattr(obj, 'details_ap') and obj.details_ap:
                if hasattr(obj.details_ap, 'activite_periodique') and obj.details_ap.activite_periodique:
                    if hasattr(obj.details_ap.activite_periodique, 'processus') and obj.details_ap.activite_periodique.processus:
                        processus_uuid = str(obj.details_ap.activite_periodique.processus.uuid)
                        logger.info(f"[ActivitePeriodiqueSuiviDeletePermission] ✅ Processus UUID extrait depuis obj: {processus_uuid}")
                        return processus_uuid
        
        # 2. Depuis view.kwargs si uuid fourni (pour delete avec UUID dans l'URL)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            suivi_uuid = view.kwargs['uuid']
            logger.warning(f"[ActivitePeriodiqueSuiviDeletePermission] 🔍 Tentative extraction depuis view.kwargs: suivi_uuid={suivi_uuid}")
            try:
                from activite_periodique.models import SuivisAP
                
                # Utiliser select_related pour optimiser et éviter les requêtes multiples
                try:
                    suivi = SuivisAP.objects.select_related(
                        'details_ap__activite_periodique__processus'
                    ).get(uuid=suivi_uuid)
                    
                    # Extraire le processus UUID depuis le suivi
                    if (suivi.details_ap and 
                        suivi.details_ap.activite_periodique and 
                        suivi.details_ap.activite_periodique.processus):
                        processus_uuid = str(suivi.details_ap.activite_periodique.processus.uuid)
                        logger.warning(f"[ActivitePeriodiqueSuiviDeletePermission] ✅✅✅ Processus UUID extrait: {processus_uuid}")
                        return processus_uuid
                    else:
                        logger.error(f"[ActivitePeriodiqueSuiviDeletePermission] ❌ Chaîne de relations incomplète pour suivi {suivi_uuid}")
                except SuivisAP.DoesNotExist:
                    logger.error(f"[ActivitePeriodiqueSuiviDeletePermission] ❌ SuivisAP {suivi_uuid} non trouvé (DoesNotExist)")
                except Exception as e:
                    logger.error(f"[ActivitePeriodiqueSuiviDeletePermission] ❌ Erreur lors de l'extraction: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(f"[ActivitePeriodiqueSuiviDeletePermission] ❌ Erreur générale extraction processus depuis suivi {suivi_uuid}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        logger.warning(f"[ActivitePeriodiqueSuiviDeletePermission] ⚠️ Aucun processus UUID trouvé, appel de super()._extract_processus_uuid")
        result = super()._extract_processus_uuid(request, view, obj)
        logger.warning(f"[ActivitePeriodiqueSuiviDeletePermission] Résultat super()._extract_processus_uuid: {result}")
        return result
