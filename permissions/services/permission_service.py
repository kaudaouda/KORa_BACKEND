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
        Un super admin est :
        1. Un utilisateur avec is_staff ET is_superuser (accès complet par défaut)
        2. OU un utilisateur qui a le rôle "admin" ou "validateur" 
           pour le processus "smi" ou "prs-smi"
        
        Security by Design : Les utilisateurs avec is_staff ET is_superuser 
        ont automatiquement toutes les permissions
        """
        if not user or not user.is_authenticated:
            return False
        
        # Security by Design : is_staff ET is_superuser = toutes les permissions
        if user.is_staff and user.is_superuser:
            logger.info(
                f"[PermissionService._is_super_admin] ✅ User {user.username} "
                f"est super admin (is_staff={user.is_staff}, is_superuser={user.is_superuser})"
            )
            return True
        
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
            logger.info(f"[PermissionService] ⚠️ Cache HIT pour {cache_key}")
            return cached_permissions
        
        # Cache miss : calculer les permissions depuis la DB
        logger.info(f"[PermissionService] ✅ Cache MISS, calcul depuis DB pour {cache_key}")

        # 1a. Récupérer les rôles spécifiques (non-globaux) de l'utilisateur
        specific_roles_query = UserProcessusRole.objects.filter(
            user=user,
            is_active=True,
            is_global=False
        ).select_related('role', 'processus')

        if processus_uuid:
            specific_roles_query = specific_roles_query.filter(processus__uuid=processus_uuid)

        specific_roles = list(specific_roles_query)

        # 1b. Récupérer les rôles globaux de l'utilisateur (is_global=True)
        #     Ces rôles s'appliquent à TOUS les processus (ex: superviseur_smi).
        global_roles = list(
            UserProcessusRole.objects.filter(
                user=user,
                is_active=True,
                is_global=True
            ).select_related('role')
        )

        logger.info(
            f"[PermissionService.get_user_permissions] User {user.username} ({user.id}), "
            f"app={app_name}, processus_uuid={processus_uuid}, "
            f"{len(specific_roles)} rôle(s) spécifique(s), "
            f"{len(global_roles)} rôle(s) global/globaux"
        )

        for user_role in specific_roles:
            logger.info(
                f"[PermissionService.get_user_permissions] Rôle spécifique: {user_role.role.code} "
                f"pour processus: {user_role.processus.nom} ({user_role.processus.uuid})"
            )
        for global_role in global_roles:
            logger.info(
                f"[PermissionService.get_user_permissions] Rôle global: {global_role.role.code}"
            )

        if not specific_roles and not global_roles:
            # Aucun rôle d'aucune sorte → aucune permission (refus par défaut)
            result = {}
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            logger.warning(
                f"[PermissionService.get_user_permissions] ⚠️ Aucun rôle trouvé pour "
                f"user={user.username}, processus_uuid={processus_uuid}"
            )
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

        # 4a. Grouper les rôles spécifiques par processus
        roles_by_processus = {}
        for user_role in specific_roles:
            processus_uuid_str = str(user_role.processus.uuid)
            if processus_uuid_str not in roles_by_processus:
                roles_by_processus[processus_uuid_str] = []
            roles_by_processus[processus_uuid_str].append(user_role.role)

        # 4b. Étendre avec les rôles globaux
        if global_roles:
            global_role_objects = [gr.role for gr in global_roles]

            if processus_uuid:
                # L'appelant cible un processus précis : injecter les rôles globaux dedans
                p_str = str(processus_uuid)
                if p_str not in roles_by_processus:
                    roles_by_processus[p_str] = []
                for role_obj in global_role_objects:
                    if role_obj not in roles_by_processus[p_str]:
                        roles_by_processus[p_str].append(role_obj)
            else:
                # Pas de filtre processus : injecter les rôles globaux dans tous les processus actifs
                all_processus_uuids = list(
                    Processus.objects.filter(is_active=True).values_list('uuid', flat=True)
                )
                for proc_uuid in all_processus_uuids:
                    p_str = str(proc_uuid)
                    if p_str not in roles_by_processus:
                        roles_by_processus[p_str] = []
                    for role_obj in global_role_objects:
                        if role_obj not in roles_by_processus[p_str]:
                            roles_by_processus[p_str].append(role_obj)
        
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
                    
                    logger.info(
                        f"[PermissionService] Rôle {role.code} pour action {action_code}: "
                        f"{mappings.count()} mappings trouvés"
                    )
                    
                    # Log spécifique pour update_cible
                    if action_code == 'update_cible':
                        mappings_list = [(m.id, m.granted, m.priority, m.is_active) for m in mappings]
                        logger.info(
                            f"[PermissionService] 🔍 DEBUG update_cible - Rôle {role.code}: "
                            f"{mappings.count()} mappings, "
                            f"détails: {mappings_list}"
                        )
                    
                    for mapping in mappings:
                        logger.info(
                            f"[PermissionService] Mapping trouvé: role={role.code}, "
                            f"action={action_code}, granted={mapping.granted}, "
                            f"priority={mapping.priority}, is_active={mapping.is_active}"
                        )
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
                    logger.info(
                        f"[PermissionService] ✅ Permission {action_code} ACCORDÉE "
                        f"(rôle: {granted_mapping.role.code}, priorité: {granted_mapping.priority})"
                    )
                elif denied_mapping:
                    granted = False
                    conditions = denied_mapping.conditions or {}
                    logger.info(
                        f"[PermissionService] ❌ Permission {action_code} REFUSÉE "
                        f"(rôle: {denied_mapping.role.code}, priorité: {denied_mapping.priority})"
                    )
                else:
                    logger.info(
                        f"[PermissionService] ⚠️ Permission {action_code} NON TROUVÉE "
                        f"(refus par défaut) - Aucun mapping trouvé pour les rôles: {[r.code for r in roles]}"
                    )
                
                result[processus_uuid_str][action_code] = {
                    'granted': granted,
                    'conditions': conditions,
                    'source': 'role_mapping'
                }
                
                # Log spécifique pour update_cible pour déboguer
                if action_code == 'update_cible':
                    logger.info(
                        f"[PermissionService] 🔍 DEBUG update_cible pour user={user.username}, "
                        f"processus={processus_uuid_str}: granted={granted}, "
                        f"granted_mapping={granted_mapping.role.code if granted_mapping else None} "
                        f"(priority={granted_mapping.priority if granted_mapping else None}), "
                        f"denied_mapping={denied_mapping.role.code if denied_mapping else None} "
                        f"(priority={denied_mapping.priority if denied_mapping else None})"
                    )
                    logger.info(
                        f"[PermissionService] 🔍 DEBUG update_cible - Résultat final: "
                        f"granted={granted}, conditions={conditions}, source=role_mapping"
                    )
        
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
        
        logger.warning(
            f"[PermissionService.can_perform_action] 🔍 Cache check: "
            f"user={user.username}, app={app_name}, action={action}, "
            f"processus_uuid={processus_uuid}, cache_key={cache_key}, "
            f"cached_result={cached_result}"
        )
        
        if cached_result is not None:
            granted, reason = cached_result
            logger.warning(
                f"[PermissionService.can_perform_action] ✅ Cache HIT: "
                f"granted={granted}, reason={reason}"
            )
            cls._log_audit(
                user, app_name, action, processus_uuid, granted, 
                reason, entity_instance, start_time, cache_hit=True
            )
            return granted, reason
        
        logger.warning(
            f"[PermissionService.can_perform_action] ❌ Cache MISS, "
            f"récupération des permissions depuis la DB"
        )
        
        # 3. Récupérer les permissions (utilise le cache bulk si disponible)
        permissions = cls.get_user_permissions(user, app_name, processus_uuid)
        
        logger.warning(
            f"[PermissionService.can_perform_action] 📦 Permissions récupérées: "
            f"processus_uuid={processus_uuid}, permissions_keys={list(permissions.get(str(processus_uuid), {}).keys())}"
        )
        
        processus_uuid_str = str(processus_uuid)
        if processus_uuid_str not in permissions:
            reason = f"Aucune permission trouvée pour le processus {processus_uuid_str}"
            result = (False, reason)
            logger.error(
                f"[PermissionService.can_perform_action] ❌ {reason}"
            )
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            cls._log_audit(
                user, app_name, action, processus_uuid, False, 
                reason, entity_instance, start_time
            )
            return result
        
        action_permission = permissions[processus_uuid_str].get(action)
        logger.warning(
            f"[PermissionService.can_perform_action] 🔍 Action permission: "
            f"action={action}, action_permission={action_permission}"
        )
        
        if not action_permission:
            reason = f"Action '{action}' non trouvée pour l'app '{app_name}'"
            result = (False, reason)
            logger.error(
                f"[PermissionService.can_perform_action] ❌ {reason}"
            )
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            cls._log_audit(
                user, app_name, action, processus_uuid, False, 
                reason, entity_instance, start_time
            )
            return result
        
        # 4. Vérifier la permission de base
        if not action_permission['granted']:
            # Récupérer le nom de l'action pour un message plus explicite
            try:
                permission_action = PermissionAction.objects.filter(
                    app_name=app_name,
                    code=action,
                    is_active=True
                ).first()
                action_nom = permission_action.nom if permission_action else action
            except Exception as e:
                logger.warning(f"[PermissionService] Erreur lors de la récupération du nom de l'action: {e}")
                action_nom = action
            
            # Récupérer les rôles de l'utilisateur pour ce processus
            # (inclut les rôles spécifiques ET les rôles globaux)
            try:
                specific_user_roles = UserProcessusRole.objects.filter(
                    user=user,
                    processus__uuid=processus_uuid,
                    is_active=True,
                    is_global=False
                ).select_related('role')
                global_user_roles = UserProcessusRole.objects.filter(
                    user=user,
                    is_active=True,
                    is_global=True
                ).select_related('role')
                roles_noms = (
                    [ur.role.nom for ur in specific_user_roles if ur.role]
                    + [f"{ur.role.nom} (global)" for ur in global_user_roles if ur.role]
                )
                roles_str = ", ".join(roles_noms) if roles_noms else "aucun rôle"
            except Exception as e:
                logger.warning(f"[PermissionService] Erreur lors de la récupération des rôles: {e}")
                roles_str = "rôle inconnu"
            
            reason = f"Vous n'avez pas la permission '{action_nom}' pour ce processus. Rôles actuels: {roles_str}."
            result = (False, reason)
            logger.error(
                f"[PermissionService.can_perform_action] ❌ {reason}, "
                f"action_permission={action_permission}"
            )
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
            cls._log_audit(
                user, app_name, action, processus_uuid, False, 
                reason, entity_instance, start_time
            )
            return result
        
        logger.warning(
            f"[PermissionService.can_perform_action] ✅ Permission accordée: "
            f"granted={action_permission['granted']}, source={action_permission.get('source')}"
        )
        
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
    def invalidate_user_cache(cls, user_id: int, app_name: Optional[str] = None, processus_uuid: Optional[str] = None, action: Optional[str] = None):
        """
        Invalide le cache des permissions d'un user
        
        Args:
            user_id: ID de l'utilisateur
            app_name: Nom de l'application (optionnel, si None invalide toutes les apps)
            processus_uuid: UUID du processus (optionnel, pour invalidation ciblée)
            action: Code de l'action (optionnel, pour invalidation ciblée)
        """
        # Invalider le cache bulk
        if app_name:
            # Invalider seulement pour cette app
            bulk_key = cls._get_bulk_cache_key(user_id, app_name)
            cache.delete(bulk_key)
            logger.info(f"[PermissionService] Cache bulk invalidé: {bulk_key}")
            
            # Si processus_uuid et action sont fournis, invalider aussi le cache individuel
            if processus_uuid and action:
                individual_key = cls._get_cache_key(user_id, app_name, processus_uuid, action)
                cache.delete(individual_key)
                logger.info(f"[PermissionService] Cache individuel invalidé: {individual_key}")
            elif processus_uuid:
                # Invalider tous les caches individuels pour ce processus
                # On ne peut pas faire de wildcard, mais on peut essayer de récupérer toutes les actions
                try:
                    from permissions.models import PermissionAction
                    actions = PermissionAction.objects.filter(app_name=app_name, is_active=True).values_list('code', flat=True)
                    for action_code in actions:
                        individual_key = cls._get_cache_key(user_id, app_name, processus_uuid, action_code)
                        cache.delete(individual_key)
                    logger.info(f"[PermissionService] Tous les caches individuels invalidés pour processus {processus_uuid}")
                except Exception as e:
                    logger.warning(f"[PermissionService] Erreur lors de l'invalidation des caches individuels: {e}")
        else:
            # Invalider toutes les apps connues
            logger.info(f"[PermissionService] Invalidation complète du cache pour user {user_id}")
            for app in ['cdr', 'dashboard', 'pac']:  # Applications connues
                bulk_key = cls._get_bulk_cache_key(user_id, app)
                cache.delete(bulk_key)
                logger.info(f"[PermissionService] Cache bulk invalidé: {bulk_key}")
    
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
                action=action_code,  # Correction : le champ s'appelle 'action' pas 'action_code'
                processus=processus,
                granted=granted,
                reason=reason,
                resolution_method=resolution_method,
                execution_time_ms=execution_time_ms,
                cache_hit=cache_hit
            )
        except Exception as e:
            logger.error(f"[PermissionService._log_audit] Erreur lors du log: {str(e)}")
