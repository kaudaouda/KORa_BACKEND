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
                    "[AppActionPermission.has_permission] ✅ Super admin bypass: user=%s, app=%s, action=%s", request.user.username, self.app_name, self.action
                )
                return True

            # Superviseur SMI : rôle global transverse — accès complet à toutes les apps
            from parametre.permissions import is_supervisor_smi
            if is_supervisor_smi(request.user):
                logger.info(
                    "[AppActionPermission.has_permission] ✅ Superviseur SMI bypass: user=%s, app=%s, action=%s", request.user.username, self.app_name, self.action
                )
                return True
            
            # Log pour déboguer
            logger.warning(
                "[AppActionPermission.has_permission] 🔍 DÉBUT Vérification permission: app=%s, action=%s, user=%s, has_view=%s, view_kwargs=%s", self.app_name, self.action, request.user.username, view is not None, view.kwargs if view and hasattr(view, 'kwargs') else 'N/A'
            )
            
            # Extraire le processus_uuid
            processus_uuid = self._extract_processus_uuid(request, view)
            
            logger.warning(
                "[AppActionPermission.has_permission] 🔍 Vérification permission: app=%s, action=%s, user=%s, processus_uuid=%s", self.app_name, self.action, request.user.username, processus_uuid
            )
            
            if not processus_uuid:
                # Si on ne peut pas extraire le processus, on refuse par sécurité
                logger.error(
                    "[AppActionPermission] ❌ ERREUR: Impossible d'extraire processus_uuid pour app=%s, action=%s, user=%s, has_view=%s, view_kwargs=%s", self.app_name, self.action, request.user.username, view is not None, view.kwargs if view and hasattr(view, 'kwargs') else 'N/A'
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
                    "[AppActionPermission.has_permission] ✅ Résultat vérification: can_perform=%s, reason=%s, app=%s, action=%s, user=%s, processus_uuid=%s", can_perform, reason, self.app_name, self.action, request.user.username, processus_uuid
                )
                
                if not can_perform:
                    logger.error(
                        "[AppActionPermission.has_permission] ❌ PERMISSION REFUSÉE: app=%s, action=%s, user=%s, processus_uuid=%s, reason=%s", self.app_name, self.action, request.user.username, processus_uuid, reason
                    )
                    raise PermissionDenied(reason or f"Action '{self.action}' non autorisée")
            except PermissionDenied:
                raise
            except Exception as e:
                logger.error(
                    "[AppActionPermission.has_permission] ❌ EXCEPTION dans PermissionService.can_perform_action: %s", e,
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
                "[AppActionPermission.has_permission] Erreur lors de la vérification de permission: %s", e,
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
            "[AppActionPermission.has_object_permission] 🔍 Début vérification: app=%s, action=%s, user=%s, obj=%s, obj_type=%s", self.app_name, self.action, request.user.username if request.user else None, obj, type(obj).__name__ if obj else None
        )
        
        if not request.user or not request.user.is_authenticated:
            logger.warning("[AppActionPermission.has_object_permission] ❌ User non authentifié")
            return False
        
        # Security by Design : Vérifier le super admin AVANT d'extraire le processus_uuid
        if PermissionService._is_super_admin(request.user):
            logger.info(
                "[AppActionPermission.has_object_permission] ✅ Super admin bypass: user=%s, app=%s, action=%s", request.user.username, self.app_name, self.action
            )
            return True

        # Superviseur SMI : rôle global transverse — accès complet
        from parametre.permissions import is_supervisor_smi
        if is_supervisor_smi(request.user):
            logger.info(
                "[AppActionPermission.has_object_permission] ✅ Superviseur SMI bypass: user=%s, app=%s, action=%s", request.user.username, self.app_name, self.action
            )
            return True

        # Extraire le processus_uuid depuis l'objet
        processus_uuid = self._extract_processus_uuid(request, view, obj)
        
        if not processus_uuid:
            logger.warning(
                "[AppActionPermission.has_object_permission] ❌ Impossible d'extraire processus_uuid depuis l'objet pour app=%s, action=%s, user=%s", self.app_name, self.action, request.user.username
            )
            raise PermissionDenied(
                f"Impossible de déterminer le processus pour vérifier la permission '{self.action}'"
            )
        
        logger.info(
            "[AppActionPermission.has_object_permission] 🔍 processus_uuid extrait: %s, check_context=%s", processus_uuid, self.check_context
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
            "[AppActionPermission.has_object_permission] %s Résultat PermissionService: can_perform=%s, reason=%s, app=%s, action=%s, user=%s, processus_uuid=%s", '✅' if can_perform else '❌', can_perform, reason, self.app_name, self.action, request.user.username, processus_uuid
        )
        
        if not can_perform:
            raise PermissionDenied(reason or f"Action '{self.action}' non autorisée sur cet objet")
        
        return True


# ==================== CLASSES SPÉCIALISÉES PAR APP ====================

# ==================== CDR (Cartographie des Risques) ====================
