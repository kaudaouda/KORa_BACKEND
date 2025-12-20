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
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Extraire le processus_uuid
        processus_uuid = self._extract_processus_uuid(request, view)
        
        if not processus_uuid:
            # Si on ne peut pas extraire le processus, on refuse par sécurité
            logger.warning(
                f"[AppActionPermission] Impossible d'extraire processus_uuid pour "
                f"app={self.app_name}, action={self.action}, user={request.user.username}"
            )
            raise PermissionDenied(
                f"Impossible de déterminer le processus pour vérifier la permission '{self.action}'"
            )
        
        # Vérifier via PermissionService
        can_perform, reason = PermissionService.can_perform_action(
            user=request.user,
            app_name=self.app_name,
            processus_uuid=processus_uuid,
            action=self.action
        )
        
        if not can_perform:
            raise PermissionDenied(reason or f"Action '{self.action}' non autorisée")
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Vérifie la permission au niveau de l'objet
        Applique les conditions contextuelles si check_context=True
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Extraire le processus_uuid depuis l'objet
        processus_uuid = self._extract_processus_uuid(request, view, obj)
        
        if not processus_uuid:
            logger.warning(
                f"[AppActionPermission] Impossible d'extraire processus_uuid depuis l'objet "
                f"pour app={self.app_name}, action={self.action}"
            )
            raise PermissionDenied(
                f"Impossible de déterminer le processus pour vérifier la permission '{self.action}'"
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


class DashboardTableauValidatePermission(AppActionPermission):
    """Permission pour valider un tableau de bord"""
    app_name = 'dashboard'
    action = 'validate_tableau_bord'


class DashboardTableauReadPermission(AppActionPermission):
    """Permission pour lire un tableau de bord"""
    app_name = 'dashboard'
    action = 'read_tableau_bord'


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
        """Extrait le processus_uuid depuis l'objectif ou le tableau_bord"""
        # Même logique que DashboardObjectiveCreatePermission
        if obj:
            if hasattr(obj, 'tableau_bord') and obj.tableau_bord:
                if hasattr(obj.tableau_bord, 'processus'):
                    return str(obj.tableau_bord.processus.uuid)
        
        # Sinon utiliser la logique par défaut (via request.data ou query params)
        return super()._extract_processus_uuid(request, view, obj)


class DashboardObjectiveDeletePermission(AppActionPermission):
    """Permission pour supprimer un objectif"""
    app_name = 'dashboard'
    action = 'delete_objective'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'objectif ou le tableau_bord"""
        if obj:
            if hasattr(obj, 'tableau_bord') and obj.tableau_bord:
                if hasattr(obj.tableau_bord, 'processus'):
                    return str(obj.tableau_bord.processus.uuid)
        
        return super()._extract_processus_uuid(request, view, obj)


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
        if obj and hasattr(obj, 'objective_id') and obj.objective_id:
            if hasattr(obj.objective_id, 'tableau_bord') and obj.objective_id.tableau_bord:
                if hasattr(obj.objective_id.tableau_bord, 'processus'):
                    return str(obj.objective_id.tableau_bord.processus.uuid)
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardIndicateurDeletePermission(AppActionPermission):
    """Permission pour supprimer un indicateur"""
    app_name = 'dashboard'
    action = 'delete_indicateur'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis l'indicateur -> objective_id -> tableau_bord"""
        if obj and hasattr(obj, 'objective_id') and obj.objective_id:
            if hasattr(obj.objective_id, 'tableau_bord') and obj.objective_id.tableau_bord:
                if hasattr(obj.objective_id.tableau_bord, 'processus'):
                    return str(obj.objective_id.tableau_bord.processus.uuid)
                    if hasattr(obj.objective.tableau_bord, 'processus'):
                        return str(obj.objective.tableau_bord.processus.uuid)
        
        return super()._extract_processus_uuid(request, view, obj)


class DashboardCibleCreatePermission(AppActionPermission):
    """Permission pour créer une cible"""
    app_name = 'dashboard'
    action = 'create_cible'


class DashboardCibleUpdatePermission(AppActionPermission):
    """Permission pour modifier une cible"""
    app_name = 'dashboard'
    action = 'update_cible'


class DashboardCibleDeletePermission(AppActionPermission):
    """Permission pour supprimer une cible"""
    app_name = 'dashboard'
    action = 'delete_cible'


class DashboardPeriodiciteCreatePermission(AppActionPermission):
    """Permission pour créer une périodicité"""
    app_name = 'dashboard'
    action = 'create_periodicite'


class DashboardPeriodiciteUpdatePermission(AppActionPermission):
    """Permission pour modifier une périodicité"""
    app_name = 'dashboard'
    action = 'update_periodicite'


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


class DashboardObservationUpdatePermission(AppActionPermission):
    """Permission pour modifier une observation"""
    app_name = 'dashboard'
    action = 'update_observation'


class DashboardObservationDeletePermission(AppActionPermission):
    """Permission pour supprimer une observation"""
    app_name = 'dashboard'
    action = 'delete_observation'


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


class PACDeletePermission(AppActionPermission):
    """Permission pour supprimer un PAC"""
    app_name = 'pac'
    action = 'delete_pac'


class PACValidatePermission(AppActionPermission):
    """Permission pour valider un PAC"""
    app_name = 'pac'
    action = 'validate_pac'


class PACReadPermission(AppActionPermission):
    """Permission pour lire un PAC"""
    app_name = 'pac'
    action = 'read_pac'


class PACDetailCreatePermission(AppActionPermission):
    """Permission pour créer un détail PAC"""
    app_name = 'pac'
    action = 'create_detail_pac'


class PACDetailUpdatePermission(AppActionPermission):
    """Permission pour modifier un détail PAC"""
    app_name = 'pac'
    action = 'update_detail_pac'


class PACDetailDeletePermission(AppActionPermission):
    """Permission pour supprimer un détail PAC"""
    app_name = 'pac'
    action = 'delete_detail_pac'


class PACTraitementCreatePermission(AppActionPermission):
    """Permission pour créer un traitement"""
    app_name = 'pac'
    action = 'create_traitement'


class PACTraitementUpdatePermission(AppActionPermission):
    """Permission pour modifier un traitement"""
    app_name = 'pac'
    action = 'update_traitement'


class PACTraitementDeletePermission(AppActionPermission):
    """Permission pour supprimer un traitement"""
    app_name = 'pac'
    action = 'delete_traitement'


class PACSuiviCreatePermission(AppActionPermission):
    """Permission pour créer un suivi"""
    app_name = 'pac'
    action = 'create_suivi'


class PACSuiviUpdatePermission(AppActionPermission):
    """Permission pour modifier un suivi"""
    app_name = 'pac'
    action = 'update_suivi'


class PACSuiviDeletePermission(AppActionPermission):
    """Permission pour supprimer un suivi"""
    app_name = 'pac'
    action = 'delete_suivi'
