"""
Service générique pour la gestion des permissions
Supporte plusieurs applications : CDR, Dashboard, PAC, etc.
"""
from django.core.cache import cache
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.contrib.auth.models import User
import hashlib
import json
import logging
from typing import Dict, Tuple, Optional, Any
from datetime import datetime

from permissions.models import (
    PermissionAction,
    RolePermissionMapping,
    AppPermission,
    PermissionOverride,
    PermissionAudit
)
from parametre.models import Role, Processus, UserProcessusRole

logger = logging.getLogger(__name__)


class PermissionService:
    """
    Service ultra-performant pour la gestion des permissions génériques
    Utilise Redis pour le cache et optimise les requêtes DB
    
    Méthodes génériques utilisables par toutes les apps :
    - can_perform_action() : Vérifie si un user peut effectuer une action
    - get_user_permissions() : Récupère toutes les permissions d'un user
    - invalidate_user_cache() : Invalide le cache des permissions
    """
    
    CACHE_TIMEOUT = 5  # 5 secondes - TTL ultra-court pour synchronisation IMMEDIATE
    CACHE_PREFIX = 'perm'
    
    @classmethod
    def _get_cache_key(cls, user_id, app_name, processus_uuid, action_code):
        """Génère une clé de cache unique"""
        key_data = f"{user_id}:{app_name}:{processus_uuid}:{action_code}"
        return f"{cls.CACHE_PREFIX}:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    @classmethod
    def _get_bulk_cache_key(cls, user_id, app_name, processus_uuid=None):
        """Clé pour le cache bulk des permissions d'un user pour une app"""
        if processus_uuid:
            return f"{cls.CACHE_PREFIX}:{app_name}:bulk:{user_id}:{processus_uuid}"
        return f"{cls.CACHE_PREFIX}:{app_name}:bulk:{user_id}"
    
    @classmethod
    def _is_super_admin(cls, user: User) -> bool:
        """
        Vérifie si user est super admin
        Un super admin est un utilisateur qui a le rôle "admin" ou "validateur" 
        pour le processus "smi" ou "prs-smi"
        """
        if not user or not user.is_authenticated:
            return False
        
        try:
            # Chercher les processus SMI (seulement par nom car Processus n'a pas de champ code)
            smi_processus = Processus.objects.filter(
                Q(nom__iexact='smi') | Q(nom__iexact='prs-smi')
            ).first()
            
            if not smi_processus:
                return False
            
            # Vérifier si l'utilisateur a le rôle admin ou validateur pour SMI
            admin_role = Role.objects.filter(code='admin').first()
            validateur_role = Role.objects.filter(code='validateur').first()
            
            if admin_role:
                has_admin = UserProcessusRole.objects.filter(
                    user=user,
                    processus=smi_processus,
                    role=admin_role,
                    is_active=True
                ).exists()
                if has_admin:
                    return True
            
            if validateur_role:
                has_validateur = UserProcessusRole.objects.filter(
                    user=user,
                    processus=smi_processus,
                    role=validateur_role,
                    is_active=True
                ).exists()
                if has_validateur:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"[PermissionService._is_super_admin] Erreur: {str(e)}")
            return False
    
    @classmethod
    def get_user_permissions(
        cls, 
        user: User, 
        app_name: str, 
        processus_uuid: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Récupère TOUTES les permissions d'un user pour une application
        Retourne un dict: {processus_uuid: {action_code: {granted: bool, conditions: dict}}}
        
        Security by Design :
        - Vérifie que l'utilisateur a au moins un rôle actif pour le processus
        - Refus par défaut si aucun rôle trouvé
        - Super admin bypass uniquement pour les super admins vérifiés
        
        Args:
            user: User Django
            app_name: Nom de l'application ('cdr', 'dashboard', 'pac', etc.)
            processus_uuid: UUID du processus (optionnel, filtre les résultats)
        
        Returns:
            dict: Permissions structurées par processus et action
        """
        if not user or not user.is_authenticated:
            return {}
        
        # Super admin : toutes les permissions accordées
        if cls._is_super_admin(user):
            # Récupérer toutes les actions pour cette app
            actions = PermissionAction.objects.filter(
                app_name=app_name,
                is_active=True
            ).values_list('code', flat=True)
            
            # Si processus_uuid spécifié, retourner seulement pour ce processus
            if processus_uuid:
                return {
                    str(processus_uuid): {
                        action: {
                            'granted': True,
                            'conditions': {},
                            'source': 'super_admin'
                        }
                        for action in actions
                    }
                }
            else:
                # Retourner pour tous les processus (structure vide pour indiquer "tous")
                return {
                    '*': {
                        action: {
                            'granted': True,
                            'conditions': {},
                            'source': 'super_admin'
                        }
                        for action in actions
                    }
                }
        
        # Vérifier le cache
        cache_key = cls._get_bulk_cache_key(user.id, app_name, processus_uuid)
        cached_permissions = cache.get(cache_key)
        if cached_permissions is not None:
            logger.debug(f"[PermissionService] Cache hit pour {cache_key}")
            return cached_permissions
        
        # Cache miss : calculer les permissions depuis la DB
        logger.debug(f"[PermissionService] Cache miss, calcul depuis DB pour {cache_key}")
        
        # 1. Récupérer les UserProcessusRole de l'utilisateur
        user_roles_query = UserProcessusRole.objects.filter(
            user=user,
            is_active=True
        ).select_related('role', 'processus')
        
        if processus_uuid:
            user_roles_query = user_roles_query.filter(processus__uuid=processus_uuid)
        
        user_roles = list(user_roles_query)
        
        if not user_roles:
            # Aucun rôle, aucune permission
            result = {}
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            return result
        
        # 2. Récupérer les PermissionAction pour cette app
        actions = PermissionAction.objects.filter(
            app_name=app_name,
            is_active=True
        ).prefetch_related('role_mappings')
        
        # 3. Récupérer les PermissionOverride pour cet utilisateur
        override_query = PermissionOverride.objects.filter(
            user=user,
            app_name=app_name,
            is_active=True
        ).select_related('permission_action', 'processus')
        
        if processus_uuid:
            override_query = override_query.filter(processus__uuid=processus_uuid)
        
        overrides = {
            (str(ov.processus.uuid), ov.permission_action.code): ov
            for ov in override_query
        }
        
        # 4. Construire le résultat
        result = {}
        
        # Grouper les rôles par processus
        roles_by_processus = {}
        for user_role in user_roles:
            processus_uuid_str = str(user_role.processus.uuid)
            if processus_uuid_str not in roles_by_processus:
                roles_by_processus[processus_uuid_str] = []
            roles_by_processus[processus_uuid_str].append(user_role.role)
        
        # Pour chaque processus, calculer les permissions
        for processus_uuid_str, roles in roles_by_processus.items():
            result[processus_uuid_str] = {}
            
            for action in actions:
                action_code = action.code
                override_key = (processus_uuid_str, action_code)
                
                # Vérifier si un override existe
                if override_key in overrides:
                    override = overrides[override_key]
                    # Vérifier la validité temporelle
                    now = timezone.now()
                    if override.date_debut and override.date_debut > now:
                        continue
                    if override.date_fin and override.date_fin < now:
                        continue
                    
                    result[processus_uuid_str][action_code] = {
                        'granted': override.granted,
                        'conditions': override.conditions or {},
                        'source': 'override'
                    }
                    continue
                
                # Sinon, calculer depuis les rôles
                # Logique : Si au moins un rôle accorde la permission, elle est accordée
                # En cas de conflit, on prend le mapping avec la plus haute priorité parmi ceux qui accordent
                # Si aucun rôle n'accorde, on prend le mapping avec la plus haute priorité (même s'il refuse)
                granted = False
                conditions = {}
                max_priority_granted = -1
                max_priority_denied = -1
                granted_mapping = None
                denied_mapping = None
                
                for role in roles:
                    # Récupérer les mappings pour ce rôle et cette action
                    mappings = RolePermissionMapping.objects.filter(
                        role=role,
                        permission_action=action,
                        is_active=True
                    ).order_by('-priority')
                    
                    for mapping in mappings:
                        if mapping.granted:
                            # Permission accordée : prendre celle avec la plus haute priorité
                            if mapping.priority > max_priority_granted:
                                max_priority_granted = mapping.priority
                                granted_mapping = mapping
                        else:
                            # Permission refusée : garder trace de la plus haute priorité
                            if mapping.priority > max_priority_denied:
                                max_priority_denied = mapping.priority
                                denied_mapping = mapping
                
                # Si au moins un rôle accorde la permission, elle est accordée
                # Sinon, on prend le mapping avec la plus haute priorité (même s'il refuse)
                if granted_mapping:
                    granted = True
                    conditions = granted_mapping.conditions or {}
                elif denied_mapping:
                    granted = False
                    conditions = denied_mapping.conditions or {}
                # Si aucun mapping trouvé, granted reste False (refus par défaut)
                
                result[processus_uuid_str][action_code] = {
                    'granted': granted,
                    'conditions': conditions,
                    'source': 'role_mapping'
                }
        
        # Mettre en cache
        cache.set(cache_key, result, cls.CACHE_TIMEOUT)
        
        return result
    
    @classmethod
    def can_perform_action(
        cls,
        user: User,
        app_name: str,
        processus_uuid: str,
        action: str,
        entity_instance: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Vérifie si un user peut effectuer une action spécifique
        
        Args:
            user: User Django
            app_name: Nom de l'application ('cdr', 'dashboard', etc.)
            processus_uuid: UUID du processus
            action: Code de l'action ('create_cdr', 'update_tableau', etc.)
            entity_instance: Instance de l'entité (pour vérifications contextuelles)
        
        Returns:
            tuple: (can_perform: bool, reason: str)
        """
        start_time = timezone.now()
        
        if not user or not user.is_authenticated:
            cls._log_audit(user, app_name, action, processus_uuid, False, "User non authentifié")
            return False, "User non authentifié"
        
        # 1. Super admin bypass
        if cls._is_super_admin(user):
            cls._log_audit(
                user, app_name, action, processus_uuid, True, 
                "Super admin", entity_instance, start_time
            )
            return True, "Super admin"
        
        # 2. Vérifier le cache pour cette action spécifique
        cache_key = cls._get_cache_key(user.id, app_name, processus_uuid, action)
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            granted, reason = cached_result
            cls._log_audit(
                user, app_name, action, processus_uuid, granted, 
                reason, entity_instance, start_time, cache_hit=True
            )
            return granted, reason
        
        # 3. Récupérer les permissions (utilise le cache bulk si disponible)
        permissions = cls.get_user_permissions(user, app_name, processus_uuid)
        
        processus_uuid_str = str(processus_uuid)
        if processus_uuid_str not in permissions:
            reason = f"Aucune permission trouvée pour le processus {processus_uuid_str}"
            result = (False, reason)
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            cls._log_audit(
                user, app_name, action, processus_uuid, False, 
                reason, entity_instance, start_time
            )
            return result
        
        action_permission = permissions[processus_uuid_str].get(action)
        if not action_permission:
            reason = f"Action '{action}' non trouvée pour l'app '{app_name}'"
            result = (False, reason)
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            cls._log_audit(
                user, app_name, action, processus_uuid, False, 
                reason, entity_instance, start_time
            )
            return result
        
        # 4. Vérifier la permission de base
        if not action_permission['granted']:
            reason = f"Permission refusée par le rôle"
            result = (False, reason)
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            cls._log_audit(
                user, app_name, action, processus_uuid, False, 
                reason, entity_instance, start_time
            )
            return result
        
        # 5. Appliquer les conditions contextuelles
        conditions = action_permission.get('conditions', {})
        if conditions:
            # Vérifier can_edit_when_validated
            if conditions.get('can_edit_when_validated') and entity_instance:
                if hasattr(entity_instance, 'is_validated'):
                    if entity_instance.is_validated:
                        reason = "Modification autorisée même si validé (condition can_edit_when_validated)"
                        result = (True, reason)
                        cache.set(cache_key, result, cls.CACHE_TIMEOUT)
                        cls._log_audit(
                            user, app_name, action, processus_uuid, True, 
                            reason, entity_instance, start_time
                        )
                        return result
            
            # Vérifier can_edit_only_own
            if conditions.get('can_edit_only_own') and entity_instance:
                if hasattr(entity_instance, 'cree_par'):
                    if entity_instance.cree_par != user:
                        reason = "Vous ne pouvez modifier que vos propres éléments"
                        result = (False, reason)
                        cache.set(cache_key, result, cls.CACHE_TIMEOUT)
                        cls._log_audit(
                            user, app_name, action, processus_uuid, False, 
                            reason, entity_instance, start_time
                        )
                        return result
        
        # 6. Permission accordée
        reason = f"Permission accordée ({action_permission.get('source', 'unknown')})"
        result = (True, reason)
        cache.set(cache_key, result, cls.CACHE_TIMEOUT)
        cls._log_audit(
            user, app_name, action, processus_uuid, True, 
            reason, entity_instance, start_time
        )
        return result
    
    @classmethod
    def invalidate_user_cache(cls, user_id: int, app_name: Optional[str] = None):
        """
        Invalide le cache des permissions d'un user
        
        Args:
            user_id: ID de l'utilisateur
            app_name: Nom de l'application (optionnel, si None invalide toutes les apps)
        """
        if app_name:
            # Invalider seulement pour cette app
            bulk_key = cls._get_bulk_cache_key(user_id, app_name)
            cache.delete(bulk_key)
            logger.info(f"[PermissionService] Cache invalidé: {bulk_key}")
        else:
            # Invalider toutes les apps connues
            logger.info(f"[PermissionService] Invalidation complète du cache pour user {user_id}")
            for app in ['cdr', 'dashboard', 'pac']:  # Applications connues
                bulk_key = cls._get_bulk_cache_key(user_id, app)
                cache.delete(bulk_key)
                logger.info(f"[PermissionService] Cache invalidé: {bulk_key}")
    
    @classmethod
    def _log_audit(
        cls,
        user: User,
        app_name: str,
        action_code: str,
        processus_uuid: Optional[str],
        granted: bool,
        reason: str,
        entity_instance: Optional[Any] = None,
        start_time: Optional[datetime] = None,
        cache_hit: bool = False
    ):
        """
        Log une vérification de permission dans PermissionAudit
        """
        try:
            execution_time_ms = None
            if start_time:
                execution_time_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            processus = None
            if processus_uuid:
                try:
                    processus = Processus.objects.get(uuid=processus_uuid)
                except Processus.DoesNotExist:
                    pass
            
            # Déterminer la méthode de résolution
            resolution_method = 'cache' if cache_hit else 'db'
            if cls._is_super_admin(user):
                resolution_method = 'super_admin'
            
            # Récupérer l'IP et user agent (si disponible dans le contexte)
            # Note: Pour l'instant, on ne les récupère pas car on n'a pas accès à la request
            # On pourrait passer la request en paramètre si nécessaire
            
            PermissionAudit.objects.create(
                user=user,
                app_name=app_name,
                action_code=action_code,
                processus=processus,
                granted=granted,
                reason=reason,
                resolution_method=resolution_method,
                execution_time_ms=execution_time_ms,
                cache_hit=cache_hit
            )
        except Exception as e:
            logger.error(f"[PermissionService._log_audit] Erreur lors du log: {str(e)}")
