from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
import logging
from permissions.services.permission_service import PermissionService
from .base import AppActionPermission

logger = logging.getLogger(__name__)

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
