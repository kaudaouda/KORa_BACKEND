"""
Permission classes DRF pour le système générique de permissions
Supporte plusieurs applications : CDR, Dashboard, PAC, etc.
"""
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
import logging

from permissions.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class AppActionPermission(BasePermission):
    """
    Classe de base générique pour vérifier les permissions par application
    
    Usage avec instantiation (pour permissions dynamiques):
        @permission_classes([IsAuthenticated, AppActionPermission('cdr', 'create_cdr')])
        def cdr_create(request):
            ...
    
    Ou avec classes filles (SANS parenthèses - DRF instancie automatiquement):
        @permission_classes([IsAuthenticated, CDRCreatePermission])
        def cdr_create(request):
            ...
    
    ⚠️ IMPORTANT: Les classes filles doivent être passées SANS parenthèses () !
    """
    
    app_name = None  # Doit être défini dans les classes filles
    action = None    # Doit être défini dans les classes filles
    
    def __init__(self, app_name=None, action=None, check_context=True):
        """
        Args:
            app_name: Nom de l'application ('cdr', 'dashboard', 'pac', etc.)
                     Si None, utilise self.app_name de la classe
            action: Code de l'action ('create_cdr', 'update_tableau', etc.)
                   Si None, utilise self.action de la classe
            check_context: Si True, vérifie aussi les conditions contextuelles
        """
        if app_name:
            self.app_name = app_name
        if action:
            self.action = action
        self.check_context = check_context
        
        if not self.app_name or not self.action:
            raise ValueError(
                f"AppActionPermission: app_name et action doivent être définis. "
                f"Reçu: app_name={self.app_name}, action={self.action}"
            )
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """
        Extrait le processus_uuid depuis la request, view ou obj
        
        Ordre de priorité:
        1. Depuis obj (si fourni) : obj.processus.uuid
        2. Depuis request.data : request.data.get('processus')
        3. Depuis view.kwargs : view.kwargs.get('processus_uuid')
        4. Depuis query params : request.query_params.get('processus_uuid')
        """
        # 1. Depuis l'objet
        if obj:
            if hasattr(obj, 'processus'):
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            # Essayer directement obj.processus_uuid
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
        
        # 2. Depuis request.data (pour POST/PUT/PATCH)
        # Note: request.data peut ne pas être encore parsé par DRF au moment de la vérification des permissions
        # On essaie d'abord request.data, puis request.body si nécessaire
        if hasattr(request, 'data') and request.data:
            processus_uuid = request.data.get('processus') or request.data.get('processus_uuid')
            if processus_uuid:
                return str(processus_uuid)
        
        # 2b. Depuis request.body si request.data n'est pas encore parsé (pour POST)
        if hasattr(request, 'body') and request.body and request.method in ['POST', 'PUT', 'PATCH']:
            try:
                import json
                body_data = json.loads(request.body)
                processus_uuid = body_data.get('processus') or body_data.get('processus_uuid')
                if processus_uuid:
                    return str(processus_uuid)
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # 3. Depuis view.kwargs (pour les vues avec paramètres d'URL)
        if hasattr(view, 'kwargs') and view.kwargs:
            processus_uuid = view.kwargs.get('processus_uuid') or view.kwargs.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        # 4. Depuis query params
        if hasattr(request, 'query_params'):
            processus_uuid = request.query_params.get('processus_uuid') or request.query_params.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        return None
    
    def has_permission(self, request, view):
        """
        Vérifie la permission au niveau de la vue
        """
        try:
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Security by Design : Vérifier le super admin AVANT d'extraire le processus_uuid
            # Les super admins (is_staff ET is_superuser) ont toutes les permissions
            if PermissionService._is_super_admin(request.user):
                logger.info(
                    f"[AppActionPermission.has_permission] ✅ Super admin bypass: "
                    f"user={request.user.username}, app={self.app_name}, action={self.action}"
                )
                return True

            # Superviseur SMI : rôle global transverse — accès complet à toutes les apps
            from parametre.permissions import is_supervisor_smi
            if is_supervisor_smi(request.user):
                logger.info(
                    f"[AppActionPermission.has_permission] ✅ Superviseur SMI bypass: "
                    f"user={request.user.username}, app={self.app_name}, action={self.action}"
                )
                return True
            
            # Log pour déboguer
            logger.warning(
                f"[AppActionPermission.has_permission] 🔍 DÉBUT Vérification permission: "
                f"app={self.app_name}, action={self.action}, user={request.user.username}, "
                f"has_view={view is not None}, view_kwargs={view.kwargs if (view and hasattr(view, 'kwargs')) else 'N/A'}"
            )
            
            # Extraire le processus_uuid
            processus_uuid = self._extract_processus_uuid(request, view)
            
            logger.warning(
                f"[AppActionPermission.has_permission] 🔍 Vérification permission: "
                f"app={self.app_name}, action={self.action}, user={request.user.username}, "
                f"processus_uuid={processus_uuid}"
            )
            
            if not processus_uuid:
                # Si on ne peut pas extraire le processus, on refuse par sécurité
                logger.error(
                    f"[AppActionPermission] ❌ ERREUR: Impossible d'extraire processus_uuid pour "
                    f"app={self.app_name}, action={self.action}, user={request.user.username}, "
                    f"has_view={view is not None}, view_kwargs={view.kwargs if (view and hasattr(view, 'kwargs')) else 'N/A'}"
                )
                raise PermissionDenied(
                    f"Impossible de déterminer le processus pour vérifier la permission '{self.action}'"
                )
            
            # Vérifier via PermissionService
            try:
                can_perform, reason = PermissionService.can_perform_action(
                    user=request.user,
                    app_name=self.app_name,
                    processus_uuid=processus_uuid,
                    action=self.action
                )
                
                logger.warning(
                    f"[AppActionPermission.has_permission] ✅ Résultat vérification: "
                    f"can_perform={can_perform}, reason={reason}, "
                    f"app={self.app_name}, action={self.action}, user={request.user.username}, "
                    f"processus_uuid={processus_uuid}"
                )
                
                if not can_perform:
                    logger.error(
                        f"[AppActionPermission.has_permission] ❌ PERMISSION REFUSÉE: "
                        f"app={self.app_name}, action={self.action}, user={request.user.username}, "
                        f"processus_uuid={processus_uuid}, reason={reason}"
                    )
                    raise PermissionDenied(reason or f"Action '{self.action}' non autorisée")
            except PermissionDenied:
                raise
            except Exception as e:
                logger.error(
                    f"[AppActionPermission.has_permission] ❌ EXCEPTION dans PermissionService.can_perform_action: {e}",
                    exc_info=True
                )
                raise PermissionDenied(
                    f"Erreur lors de la vérification de la permission '{self.action}': {str(e)}"
                )
            
            return True
        except PermissionDenied:
            # Répercuter PermissionDenied tel quel
            raise
        except Exception as e:
            # Logger toute autre exception et refuser par sécurité
            logger.error(
                f"[AppActionPermission.has_permission] Erreur lors de la vérification de permission: {e}",
                exc_info=True
            )
            raise PermissionDenied(
                f"Erreur lors de la vérification de la permission '{self.action}': {str(e)}"
            )
    
    def has_object_permission(self, request, view, obj):
        """
        Vérifie la permission au niveau de l'objet
        Applique les conditions contextuelles si check_context=True
        """
        logger.info(
            f"[AppActionPermission.has_object_permission] 🔍 Début vérification: "
            f"app={self.app_name}, action={self.action}, user={request.user.username if request.user else None}, "
            f"obj={obj}, obj_type={type(obj).__name__ if obj else None}"
        )
        
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"[AppActionPermission.has_object_permission] ❌ User non authentifié")
            return False
        
        # Security by Design : Vérifier le super admin AVANT d'extraire le processus_uuid
        if PermissionService._is_super_admin(request.user):
            logger.info(
                f"[AppActionPermission.has_object_permission] ✅ Super admin bypass: "
                f"user={request.user.username}, app={self.app_name}, action={self.action}"
            )
            return True

        # Superviseur SMI : rôle global transverse — accès complet
        from parametre.permissions import is_supervisor_smi
        if is_supervisor_smi(request.user):
            logger.info(
                f"[AppActionPermission.has_object_permission] ✅ Superviseur SMI bypass: "
                f"user={request.user.username}, app={self.app_name}, action={self.action}"
            )
            return True

        # Extraire le processus_uuid depuis l'objet
        processus_uuid = self._extract_processus_uuid(request, view, obj)
        
        if not processus_uuid:
            logger.warning(
                f"[AppActionPermission.has_object_permission] ❌ Impossible d'extraire processus_uuid depuis l'objet "
                f"pour app={self.app_name}, action={self.action}, user={request.user.username}"
            )
            raise PermissionDenied(
                f"Impossible de déterminer le processus pour vérifier la permission '{self.action}'"
            )
        
        logger.info(
            f"[AppActionPermission.has_object_permission] 🔍 processus_uuid extrait: {processus_uuid}, "
            f"check_context={self.check_context}"
        )
        
        # Vérifier via PermissionService avec l'instance de l'objet pour les conditions contextuelles
        entity_instance = obj if self.check_context else None
        
        can_perform, reason = PermissionService.can_perform_action(
            user=request.user,
            app_name=self.app_name,
            processus_uuid=processus_uuid,
            action=self.action,
            entity_instance=entity_instance
        )
        
        logger.info(
            f"[AppActionPermission.has_object_permission] {'✅' if can_perform else '❌'} Résultat PermissionService: "
            f"can_perform={can_perform}, reason={reason}, app={self.app_name}, action={self.action}, "
            f"user={request.user.username}, processus_uuid={processus_uuid}"
        )
        
        if not can_perform:
            raise PermissionDenied(reason or f"Action '{self.action}' non autorisée sur cet objet")
        
        return True


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

class DashboardTableauCreatePermission(AppActionPermission):
    """Permission pour créer un tableau de bord"""
    app_name = 'dashboard'
    action = 'create_tableau_bord'


class DashboardTableauUpdatePermission(AppActionPermission):
    """Permission pour modifier un tableau de bord"""
    app_name = 'dashboard'
    action = 'update_tableau_bord'


class DashboardTableauDeletePermission(AppActionPermission):
    """Permission pour supprimer un tableau de bord"""
    app_name = 'dashboard'
    action = 'delete_tableau_bord'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis le TableauBord via l'UUID dans view.kwargs"""
        # Si obj est fourni (pour has_object_permission)
        if obj and hasattr(obj, 'processus'):
            return str(obj.processus.uuid) if obj.processus else None
        
        # Si obj n'est pas fourni (pour has_permission), récupérer depuis view.kwargs
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            tableau_uuid = view.kwargs['uuid']
            try:
                from dashboard.models import TableauBord
                tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_uuid)
                return str(tableau.processus.uuid) if tableau.processus else None
            except TableauBord.DoesNotExist:
                return None
        
        return None


class DashboardTableauValidatePermission(AppActionPermission):
    """Permission pour valider un tableau de bord"""
    app_name = 'dashboard'
    action = 'validate_tableau_bord'

    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis le TableauBord via l'UUID dans view.kwargs"""
        # Si obj est fourni (pour has_object_permission)
        if obj and hasattr(obj, 'processus'):
            return str(obj.processus.uuid) if obj.processus else None
        
        # Si obj n'est pas fourni (pour has_permission), récupérer depuis view.kwargs
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            tableau_uuid = view.kwargs['uuid']
            try:
                from dashboard.models import TableauBord
                tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_uuid)
                if tableau.processus:
                    return str(tableau.processus.uuid)
            except TableauBord.DoesNotExist:
                logger.warning(f"[DashboardTableauValidatePermission] TableauBord {tableau_uuid} non trouvé.")
            except Exception as e:
                logger.error(f"[DashboardTableauValidatePermission] Erreur lors de l'extraction du processus pour TableauBord {tableau_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardTableauDevalidatePermission(AppActionPermission):
    """Permission pour dévalider un tableau de bord"""
    app_name = 'dashboard'
    action = 'devalidate_tableau_bord'

    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis le TableauBord via l'UUID dans view.kwargs"""
        # Si obj est fourni (pour has_object_permission)
        if obj and hasattr(obj, 'processus'):
            return str(obj.processus.uuid) if obj.processus else None
        
        # Si obj n'est pas fourni (pour has_permission), récupérer depuis view.kwargs
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            tableau_uuid = view.kwargs['uuid']
            try:
                from dashboard.models import TableauBord
                tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_uuid)
                if tableau.processus:
                    return str(tableau.processus.uuid)
            except TableauBord.DoesNotExist:
                logger.warning(f"[DashboardTableauDevalidatePermission] TableauBord {tableau_uuid} non trouvé.")
            except Exception as e:
                logger.error(f"[DashboardTableauDevalidatePermission] Erreur lors de l'extraction du processus pour TableauBord {tableau_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardTableauReadPermission(AppActionPermission):
    """Permission pour lire un tableau de bord"""
    app_name = 'dashboard'
    action = 'read_tableau_bord'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis le TableauBord"""
        # Si obj est fourni (pour has_object_permission)
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
        
        # Si obj n'est pas fourni (pour has_permission), récupérer depuis view.kwargs
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            tableau_uuid = view.kwargs['uuid']
            try:
                from dashboard.models import TableauBord
                tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_uuid)
                if tableau.processus:
                    return str(tableau.processus.uuid)
            except Exception as e:
                logger.warning(f"[DashboardTableauReadPermission] Erreur extraction processus depuis tableau {tableau_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class DashboardAmendementCreatePermission(AppActionPermission):
    """Permission pour créer un amendement"""
    app_name = 'dashboard'
    action = 'create_amendement'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """
        Extrait le processus_uuid depuis tableau_initial_uuid dans les kwargs
        Pour créer un amendement, on doit récupérer le tableau initial pour obtenir son processus
        """
        # 1. Depuis l'objet (si fourni)
        if obj:
            if hasattr(obj, 'processus'):
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
        
        # 2. Depuis view.kwargs : tableau_initial_uuid (cas spécifique pour create_amendement)
        if hasattr(view, 'kwargs') and view.kwargs:
            tableau_initial_uuid = view.kwargs.get('tableau_initial_uuid')
            if tableau_initial_uuid:
                # Récupérer le tableau initial pour obtenir son processus
                try:
                    from dashboard.models import TableauBord
                    initial_tableau = TableauBord.objects.select_related('processus').get(
                        uuid=tableau_initial_uuid,
                        type_tableau__code='INITIAL'
                    )
                    if initial_tableau.processus:
                        return str(initial_tableau.processus.uuid)
                except Exception as e:
                    logger.warning(
                        f"[DashboardAmendementCreatePermission] Erreur lors de la récupération "
                        f"du tableau initial {tableau_initial_uuid}: {str(e)}"
                    )
            
            # Fallback : processus_uuid ou processus dans les kwargs
            processus_uuid = view.kwargs.get('processus_uuid') or view.kwargs.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        # 3. Depuis request.data (pour POST/PUT/PATCH)
        if hasattr(request, 'data') and request.data:
            processus_uuid = request.data.get('processus') or request.data.get('processus_uuid')
            if processus_uuid:
                return str(processus_uuid)
        
        # 4. Depuis query params
        if hasattr(request, 'query_params'):
            processus_uuid = request.query_params.get('processus_uuid') or request.query_params.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        return None


class DashboardObjectiveCreatePermission(AppActionPermission):
    """Permission pour créer un objectif"""
    app_name = 'dashboard'
    action = 'create_objective'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """
        Extrait le processus_uuid depuis tableau_bord UUID dans request.data
        Pour créer un objectif, on doit récupérer le tableau de bord pour obtenir son processus
        """
        # 1. Depuis l'objet (si fourni)
        if obj:
            if hasattr(obj, 'processus'):
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
            # Essayer depuis tableau_bord de l'objectif
            if hasattr(obj, 'tableau_bord') and obj.tableau_bord:
                if hasattr(obj.tableau_bord, 'processus'):
                    return str(obj.tableau_bord.processus.uuid)
        
        # 2. Depuis request.data : tableau_bord UUID (cas pour create objective)
        if hasattr(request, 'data') and request.data:
            tableau_bord_uuid = request.data.get('tableau_bord')
            if tableau_bord_uuid:
                # Récupérer le tableau de bord pour obtenir son processus
                try:
                    from dashboard.models import TableauBord
                    tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_bord_uuid)
                    if tableau.processus:
                        return str(tableau.processus.uuid)
                except Exception as e:
                    logger.warning(
                        f"[DashboardObjectiveCreatePermission] Erreur lors de la récupération "
                        f"du tableau de bord {tableau_bord_uuid}: {str(e)}"
                    )
            
            # Fallback : processus ou processus_uuid directement dans request.data
            processus_uuid = request.data.get('processus') or request.data.get('processus_uuid')
            if processus_uuid:
                return str(processus_uuid)
        
        # 3. Depuis request.body si request.data n'est pas encore parsé (pour POST)
        if hasattr(request, 'body') and request.body and request.method in ['POST', 'PUT', 'PATCH']:
            try:
                import json
                body_data = json.loads(request.body)
                tableau_bord_uuid = body_data.get('tableau_bord')
                if tableau_bord_uuid:
                    try:
                        from dashboard.models import TableauBord
                        tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_bord_uuid)
                        if tableau.processus:
                            return str(tableau.processus.uuid)
                    except Exception as e:
                        logger.warning(
                            f"[DashboardObjectiveCreatePermission] Erreur lors de la récupération "
                            f"du tableau de bord depuis body {tableau_bord_uuid}: {str(e)}"
                        )
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # 4. Depuis view.kwargs (fallback)
        if hasattr(view, 'kwargs') and view.kwargs:
            processus_uuid = view.kwargs.get('processus_uuid') or view.kwargs.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        # 5. Depuis query params (fallback)
        if hasattr(request, 'query_params'):
            processus_uuid = request.query_params.get('processus_uuid') or request.query_params.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        return None


class DashboardObjectiveUpdatePermission(AppActionPermission):
    """Permission pour modifier un objectif"""
    app_name = 'dashboard'
    action = 'update_objective'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'objectif -> tableau_bord -> processus"""
        try:
            # Si obj est fourni (pour has_object_permission)
            if obj:
                if hasattr(obj, 'tableau_bord') and obj.tableau_bord:
                    if hasattr(obj.tableau_bord, 'processus'):
                        processus_uuid = str(obj.tableau_bord.processus.uuid)
                        logger.info(
                            f"[DashboardObjectiveUpdatePermission] ✅ Processus trouvé depuis obj: {processus_uuid}"
                        )
                        return processus_uuid
            
            # Si obj n'est pas fourni (ex: has_permission est appelé avant la récupération de l'objet)
            if not obj and hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
                objective_uuid = view.kwargs['uuid']
                logger.info(
                    f"[DashboardObjectiveUpdatePermission] objective_uuid depuis view.kwargs: {objective_uuid}"
                )
                try:
                    from dashboard.models import Objectives
                    objective = Objectives.objects.select_related('tableau_bord__processus').get(uuid=objective_uuid)
                    if objective.tableau_bord and objective.tableau_bord.processus:
                        processus_uuid = str(objective.tableau_bord.processus.uuid)
                        logger.info(
                            f"[DashboardObjectiveUpdatePermission] ✅ Processus trouvé depuis view.kwargs: {processus_uuid}"
                        )
                        return processus_uuid
                except Objectives.DoesNotExist:
                    logger.warning(f"[DashboardObjectiveUpdatePermission] Objective {objective_uuid} non trouvé pour extraction processus.")
                except Exception as e:
                    logger.error(f"[DashboardObjectiveUpdatePermission] Erreur lors de l'extraction du processus pour Objective {objective_uuid}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[DashboardObjectiveUpdatePermission] Erreur critique dans _extract_processus_uuid: {e}", exc_info=True)
        
        # Si on arrive ici, essayer la méthode parente
        try:
            result = super()._extract_processus_uuid(request, view, obj)
            if result:
                logger.info(f"[DashboardObjectiveUpdatePermission] Processus trouvé via super(): {result}")
            return result
        except Exception as e:
            logger.error(f"[DashboardObjectiveUpdatePermission] Erreur dans super()._extract_processus_uuid: {e}", exc_info=True)
            return None


class DashboardObjectiveDeletePermission(AppActionPermission):
    """Permission pour supprimer un objectif"""
    app_name = 'dashboard'
    action = 'delete_objective'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'objectif -> tableau_bord -> processus"""
        try:
            # Si obj est fourni (pour has_object_permission)
            if obj:
                if hasattr(obj, 'tableau_bord') and obj.tableau_bord:
                    if hasattr(obj.tableau_bord, 'processus'):
                        processus_uuid = str(obj.tableau_bord.processus.uuid)
                        logger.info(
                            f"[DashboardObjectiveDeletePermission] ✅ Processus trouvé depuis obj: {processus_uuid}"
                        )
                        return processus_uuid
            
            # Si obj n'est pas fourni (ex: has_permission est appelé avant la récupération de l'objet)
            if not obj and hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
                objective_uuid = view.kwargs['uuid']
                logger.info(
                    f"[DashboardObjectiveDeletePermission] objective_uuid depuis view.kwargs: {objective_uuid}"
                )
                try:
                    from dashboard.models import Objectives
                    objective = Objectives.objects.select_related('tableau_bord__processus').get(uuid=objective_uuid)
                    if objective.tableau_bord and objective.tableau_bord.processus:
                        processus_uuid = str(objective.tableau_bord.processus.uuid)
                        logger.info(
                            f"[DashboardObjectiveDeletePermission] ✅ Processus trouvé depuis view.kwargs: {processus_uuid}"
                        )
                        return processus_uuid
                except Objectives.DoesNotExist:
                    logger.warning(f"[DashboardObjectiveDeletePermission] Objective {objective_uuid} non trouvé pour extraction processus.")
                except Exception as e:
                    logger.error(f"[DashboardObjectiveDeletePermission] Erreur lors de l'extraction du processus pour Objective {objective_uuid}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[DashboardObjectiveDeletePermission] Erreur critique dans _extract_processus_uuid: {e}", exc_info=True)
        
        # Si on arrive ici, essayer la méthode parente
        try:
            result = super()._extract_processus_uuid(request, view, obj)
            if result:
                logger.info(f"[DashboardObjectiveDeletePermission] Processus trouvé via super(): {result}")
            return result
        except Exception as e:
            logger.error(f"[DashboardObjectiveDeletePermission] Erreur dans super()._extract_processus_uuid: {e}", exc_info=True)
            return None


class DashboardIndicateurCreatePermission(AppActionPermission):
    """Permission pour créer un indicateur"""
    app_name = 'dashboard'
    action = 'create_indicateur'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur -> objective -> tableau_bord"""
        if obj:
            if hasattr(obj, 'objective') and obj.objective:
                if hasattr(obj.objective, 'tableau_bord') and obj.objective.tableau_bord:
                    if hasattr(obj.objective.tableau_bord, 'processus'):
                        return str(obj.objective.tableau_bord.processus.uuid)
        
        # Si objective_id dans request.data, récupérer le processus depuis l'objective
        if hasattr(request, 'data') and request.data:
            objective_id = request.data.get('objective') or request.data.get('objective_id')
            if objective_id:
                try:
                    from dashboard.models import Objectives
                    objective = Objectives.objects.select_related('tableau_bord__processus').get(uuid=objective_id)
                    if objective.tableau_bord and objective.tableau_bord.processus:
                        return str(objective.tableau_bord.processus.uuid)
                except Exception as e:
                    logger.warning(f"[DashboardIndicateurCreatePermission] Erreur: {str(e)}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardIndicateurUpdatePermission(AppActionPermission):
    """Permission pour modifier un indicateur"""
    app_name = 'dashboard'
    action = 'update_indicateur'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur -> objective_id -> tableau_bord"""
        # Si obj est fourni, utiliser directement
        if obj and hasattr(obj, 'objective_id') and obj.objective_id:
            if hasattr(obj.objective_id, 'tableau_bord') and obj.objective_id.tableau_bord:
                if hasattr(obj.objective_id.tableau_bord, 'processus'):
                    return str(obj.objective_id.tableau_bord.processus.uuid)
        
        # Sinon, essayer de récupérer l'indicateur depuis view.kwargs (pour has_permission)
        if hasattr(view, 'kwargs') and view.kwargs:
            indicateur_uuid = view.kwargs.get('uuid')
            if indicateur_uuid:
                try:
                    from dashboard.models import Indicateur
                    indicateur = Indicateur.objects.select_related(
                        'objective_id__tableau_bord__processus'
                    ).get(uuid=indicateur_uuid)
                    if indicateur.objective_id and indicateur.objective_id.tableau_bord:
                        if indicateur.objective_id.tableau_bord.processus:
                            return str(indicateur.objective_id.tableau_bord.processus.uuid)
                except Indicateur.DoesNotExist:
                    logger.warning(f"[DashboardIndicateurUpdatePermission] Indicateur {indicateur_uuid} non trouvé.")
                except Exception as e:
                    logger.error(f"[DashboardIndicateurUpdatePermission] Erreur lors de l'extraction du processus pour Indicateur {indicateur_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardIndicateurDeletePermission(AppActionPermission):
    """Permission pour supprimer un indicateur"""
    app_name = 'dashboard'
    action = 'delete_indicateur'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur -> objective_id -> tableau_bord"""
        try:
            # Si obj est fourni (pour has_object_permission)
            if obj:
                if hasattr(obj, 'objective_id') and obj.objective_id:
                    if hasattr(obj.objective_id, 'tableau_bord') and obj.objective_id.tableau_bord:
                        if hasattr(obj.objective_id.tableau_bord, 'processus'):
                            processus_uuid = str(obj.objective_id.tableau_bord.processus.uuid)
                            logger.info(
                                f"[DashboardIndicateurDeletePermission] ✅ Processus trouvé depuis obj: {processus_uuid}"
                            )
                            return processus_uuid
            
            # Si obj n'est pas fourni (ex: has_permission est appelé avant la récupération de l'objet)
            if not obj and hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
                indicateur_uuid = view.kwargs['uuid']
                logger.info(
                    f"[DashboardIndicateurDeletePermission] indicateur_uuid depuis view.kwargs: {indicateur_uuid}"
                )
                try:
                    from dashboard.models import Indicateur
                    indicateur = Indicateur.objects.select_related('objective_id__tableau_bord__processus').get(uuid=indicateur_uuid)
                    if indicateur.objective_id and indicateur.objective_id.tableau_bord and indicateur.objective_id.tableau_bord.processus:
                        processus_uuid = str(indicateur.objective_id.tableau_bord.processus.uuid)
                        logger.info(
                            f"[DashboardIndicateurDeletePermission] ✅ Processus trouvé depuis view.kwargs: {processus_uuid}"
                        )
                        return processus_uuid
                except Indicateur.DoesNotExist:
                    logger.warning(f"[DashboardIndicateurDeletePermission] Indicateur {indicateur_uuid} non trouvé pour extraction processus.")
                except Exception as e:
                    logger.error(f"[DashboardIndicateurDeletePermission] Erreur lors de l'extraction du processus pour Indicateur {indicateur_uuid}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[DashboardIndicateurDeletePermission] Erreur critique dans _extract_processus_uuid: {e}", exc_info=True)
        
        # Si on arrive ici, essayer la méthode parente
        try:
            result = super()._extract_processus_uuid(request, view, obj)
            if result:
                logger.info(f"[DashboardIndicateurDeletePermission] Processus trouvé via super(): {result}")
            return result
        except Exception as e:
            logger.error(f"[DashboardIndicateurDeletePermission] Erreur dans super()._extract_processus_uuid: {e}", exc_info=True)
            return None


class DashboardCibleCreatePermission(AppActionPermission):
    """Permission pour créer une cible"""
    app_name = 'dashboard'
    action = 'create_cible'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur_id dans request.data"""
        if hasattr(request, 'data') and request.data:
            indicateur_uuid = request.data.get('indicateur_id')
            if indicateur_uuid:
                try:
                    from dashboard.models import Indicateur
                    indicateur = Indicateur.objects.select_related(
                        'objective_id__tableau_bord__processus'
                    ).get(uuid=indicateur_uuid)
                    if indicateur.objective_id and indicateur.objective_id.tableau_bord:
                        if indicateur.objective_id.tableau_bord.processus:
                            return str(indicateur.objective_id.tableau_bord.processus.uuid)
                except Indicateur.DoesNotExist:
                    logger.warning(f"[DashboardCibleCreatePermission] Indicateur {indicateur_uuid} non trouvé.")
                except Exception as e:
                    logger.error(f"[DashboardCibleCreatePermission] Erreur lors de l'extraction du processus pour Indicateur {indicateur_uuid}: {e}")
        
        # Essayer aussi depuis request.body si request.data n'est pas encore parsé
        if hasattr(request, 'body') and request.body and request.method == 'POST':
            try:
                import json
                body_data = json.loads(request.body)
                indicateur_uuid = body_data.get('indicateur_id')
                if indicateur_uuid:
                    from dashboard.models import Indicateur
                    indicateur = Indicateur.objects.select_related(
                        'objective_id__tableau_bord__processus'
                    ).get(uuid=indicateur_uuid)
                    if indicateur.objective_id and indicateur.objective_id.tableau_bord:
                        if indicateur.objective_id.tableau_bord.processus:
                            return str(indicateur.objective_id.tableau_bord.processus.uuid)
            except (json.JSONDecodeError, Indicateur.DoesNotExist, Exception) as e:
                logger.warning(f"[DashboardCibleCreatePermission] Erreur lors de l'extraction depuis body: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardCibleUpdatePermission(AppActionPermission):
    """Permission pour modifier une cible"""
    app_name = 'dashboard'
    action = 'update_cible'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis la cible -> indicateur -> objective_id -> tableau_bord"""
        # Si obj est fourni, utiliser directement
        if obj and hasattr(obj, 'indicateur_id') and obj.indicateur_id:
            try:
                from dashboard.models import Indicateur
                indicateur = Indicateur.objects.select_related(
                    'objective_id__tableau_bord__processus'
                ).get(uuid=obj.indicateur_id.uuid)
                if indicateur.objective_id and indicateur.objective_id.tableau_bord:
                    if indicateur.objective_id.tableau_bord.processus:
                        return str(indicateur.objective_id.tableau_bord.processus.uuid)
            except Exception as e:
                logger.warning(f"[DashboardCibleUpdatePermission] Erreur avec obj: {e}")
        
        # Sinon, essayer de récupérer la cible depuis view.kwargs (pour has_permission)
        if hasattr(view, 'kwargs') and view.kwargs:
            cible_uuid = view.kwargs.get('uuid')
            if cible_uuid:
                try:
                    from parametre.models import Cible
                    from dashboard.models import Indicateur
                    cible = Cible.objects.select_related('indicateur_id').get(uuid=cible_uuid)
                    if cible.indicateur_id:
                        indicateur = Indicateur.objects.select_related(
                            'objective_id__tableau_bord__processus'
                        ).get(uuid=cible.indicateur_id.uuid)
                        if indicateur.objective_id and indicateur.objective_id.tableau_bord:
                            if indicateur.objective_id.tableau_bord.processus:
                                return str(indicateur.objective_id.tableau_bord.processus.uuid)
                except Exception as e:
                    logger.warning(f"[DashboardCibleUpdatePermission] Erreur lors de l'extraction du processus pour Cible {cible_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardCibleDeletePermission(AppActionPermission):
    """Permission pour supprimer une cible"""
    app_name = 'dashboard'
    action = 'delete_cible'


class DashboardPeriodiciteCreatePermission(AppActionPermission):
    """Permission pour créer une périodicité"""
    app_name = 'dashboard'
    action = 'create_periodicite'

    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur_id dans request.data"""
        if hasattr(request, 'data') and request.data:
            indicateur_uuid = request.data.get('indicateur_id')
            if indicateur_uuid:
                try:
                    from dashboard.models import Indicateur
                    indicateur = Indicateur.objects.select_related('objective_id__tableau_bord__processus').get(uuid=indicateur_uuid)
                    if indicateur.objective_id and indicateur.objective_id.tableau_bord and indicateur.objective_id.tableau_bord.processus:
                        return str(indicateur.objective_id.tableau_bord.processus.uuid)
                except Indicateur.DoesNotExist:
                    logger.warning(f"[DashboardPeriodiciteCreatePermission] Indicateur {indicateur_uuid} non trouvé.")
                except Exception as e:
                    logger.error(f"[DashboardPeriodiciteCreatePermission] Erreur lors de l'extraction du processus pour Indicateur {indicateur_uuid}: {e}")
        
        # Fallback pour request.body si request.data n'est pas encore parsé
        if hasattr(request, 'body') and request.body and request.method in ['POST', 'PUT', 'PATCH']:
            try:
                import json
                body_data = json.loads(request.body)
                indicateur_uuid = body_data.get('indicateur_id')
                if indicateur_uuid:
                    from dashboard.models import Indicateur
                    indicateur = Indicateur.objects.select_related('objective_id__tableau_bord__processus').get(uuid=indicateur_uuid)
                    if indicateur.objective_id and indicateur.objective_id.tableau_bord and indicateur.objective_id.tableau_bord.processus:
                        return str(indicateur.objective_id.tableau_bord.processus.uuid)
            except (json.JSONDecodeError, Indicateur.DoesNotExist, Exception) as e:
                logger.warning(f"[DashboardPeriodiciteCreatePermission] Erreur lors de l'extraction depuis body: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardPeriodiciteUpdatePermission(AppActionPermission):
    """Permission pour modifier une périodicité"""
    app_name = 'dashboard'
    action = 'update_periodicite'

    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis la périodicité -> indicateur -> objective -> tableau_bord"""
        if obj:
            if hasattr(obj, 'indicateur_id') and obj.indicateur_id:
                if hasattr(obj.indicateur_id, 'objective_id') and obj.indicateur_id.objective_id:
                    if hasattr(obj.indicateur_id.objective_id, 'tableau_bord') and obj.indicateur_id.objective_id.tableau_bord:
                        if hasattr(obj.indicateur_id.objective_id.tableau_bord, 'processus'):
                            return str(obj.indicateur_id.objective_id.tableau_bord.processus.uuid)
        
        # Si obj n'est pas fourni (ex: has_permission est appelé avant la récupération de l'objet)
        if not obj and hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            periodicite_uuid = view.kwargs['uuid']
            try:
                from parametre.models import Periodicite
                periodicite = Periodicite.objects.select_related('indicateur_id__objective_id__tableau_bord__processus').get(uuid=periodicite_uuid)
                if periodicite.indicateur_id and periodicite.indicateur_id.objective_id and periodicite.indicateur_id.objective_id.tableau_bord and periodicite.indicateur_id.objective_id.tableau_bord.processus:
                    return str(periodicite.indicateur_id.objective_id.tableau_bord.processus.uuid)
            except Periodicite.DoesNotExist:
                logger.warning(f"[DashboardPeriodiciteUpdatePermission] Periodicite {periodicite_uuid} non trouvée pour extraction processus.")
            except Exception as e:
                logger.error(f"[DashboardPeriodiciteUpdatePermission] Erreur lors de l'extraction du processus pour Periodicite {periodicite_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardPeriodiciteDeletePermission(AppActionPermission):
    """Permission pour supprimer une périodicité"""
    app_name = 'dashboard'
    action = 'delete_periodicite'


class DashboardFrequenceUpdatePermission(AppActionPermission):
    """Permission pour modifier la fréquence d'un indicateur"""
    app_name = 'dashboard'
    action = 'update_frequence'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur"""
        # La fréquence est modifiée via l'indicateur
        # Si on a l'UUID de l'indicateur dans request.data
        if hasattr(request, 'data') and request.data:
            indicateur_uuid = request.data.get('indicateur_uuid') or request.data.get('uuid')
            if indicateur_uuid:
                try:
                    from dashboard.models import Indicateur
                    indicateur = Indicateur.objects.select_related(
                        'objective_id__tableau_bord__processus'
                    ).get(uuid=indicateur_uuid)
                    if indicateur.objective_id and indicateur.objective_id.tableau_bord:
                        if indicateur.objective_id.tableau_bord.processus:
                            return str(indicateur.objective_id.tableau_bord.processus.uuid)
                except Exception as e:
                    logger.warning(f"[DashboardFrequenceUpdatePermission] Erreur: {str(e)}")
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardObservationCreatePermission(AppActionPermission):
    """Permission pour créer une observation"""
    app_name = 'dashboard'
    action = 'create_observation'

    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur_id dans request.data"""
        try:
            # Essayer depuis request.data (si déjà parsé par DRF)
            if hasattr(request, 'data') and request.data:
                indicateur_uuid = request.data.get('indicateur_id')
                if indicateur_uuid:
                    try:
                        from dashboard.models import Indicateur
                        indicateur = Indicateur.objects.select_related('objective_id__tableau_bord__processus').get(uuid=indicateur_uuid)
                        if indicateur.objective_id and indicateur.objective_id.tableau_bord and indicateur.objective_id.tableau_bord.processus:
                            processus_uuid = str(indicateur.objective_id.tableau_bord.processus.uuid)
                            logger.info(
                                f"[DashboardObservationCreatePermission] ✅ Processus trouvé depuis request.data: {processus_uuid}"
                            )
                            return processus_uuid
                    except Indicateur.DoesNotExist:
                        logger.warning(f"[DashboardObservationCreatePermission] Indicateur {indicateur_uuid} non trouvé.")
                    except Exception as e:
                        logger.error(f"[DashboardObservationCreatePermission] Erreur extraction depuis request.data: {e}", exc_info=True)
            
            # Fallback pour request.body si request.data n'est pas encore parsé
            if hasattr(request, 'body') and request.body and request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    import json
                    # Vérifier si request.body est déjà un bytes ou string
                    body_str = request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body
                    body_data = json.loads(body_str)
                    indicateur_uuid = body_data.get('indicateur_id')
                    if indicateur_uuid:
                        from dashboard.models import Indicateur
                        indicateur = Indicateur.objects.select_related('objective_id__tableau_bord__processus').get(uuid=indicateur_uuid)
                        if indicateur.objective_id and indicateur.objective_id.tableau_bord and indicateur.objective_id.tableau_bord.processus:
                            processus_uuid = str(indicateur.objective_id.tableau_bord.processus.uuid)
                            logger.info(
                                f"[DashboardObservationCreatePermission] ✅ Processus trouvé depuis request.body: {processus_uuid}"
                            )
                            return processus_uuid
                except (json.JSONDecodeError, UnicodeDecodeError, Indicateur.DoesNotExist) as e:
                    logger.warning(f"[DashboardObservationCreatePermission] Erreur extraction depuis body: {e}")
                except Exception as e:
                    logger.error(f"[DashboardObservationCreatePermission] Erreur inattendue extraction depuis body: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[DashboardObservationCreatePermission] Erreur critique dans _extract_processus_uuid: {e}", exc_info=True)
        
        # Si on arrive ici, essayer la méthode parente
        try:
            result = super()._extract_processus_uuid(request, view, obj)
            if result:
                logger.info(f"[DashboardObservationCreatePermission] Processus trouvé via super(): {result}")
            return result
        except Exception as e:
            logger.error(f"[DashboardObservationCreatePermission] Erreur dans super()._extract_processus_uuid: {e}", exc_info=True)
            return None


class DashboardObservationUpdatePermission(AppActionPermission):
    """Permission pour modifier une observation"""
    app_name = 'dashboard'
    action = 'update_observation'

    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'observation -> indicateur -> objective -> tableau_bord"""
        logger.info(
            f"[DashboardObservationUpdatePermission._extract_processus_uuid] 🔍 Début extraction: "
            f"has_obj={obj is not None}, "
            f"has_view_kwargs={hasattr(view, 'kwargs') and bool(view.kwargs)}"
        )
        
        if obj:
            if hasattr(obj, 'indicateur_id') and obj.indicateur_id:
                if hasattr(obj.indicateur_id, 'objective_id') and obj.indicateur_id.objective_id:
                    if hasattr(obj.indicateur_id.objective_id, 'tableau_bord') and obj.indicateur_id.objective_id.tableau_bord:
                        if hasattr(obj.indicateur_id.objective_id.tableau_bord, 'processus'):
                            processus_uuid = str(obj.indicateur_id.objective_id.tableau_bord.processus.uuid)
                            logger.info(
                                f"[DashboardObservationUpdatePermission._extract_processus_uuid] ✅ "
                                f"Processus trouvé depuis obj: {processus_uuid}"
                            )
                            return processus_uuid
        
        # Si obj n'est pas fourni (ex: has_permission est appelé avant la récupération de l'objet)
        if not obj and hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            observation_uuid = view.kwargs['uuid']
            logger.info(
                f"[DashboardObservationUpdatePermission._extract_processus_uuid] "
                f"observation_uuid depuis view.kwargs: {observation_uuid}"
            )
            try:
                from dashboard.models import Observation
                observation = Observation.objects.select_related('indicateur_id__objective_id__tableau_bord__processus').get(uuid=observation_uuid)
                if observation.indicateur_id and observation.indicateur_id.objective_id and observation.indicateur_id.objective_id.tableau_bord and observation.indicateur_id.objective_id.tableau_bord.processus:
                    processus_uuid = str(observation.indicateur_id.objective_id.tableau_bord.processus.uuid)
                    logger.info(
                        f"[DashboardObservationUpdatePermission._extract_processus_uuid] ✅ "
                        f"Processus trouvé depuis view.kwargs: {processus_uuid}"
                    )
                    return processus_uuid
            except Observation.DoesNotExist:
                logger.warning(f"[DashboardObservationUpdatePermission] Observation {observation_uuid} non trouvée pour extraction processus.")
            except Exception as e:
                logger.error(f"[DashboardObservationUpdatePermission] Erreur lors de l'extraction du processus pour Observation {observation_uuid}: {e}", exc_info=True)
        
        logger.info(
            f"[DashboardObservationUpdatePermission._extract_processus_uuid] ⚠️ "
            f"Aucun processus trouvé, appel de super()._extract_processus_uuid"
        )
        result = super()._extract_processus_uuid(request, view, obj)
        logger.info(
            f"[DashboardObservationUpdatePermission._extract_processus_uuid] "
            f"Résultat super()._extract_processus_uuid: {result}"
        )
        return result


class DashboardObservationDeletePermission(AppActionPermission):
    """Permission pour supprimer une observation"""
    app_name = 'dashboard'
    action = 'delete_observation'

    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'observation -> indicateur -> objective -> tableau_bord"""
        try:
            # Si obj est fourni (pour has_object_permission)
            if obj:
                if hasattr(obj, 'indicateur_id') and obj.indicateur_id:
                    if hasattr(obj.indicateur_id, 'objective_id') and obj.indicateur_id.objective_id:
                        if hasattr(obj.indicateur_id.objective_id, 'tableau_bord') and obj.indicateur_id.objective_id.tableau_bord:
                            if hasattr(obj.indicateur_id.objective_id.tableau_bord, 'processus'):
                                processus_uuid = str(obj.indicateur_id.objective_id.tableau_bord.processus.uuid)
                                logger.info(
                                    f"[DashboardObservationDeletePermission] ✅ Processus trouvé depuis obj: {processus_uuid}"
                                )
                                return processus_uuid
            
            # Si obj n'est pas fourni (ex: has_permission est appelé avant la récupération de l'objet)
            if not obj and hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
                observation_uuid = view.kwargs['uuid']
                logger.info(
                    f"[DashboardObservationDeletePermission] observation_uuid depuis view.kwargs: {observation_uuid}"
                )
                try:
                    from dashboard.models import Observation
                    observation = Observation.objects.select_related('indicateur_id__objective_id__tableau_bord__processus').get(uuid=observation_uuid)
                    if observation.indicateur_id and observation.indicateur_id.objective_id and observation.indicateur_id.objective_id.tableau_bord and observation.indicateur_id.objective_id.tableau_bord.processus:
                        processus_uuid = str(observation.indicateur_id.objective_id.tableau_bord.processus.uuid)
                        logger.info(
                            f"[DashboardObservationDeletePermission] ✅ Processus trouvé depuis view.kwargs: {processus_uuid}"
                        )
                        return processus_uuid
                except Observation.DoesNotExist:
                    logger.warning(f"[DashboardObservationDeletePermission] Observation {observation_uuid} non trouvée pour extraction processus.")
                except Exception as e:
                    logger.error(f"[DashboardObservationDeletePermission] Erreur lors de l'extraction du processus pour Observation {observation_uuid}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[DashboardObservationDeletePermission] Erreur critique dans _extract_processus_uuid: {e}", exc_info=True)
        
        # Si on arrive ici, essayer la méthode parente
        try:
            result = super()._extract_processus_uuid(request, view, obj)
            if result:
                logger.info(f"[DashboardObservationDeletePermission] Processus trouvé via super(): {result}")
            return result
        except Exception as e:
            logger.error(f"[DashboardObservationDeletePermission] Erreur dans super()._extract_processus_uuid: {e}", exc_info=True)
            return None


# ==================== ANALYSE TABLEAU ====================

class AnalyseTableauCreatePermission(AppActionPermission):
    """Permission pour créer une analyse de tableau de bord"""
    app_name = 'dashboard'
    action = 'create_analyse_tableau'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis tableau_bord_uuid dans request.data"""
        # Si obj est fourni (pour has_object_permission)
        if obj:
            if hasattr(obj, 'tableau_bord') and obj.tableau_bord:
                if hasattr(obj.tableau_bord, 'processus') and obj.tableau_bord.processus:
                    return str(obj.tableau_bord.processus.uuid)
        
        # Depuis request.data (si déjà parsé par DRF)
        if hasattr(request, 'data') and request.data:
            tableau_bord_uuid = request.data.get('tableau_bord_uuid')
            if tableau_bord_uuid:
                try:
                    from dashboard.models import TableauBord
                    tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_bord_uuid)
                    if tableau.processus:
                        return str(tableau.processus.uuid)
                except TableauBord.DoesNotExist:
                    logger.warning(f"[AnalyseTableauCreatePermission] TableauBord {tableau_bord_uuid} non trouvé.")
                except Exception as e:
                    logger.error(f"[AnalyseTableauCreatePermission] Erreur extraction processus: {e}")
        
        # Fallback pour request.body si request.data n'est pas encore parsé
        if hasattr(request, 'body') and request.body and request.method == 'POST':
            try:
                import json
                body_data = json.loads(request.body)
                tableau_bord_uuid = body_data.get('tableau_bord_uuid')
                if tableau_bord_uuid:
                    from dashboard.models import TableauBord
                    tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_bord_uuid)
                    if tableau.processus:
                        return str(tableau.processus.uuid)
            except (json.JSONDecodeError, TableauBord.DoesNotExist, Exception) as e:
                logger.warning(f"[AnalyseTableauCreatePermission] Erreur extraction depuis body: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class AnalyseLigneCreatePermission(AppActionPermission):
    """Permission pour créer une ligne d'analyse"""
    app_name = 'dashboard'
    action = 'create_analyse_ligne'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis tableau_bord_uuid dans request.data"""
        # Depuis request.data (si déjà parsé par DRF)
        if hasattr(request, 'data') and request.data:
            tableau_bord_uuid = request.data.get('tableau_bord_uuid')
            if tableau_bord_uuid:
                try:
                    from dashboard.models import TableauBord
                    tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_bord_uuid)
                    if tableau.processus:
                        return str(tableau.processus.uuid)
                except TableauBord.DoesNotExist:
                    logger.warning(f"[AnalyseLigneCreatePermission] TableauBord {tableau_bord_uuid} non trouvé.")
                except Exception as e:
                    logger.error(f"[AnalyseLigneCreatePermission] Erreur extraction processus: {e}")
        
        # Fallback pour request.body si request.data n'est pas encore parsé
        if hasattr(request, 'body') and request.body and request.method == 'POST':
            try:
                import json
                body_data = json.loads(request.body)
                tableau_bord_uuid = body_data.get('tableau_bord_uuid')
                if tableau_bord_uuid:
                    from dashboard.models import TableauBord
                    tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_bord_uuid)
                    if tableau.processus:
                        return str(tableau.processus.uuid)
            except (json.JSONDecodeError, TableauBord.DoesNotExist, Exception) as e:
                logger.warning(f"[AnalyseLigneCreatePermission] Erreur extraction depuis body: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class AnalyseLigneUpdatePermission(AppActionPermission):
    """Permission pour modifier une ligne d'analyse"""
    app_name = 'dashboard'
    action = 'update_analyse_ligne'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis la ligne -> analyse_tableau -> tableau_bord -> processus"""
        # Si obj est fourni (pour has_object_permission)
        if obj:
            if hasattr(obj, 'analyse_tableau') and obj.analyse_tableau:
                if hasattr(obj.analyse_tableau, 'tableau_bord') and obj.analyse_tableau.tableau_bord:
                    if hasattr(obj.analyse_tableau.tableau_bord, 'processus') and obj.analyse_tableau.tableau_bord.processus:
                        return str(obj.analyse_tableau.tableau_bord.processus.uuid)
        
        # Depuis view.kwargs (pour has_permission)
        if hasattr(view, 'kwargs') and view.kwargs.get('ligne_uuid'):
            ligne_uuid = view.kwargs['ligne_uuid']
            try:
                from analyse_tableau.models import AnalyseLigne
                ligne = AnalyseLigne.objects.select_related(
                    'analyse_tableau__tableau_bord__processus'
                ).get(uuid=ligne_uuid)
                if ligne.analyse_tableau and ligne.analyse_tableau.tableau_bord:
                    if ligne.analyse_tableau.tableau_bord.processus:
                        return str(ligne.analyse_tableau.tableau_bord.processus.uuid)
            except AnalyseLigne.DoesNotExist:
                logger.warning(f"[AnalyseLigneUpdatePermission] AnalyseLigne {ligne_uuid} non trouvée.")
            except Exception as e:
                logger.error(f"[AnalyseLigneUpdatePermission] Erreur extraction processus: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class AnalyseActionCreatePermission(AppActionPermission):
    """Permission pour créer une action d'analyse"""
    app_name = 'dashboard'
    action = 'create_analyse_action'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis ligne (UUID) dans request.data -> analyse_tableau -> tableau_bord -> processus"""
        # Depuis request.data (si déjà parsé par DRF)
        if hasattr(request, 'data') and request.data:
            ligne_uuid = request.data.get('ligne')
            if ligne_uuid:
                try:
                    from analyse_tableau.models import AnalyseLigne
                    # ligne peut être un UUID string ou un objet
                    ligne_uuid_str = str(ligne_uuid) if not isinstance(ligne_uuid, str) else ligne_uuid
                    ligne = AnalyseLigne.objects.select_related(
                        'analyse_tableau__tableau_bord__processus'
                    ).get(uuid=ligne_uuid_str)
                    if ligne.analyse_tableau and ligne.analyse_tableau.tableau_bord:
                        if ligne.analyse_tableau.tableau_bord.processus:
                            return str(ligne.analyse_tableau.tableau_bord.processus.uuid)
                except AnalyseLigne.DoesNotExist:
                    logger.warning(f"[AnalyseActionCreatePermission] AnalyseLigne {ligne_uuid} non trouvée.")
                except Exception as e:
                    logger.error(f"[AnalyseActionCreatePermission] Erreur extraction processus: {e}")
        
        # Fallback pour request.body si request.data n'est pas encore parsé
        if hasattr(request, 'body') and request.body and request.method == 'POST':
            try:
                import json
                body_data = json.loads(request.body)
                ligne_uuid = body_data.get('ligne')
                if ligne_uuid:
                    from analyse_tableau.models import AnalyseLigne
                    ligne_uuid_str = str(ligne_uuid) if not isinstance(ligne_uuid, str) else ligne_uuid
                    ligne = AnalyseLigne.objects.select_related(
                        'analyse_tableau__tableau_bord__processus'
                    ).get(uuid=ligne_uuid_str)
                    if ligne.analyse_tableau and ligne.analyse_tableau.tableau_bord:
                        if ligne.analyse_tableau.tableau_bord.processus:
                            return str(ligne.analyse_tableau.tableau_bord.processus.uuid)
            except (json.JSONDecodeError, AnalyseLigne.DoesNotExist, Exception) as e:
                logger.warning(f"[AnalyseActionCreatePermission] Erreur extraction depuis body: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class AnalyseActionUpdatePermission(AppActionPermission):
    """Permission pour modifier une action d'analyse"""
    app_name = 'dashboard'
    action = 'update_analyse_action'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'action -> ligne -> analyse_tableau -> tableau_bord -> processus"""
        # Si obj est fourni (pour has_object_permission)
        if obj:
            if hasattr(obj, 'ligne') and obj.ligne:
                if hasattr(obj.ligne, 'analyse_tableau') and obj.ligne.analyse_tableau:
                    if hasattr(obj.ligne.analyse_tableau, 'tableau_bord') and obj.ligne.analyse_tableau.tableau_bord:
                        if hasattr(obj.ligne.analyse_tableau.tableau_bord, 'processus') and obj.ligne.analyse_tableau.tableau_bord.processus:
                            return str(obj.ligne.analyse_tableau.tableau_bord.processus.uuid)
        
        # Depuis view.kwargs (pour has_permission)
        if hasattr(view, 'kwargs') and view.kwargs.get('action_uuid'):
            action_uuid = view.kwargs['action_uuid']
            try:
                from analyse_tableau.models import AnalyseAction
                action = AnalyseAction.objects.select_related(
                    'ligne__analyse_tableau__tableau_bord__processus'
                ).get(uuid=action_uuid)
                if action.ligne and action.ligne.analyse_tableau:
                    if action.ligne.analyse_tableau.tableau_bord:
                        if action.ligne.analyse_tableau.tableau_bord.processus:
                            return str(action.ligne.analyse_tableau.tableau_bord.processus.uuid)
            except AnalyseAction.DoesNotExist:
                logger.warning(f"[AnalyseActionUpdatePermission] AnalyseAction {action_uuid} non trouvée.")
            except Exception as e:
                logger.error(f"[AnalyseActionUpdatePermission] Erreur extraction processus: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class AnalyseActionDeletePermission(AppActionPermission):
    """Permission pour supprimer une action d'analyse"""
    app_name = 'dashboard'
    action = 'delete_analyse_action'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'action -> ligne -> analyse_tableau -> tableau_bord -> processus"""
        # Si obj est fourni (pour has_object_permission)
        if obj:
            if hasattr(obj, 'ligne') and obj.ligne:
                if hasattr(obj.ligne, 'analyse_tableau') and obj.ligne.analyse_tableau:
                    if hasattr(obj.ligne.analyse_tableau, 'tableau_bord') and obj.ligne.analyse_tableau.tableau_bord:
                        if hasattr(obj.ligne.analyse_tableau.tableau_bord, 'processus') and obj.ligne.analyse_tableau.tableau_bord.processus:
                            return str(obj.ligne.analyse_tableau.tableau_bord.processus.uuid)
        
        # Depuis view.kwargs (pour has_permission)
        if hasattr(view, 'kwargs') and view.kwargs.get('action_uuid'):
            action_uuid = view.kwargs['action_uuid']
            try:
                from analyse_tableau.models import AnalyseAction
                action = AnalyseAction.objects.select_related(
                    'ligne__analyse_tableau__tableau_bord__processus'
                ).get(uuid=action_uuid)
                if action.ligne and action.ligne.analyse_tableau:
                    if action.ligne.analyse_tableau.tableau_bord:
                        if action.ligne.analyse_tableau.tableau_bord.processus:
                            return str(action.ligne.analyse_tableau.tableau_bord.processus.uuid)
            except AnalyseAction.DoesNotExist:
                logger.warning(f"[AnalyseActionDeletePermission] AnalyseAction {action_uuid} non trouvée.")
            except Exception as e:
                logger.error(f"[AnalyseActionDeletePermission] Erreur extraction processus: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


# ==================== PERMISSIONS MULTI-MÉTHODES ====================

class DashboardTableauListCreatePermission(BasePermission):
    """
    Permission pour tableaux_bord_list_create qui gère GET et POST
    GET : DashboardTableauReadPermission
    POST : DashboardTableauCreatePermission
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.method == 'GET':
            # Pour GET, vérifier read_tableau_bord mais on doit avoir accès au processus
            # La vérification se fait dans la vue avec get_user_processus_list
            return True  # GET est autorisé si authentifié, le filtrage se fait dans la vue
        elif request.method == 'POST':
            # Pour POST, utiliser DashboardTableauCreatePermission
            # IMPORTANT: Ne pas faire return, laisser l'exception PermissionDenied se propager
            permission = DashboardTableauCreatePermission()
            # Si has_permission lève une exception PermissionDenied, elle sera propagée automatiquement par DRF
            # Si elle retourne True, on retourne True
            # Si elle retourne False, on retourne False
            result = permission.has_permission(request, view)
            return result
        return False


class DashboardTableauDetailPermission(BasePermission):
    """
    Permission pour tableau_bord_detail qui gère GET, PATCH et DELETE
    GET : DashboardTableauReadPermission
    PATCH : DashboardTableauUpdatePermission
    DELETE : DashboardTableauDeletePermission
    
    Note: Pour les @api_view, DRF ne passe pas automatiquement par has_object_permission.
    On doit donc vérifier dans has_permission en extrayant l'objet depuis view.kwargs.
    """
    def has_permission(self, request, view):
        """
        Security by Design : Vérifie les permissions AVANT toute requête DB
        Refus par défaut si l'objet n'existe pas ou si les permissions échouent
        """
        if not request.user or not request.user.is_authenticated:
            raise PermissionDenied("Authentification requise")
        
        # Extraire l'UUID depuis les kwargs de la vue
        tableau_uuid = view.kwargs.get('uuid')
        if not tableau_uuid:
            raise PermissionDenied("UUID du tableau de bord manquant")
        
        # Récupérer l'objet TableauBord pour avoir le processus_uuid
        # Security by Design : On doit récupérer l'objet pour vérifier les permissions,
        # mais on le fait dans la permission pour garantir que la vérification se fait avant
        try:
            from dashboard.models import TableauBord
            tableau = TableauBord.objects.get(uuid=tableau_uuid)
        except TableauBord.DoesNotExist:
            # Security by Design : Refus par défaut - ne pas révéler si l'objet existe ou non
            raise PermissionDenied("Accès refusé à ce tableau de bord")
        
        # Vérifier selon la méthode HTTP
        if request.method == 'GET':
            permission = DashboardTableauReadPermission()
            if not permission.has_object_permission(request, view, tableau):
                raise PermissionDenied("Vous n'avez pas la permission de lire ce tableau de bord")
        elif request.method == 'PATCH':
            permission = DashboardTableauUpdatePermission()
            if not permission.has_object_permission(request, view, tableau):
                raise PermissionDenied("Vous n'avez pas la permission de modifier ce tableau de bord")
        elif request.method == 'DELETE':
            permission = DashboardTableauDeletePermission()
            if not permission.has_object_permission(request, view, tableau):
                raise PermissionDenied("Vous n'avez pas la permission de supprimer ce tableau de bord")
        else:
            raise PermissionDenied(f"Méthode HTTP '{request.method}' non autorisée")
        
        return True


# ==================== PAC (Plan d'Action de Conformité) ====================

class PACCreatePermission(AppActionPermission):
    """Permission pour créer un PAC"""
    app_name = 'pac'
    action = 'create_pac'


class PACUpdatePermission(AppActionPermission):
    """Permission pour modifier un PAC"""
    app_name = 'pac'
    action = 'update_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        # Si obj est fourni et c'est un objet Pac
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
            pac_uuid = view.kwargs['uuid']
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    return str(pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACUpdatePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class PACDeletePermission(AppActionPermission):
    """Permission pour supprimer un PAC"""
    app_name = 'pac'
    action = 'delete_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        # Si obj est fourni et c'est un objet Pac
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
            pac_uuid = view.kwargs['uuid']
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    return str(pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDeletePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class PACValidatePermission(AppActionPermission):
    """Permission pour valider un PAC"""
    app_name = 'pac'
    action = 'validate_pac'


class PacListPermission(BasePermission):
    """
    Permission pour pac_list qui gère GET
    GET : Autorise si authentifié, le filtrage se fait dans la vue avec get_user_processus_list
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.method == 'GET':
            # Pour GET, autoriser si authentifié, le filtrage se fait dans la vue
            return True
        return False


class PacDetailPermission(BasePermission):
    """
    Permission pour pac_detail et pac_complet qui gèrent GET, PATCH et DELETE
    GET : PACReadPermission
    PATCH : PACUpdatePermission
    DELETE : PACDeletePermission
    
    Note: Pour les @api_view, DRF ne passe pas automatiquement par has_object_permission.
    On doit donc vérifier dans has_permission en extrayant l'objet depuis view.kwargs.
    """
    def has_permission(self, request, view):
        """
        Security by Design : Vérifie les permissions AVANT toute requête DB
        Refus par défaut si l'objet n'existe pas ou si les permissions échouent
        """
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"[PacDetailPermission] Utilisateur non authentifié")
            raise PermissionDenied("Authentification requise")
        
        # Extraire l'UUID depuis les kwargs de la vue
        pac_uuid = view.kwargs.get('uuid')
        if not pac_uuid:
            logger.warning(f"[PacDetailPermission] UUID du PAC manquant pour user={request.user.username}")
            raise PermissionDenied("UUID du PAC manquant")
        
        logger.info(
            f"[PacDetailPermission] 🔍 Début vérification permission: "
            f"user={request.user.username}, method={request.method}, pac_uuid={pac_uuid}"
        )
        
        # Récupérer l'objet Pac pour avoir le processus_uuid
        # Security by Design : On doit récupérer l'objet pour vérifier les permissions,
        # mais on le fait dans la permission pour garantir que la vérification se fait avant
        try:
            from pac.models import Pac
            from parametre.permissions import user_has_access_to_processus
            pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
            logger.info(
                f"[PacDetailPermission] ✅ PAC trouvé: uuid={pac.uuid}, processus_uuid={pac.processus.uuid if pac.processus else None}"
            )
        except Pac.DoesNotExist:
            # Security by Design : Refus par défaut - ne pas révéler si l'objet existe ou non
            logger.warning(f"[PacDetailPermission] ❌ PAC non trouvé: uuid={pac_uuid}")
            raise PermissionDenied("Accès refusé à ce PAC")
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not pac.processus:
            logger.warning(f"[PacDetailPermission] ❌ PAC sans processus: uuid={pac_uuid}")
            raise PermissionDenied("Ce PAC n'est associé à aucun processus")
        
        processus_uuid = str(pac.processus.uuid)
        has_access = user_has_access_to_processus(request.user, processus_uuid)
        logger.info(
            f"[PacDetailPermission] 🔍 Vérification accès processus: "
            f"user={request.user.username}, processus_uuid={processus_uuid}, has_access={has_access}"
        )
        
        if not has_access:
            logger.warning(
                f"[PacDetailPermission] ❌ Accès refusé au processus: "
                f"user={request.user.username}, processus_uuid={processus_uuid}"
            )
            raise PermissionDenied("Vous n'avez pas accès au processus de ce PAC")
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier selon la méthode HTTP
        try:
            if request.method == 'GET':
                logger.info(f"[PacDetailPermission] 🔍 Vérification permission read_pac pour user={request.user.username}")
                permission = PACReadPermission()
                permission.has_object_permission(request, view, pac)
                logger.info(f"[PacDetailPermission] ✅ Permission read_pac accordée")
            elif request.method in ['PATCH', 'PUT']:
                logger.info(f"[PacDetailPermission] 🔍 Vérification permission update_pac pour user={request.user.username}")
                permission = PACUpdatePermission()
                permission.has_object_permission(request, view, pac)
                logger.info(f"[PacDetailPermission] ✅ Permission update_pac accordée")
            elif request.method == 'DELETE':
                logger.info(f"[PacDetailPermission] 🔍 Vérification permission delete_pac pour user={request.user.username}")
                permission = PACDeletePermission()
                permission.has_object_permission(request, view, pac)
                logger.info(f"[PacDetailPermission] ✅ Permission delete_pac accordée")
            else:
                logger.warning(f"[PacDetailPermission] ❌ Méthode HTTP non autorisée: {request.method}")
                raise PermissionDenied(f"Méthode HTTP '{request.method}' non autorisée")
        except PermissionDenied as e:
            # Re-lever l'exception pour que DRF la gère correctement
            logger.warning(f"[PacDetailPermission] ❌ Permission refusée: {e}")
            raise
        except Exception as e:
            # Logger l'erreur et refuser l'accès par sécurité
            logger.error(f"[PacDetailPermission] ❌ Erreur lors de la vérification de permission: {e}", exc_info=True)
            raise PermissionDenied("Erreur lors de la vérification des permissions")
        
        logger.info(f"[PacDetailPermission] ✅ Permission accordée pour user={request.user.username}, method={request.method}")
        return True


class PACReadPermission(AppActionPermission):
    """Permission pour lire un PAC"""
    app_name = 'pac'
    action = 'read_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        logger.info(
            f"[PACReadPermission._extract_processus_uuid] 🔍 Extraction processus_uuid: "
            f"obj={obj}, obj_type={type(obj).__name__ if obj else None}"
        )
        
        # Si obj est fourni et c'est un objet Pac
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grâce à select_related)
                if hasattr(obj.processus, 'uuid'):
                    processus_uuid = str(obj.processus.uuid)
                    logger.info(f"[PACReadPermission._extract_processus_uuid] ✅ Extrait depuis obj.processus.uuid: {processus_uuid}")
                    return processus_uuid
                # Si c'est une chaîne (cas improbable mais géré)
                elif isinstance(obj.processus, str):
                    logger.info(f"[PACReadPermission._extract_processus_uuid] ✅ Extrait depuis obj.processus (str): {obj.processus}")
                    return obj.processus
            else:
                logger.warning(
                    f"[PACReadPermission._extract_processus_uuid] ⚠️ obj.processus manquant: "
                    f"has_attr_processus={hasattr(obj, 'processus')}, processus={getattr(obj, 'processus', None)}"
                )
        
        # Depuis view.kwargs si uuid fourni (pour compatibilité avec les autres méthodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            pac_uuid = view.kwargs['uuid']
            logger.info(f"[PACReadPermission._extract_processus_uuid] 🔍 Tentative extraction depuis view.kwargs: pac_uuid={pac_uuid}")
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    processus_uuid = str(pac.processus.uuid)
                    logger.info(f"[PACReadPermission._extract_processus_uuid] ✅ Extrait depuis DB: {processus_uuid}")
                    return processus_uuid
            except Exception as e:
                logger.warning(f"[PACReadPermission._extract_processus_uuid] ⚠️ Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        logger.info(f"[PACReadPermission._extract_processus_uuid] 🔍 Fallback sur méthode parent")
        result = super()._extract_processus_uuid(request, view, obj)
        logger.info(f"[PACReadPermission._extract_processus_uuid] {'✅' if result else '❌'} Résultat méthode parent: {result}")
        return result


class PACAmendementCreatePermission(AppActionPermission):
    """Permission pour créer un amendement PAC"""
    app_name = 'pac'
    action = 'create_amendement_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """
        Extrait le processus_uuid depuis initial_ref ou depuis le processus fourni dans request.data
        Pour créer un amendement, on doit récupérer le PAC initial pour obtenir son processus
        """
        # 1. Depuis l'objet (si fourni)
        if obj:
            if hasattr(obj, 'processus'):
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
        
        # 2. Depuis request.data : initial_ref (cas spécifique pour create_amendement_pac)
        if hasattr(request, 'data') and request.data:
            initial_ref_uuid = request.data.get('initial_ref')
            if initial_ref_uuid:
                # Récupérer le PAC initial pour obtenir son processus
                try:
                    from pac.models import Pac
                    initial_pac = Pac.objects.select_related('processus').get(uuid=initial_ref_uuid)
                    if initial_pac.processus:
                        return str(initial_pac.processus.uuid)
                except Exception as e:
                    logger.warning(
                        f"[PACAmendementCreatePermission] Erreur lors de la récupération "
                        f"du PAC initial {initial_ref_uuid}: {str(e)}"
                    )
            
            # Fallback : processus_uuid ou processus dans request.data
            processus_uuid = request.data.get('processus') or request.data.get('processus_uuid')
            if processus_uuid:
                return str(processus_uuid)
        
        # 3. Depuis view.kwargs si fourni
        if hasattr(view, 'kwargs') and view.kwargs:
            processus_uuid = view.kwargs.get('processus_uuid') or view.kwargs.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        # 4. Depuis query params
        if hasattr(request, 'query_params'):
            processus_uuid = request.query_params.get('processus_uuid') or request.query_params.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        return super()._extract_processus_uuid(request, view, obj)


class PACDetailCreatePermission(AppActionPermission):
    """Permission pour créer un détail PAC"""
    app_name = 'pac'
    action = 'create_detail_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (pac) ou depuis obj.pac.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'pac') and obj.pac:
                if hasattr(obj.pac, 'processus') and obj.pac.processus:
                    return str(obj.pac.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            pac_uuid = request.data.get('pac')
            if pac_uuid:
                try:
                    from pac.models import Pac
                    pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                    if pac.processus:
                        return str(pac.processus.uuid)
                except Exception as e:
                    logger.warning(f"[PACDetailCreatePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from pac.models import DetailsPac
                detail = DetailsPac.objects.select_related('pac__processus').get(uuid=detail_uuid)
                if detail.pac and detail.pac.processus:
                    return str(detail.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDetailCreatePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACDetailUpdatePermission(AppActionPermission):
    """Permission pour modifier un détail PAC"""
    app_name = 'pac'
    action = 'update_detail_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.pac.processus"""
        if obj:
            if hasattr(obj, 'pac') and obj.pac:
                if hasattr(obj.pac, 'processus') and obj.pac.processus:
                    return str(obj.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from pac.models import DetailsPac
                detail = DetailsPac.objects.select_related('pac__processus').get(uuid=detail_uuid)
                if detail.pac and detail.pac.processus:
                    return str(detail.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDetailUpdatePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACDetailDeletePermission(AppActionPermission):
    """Permission pour supprimer un détail PAC"""
    app_name = 'pac'
    action = 'delete_detail_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.pac.processus"""
        if obj:
            if hasattr(obj, 'pac') and obj.pac:
                if hasattr(obj.pac, 'processus') and obj.pac.processus:
                    return str(obj.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from pac.models import DetailsPac
                detail = DetailsPac.objects.select_related('pac__processus').get(uuid=detail_uuid)
                if detail.pac and detail.pac.processus:
                    return str(detail.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDetailDeletePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACTraitementCreatePermission(AppActionPermission):
    """Permission pour créer un traitement"""
    app_name = 'pac'
    action = 'create_traitement'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (details_pac) ou depuis obj.details_pac.pac.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'details_pac') and obj.details_pac:
                if hasattr(obj.details_pac, 'pac') and obj.details_pac.pac:
                    if hasattr(obj.details_pac.pac, 'processus') and obj.details_pac.pac.processus:
                        return str(obj.details_pac.pac.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            details_pac_uuid = request.data.get('details_pac')
            if details_pac_uuid:
                try:
                    from pac.models import DetailsPac
                    detail = DetailsPac.objects.select_related('pac__processus').get(uuid=details_pac_uuid)
                    if detail.pac and detail.pac.processus:
                        return str(detail.pac.processus.uuid)
                except Exception as e:
                    logger.warning(f"[PACTraitementCreatePermission] Erreur extraction processus depuis details_pac {details_pac_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACTraitementUpdatePermission(AppActionPermission):
    """Permission pour modifier un traitement"""
    app_name = 'pac'
    action = 'update_traitement'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'details_pac') and obj.details_pac:
                if hasattr(obj.details_pac, 'pac') and obj.details_pac.pac:
                    if hasattr(obj.details_pac.pac, 'processus') and obj.details_pac.pac.processus:
                        return str(obj.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            traitement_uuid = view.kwargs['uuid']
            try:
                from pac.models import TraitementPac
                traitement = TraitementPac.objects.select_related('details_pac__pac__processus').get(uuid=traitement_uuid)
                if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                    return str(traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACTraitementUpdatePermission] Erreur extraction processus depuis traitement {traitement_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACTraitementDeletePermission(AppActionPermission):
    """Permission pour supprimer un traitement"""
    app_name = 'pac'
    action = 'delete_traitement'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'details_pac') and obj.details_pac:
                if hasattr(obj.details_pac, 'pac') and obj.details_pac.pac:
                    if hasattr(obj.details_pac.pac, 'processus') and obj.details_pac.pac.processus:
                        return str(obj.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            traitement_uuid = view.kwargs['uuid']
            try:
                from pac.models import TraitementPac
                traitement = TraitementPac.objects.select_related('details_pac__pac__processus').get(uuid=traitement_uuid)
                if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                    return str(traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACTraitementDeletePermission] Erreur extraction processus depuis traitement {traitement_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACSuiviCreatePermission(AppActionPermission):
    """Permission pour créer un suivi"""
    app_name = 'pac'
    action = 'create_suivi'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (traitement) ou depuis obj.traitement.details_pac.pac.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'traitement') and obj.traitement:
                if hasattr(obj.traitement, 'details_pac') and obj.traitement.details_pac:
                    if hasattr(obj.traitement.details_pac, 'pac') and obj.traitement.details_pac.pac:
                        if hasattr(obj.traitement.details_pac.pac, 'processus') and obj.traitement.details_pac.pac.processus:
                            return str(obj.traitement.details_pac.pac.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            traitement_uuid = request.data.get('traitement')
            if traitement_uuid:
                try:
                    from pac.models import TraitementPac
                    traitement = TraitementPac.objects.select_related('details_pac__pac__processus').get(uuid=traitement_uuid)
                    if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                        return str(traitement.details_pac.pac.processus.uuid)
                except Exception as e:
                    logger.warning(f"[PACSuiviCreatePermission] Erreur extraction processus depuis traitement {traitement_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACSuiviUpdatePermission(AppActionPermission):
    """Permission pour modifier un suivi"""
    app_name = 'pac'
    action = 'update_suivi'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.traitement.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'traitement') and obj.traitement:
                if hasattr(obj.traitement, 'details_pac') and obj.traitement.details_pac:
                    if hasattr(obj.traitement.details_pac, 'pac') and obj.traitement.details_pac.pac:
                        if hasattr(obj.traitement.details_pac.pac, 'processus') and obj.traitement.details_pac.pac.processus:
                            return str(obj.traitement.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            suivi_uuid = view.kwargs['uuid']
            try:
                from pac.models import PacSuivi
                suivi = PacSuivi.objects.select_related('traitement__details_pac__pac__processus').get(uuid=suivi_uuid)
                if suivi.traitement and suivi.traitement.details_pac and suivi.traitement.details_pac.pac and suivi.traitement.details_pac.pac.processus:
                    return str(suivi.traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACSuiviUpdatePermission] Erreur extraction processus depuis suivi {suivi_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACSuiviDeletePermission(AppActionPermission):
    """Permission pour supprimer un suivi"""
    app_name = 'pac'
    action = 'delete_suivi'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.traitement.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'traitement') and obj.traitement:
                if hasattr(obj.traitement, 'details_pac') and obj.traitement.details_pac:
                    if hasattr(obj.traitement.details_pac, 'pac') and obj.traitement.details_pac.pac:
                        if hasattr(obj.traitement.details_pac.pac, 'processus') and obj.traitement.details_pac.pac.processus:
                            return str(obj.traitement.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            suivi_uuid = view.kwargs['uuid']
            try:
                from pac.models import PacSuivi
                suivi = PacSuivi.objects.select_related('traitement__details_pac__pac__processus').get(uuid=suivi_uuid)
                if suivi.traitement and suivi.traitement.details_pac and suivi.traitement.details_pac.pac and suivi.traitement.details_pac.pac.processus:
                    return str(suivi.traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACSuiviDeletePermission] Erreur extraction processus depuis suivi {suivi_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACUnvalidatePermission(AppActionPermission):
    """Permission pour dévalider un PAC"""
    app_name = 'pac'
    action = 'unvalidate_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        # Si obj est fourni et c'est un objet Pac
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
            pac_uuid = view.kwargs['uuid']
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    return str(pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACUnvalidatePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


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

