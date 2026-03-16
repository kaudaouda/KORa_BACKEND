"""
Middleware pour l'invalidation automatique du cache des permissions
"""
from django.utils.deprecation import MiddlewareMixin
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from permissions.services.permission_service import PermissionService
from parametre.models import UserProcessusRole
from permissions.models import RolePermissionMapping, PermissionOverride     

logger = logging.getLogger(__name__)


class PermissionCacheMiddleware(MiddlewareMixin):
    """
    Middleware pour invalider automatiquement le cache Redis
    quand les permissions sont modifiées (USERPROCESSUSROLE, etc.)
    
    Note: L'invalidation principale se fait via les signals Django
    Ce middleware peut être utilisé pour des invalidations supplémentaires
    """
    
    def process_response(self, request, response):
        """
        Détecte les modifications de permissions et invalide le cache
        """
        # L'invalidation principale est gérée par les signals Django
        # Ce middleware peut être utilisé pour des cas spécifiques si nécessaire
        
        return response


# ==================== SIGNALS POUR INVALIDATION AUTOMATIQUE ====================

@receiver(post_save, sender=UserProcessusRole)
@receiver(post_delete, sender=UserProcessusRole)
def invalidate_cache_on_user_processus_role_change(sender, instance, **kwargs):
    """
    Invalide le cache des permissions quand un UserProcessusRole est modifié ou supprimé
    """
    try:
        user_id = instance.user.id if hasattr(instance, 'user') else None
        
        if user_id:
            # Invalider le cache pour toutes les apps pour cet utilisateur
            PermissionService.invalidate_user_cache(user_id, app_name=None)
            logger.info(
                f"[PermissionCache] Cache invalidé pour user_id={user_id} "
                f"(UserProcessusRole modifié/supprimé)"
            )
    except Exception as e:
        logger.error(
            f"[PermissionCache] Erreur lors de l'invalidation du cache"
            f"pour UserProcessusRole: {str(e)}"
        )


@receiver(post_save, sender=RolePermissionMapping)
@receiver(post_delete, sender=RolePermissionMapping)
def invalidate_cache_on_role_mapping_change(sender, instance, **kwargs):
    """
    Invalide le cache des permissions quand un RolePermissionMapping est modifié
    Tous les utilisateurs ayant ce rôle doivent avoir leur cache invalidé
    """
    try:
        if not hasattr(instance, 'role') or not instance.role:
            return
        
        role = instance.role
        app_name = instance.permission_action.app_name if hasattr(instance, 'permission_action') and instance.permission_action else None
        
        action_code = instance.permission_action.code if hasattr(instance, 'permission_action') and instance.permission_action else 'N/A'
        granted_value = instance.granted if hasattr(instance, 'granted') else 'N/A'
        
        # Log détaillé avec print pour être sûr que ça s'affiche
        print(f"\n{'='*80}")
        print(f"[PermissionCache] SIGNAL DÉCLENCHÉ pour RolePermissionMapping")
        print(f"  Rôle: {role.code}")
        print(f"  Action: {action_code}")
        print(f"  Granted: {granted_value}")
        print(f"  App: {app_name}")
        print(f"{'='*80}\n")
        
        logger.info(
            f"[PermissionCache]  Signal déclenché pour RolePermissionMapping: "
            f"role={role.code}, action={action_code}, "
            f"granted={granted_value}, "
            f"app_name={app_name}"
        )
        
        # Récupérer tous les utilisateurs ayant ce rôle avec leurs processus
        user_processus_roles = UserProcessusRole.objects.filter(
            role=role,
            is_active=True
        ).select_related('processus').values('user_id', 'processus__uuid').distinct()
        
        user_ids = list(set([upr['user_id'] for upr in user_processus_roles]))
        processus_uuids = list(set([str(upr['processus__uuid']) for upr in user_processus_roles if upr['processus__uuid']]))
        
        logger.info(
            f"[PermissionCache] {len(user_ids)} utilisateurs trouvés avec le rôle {role.code}, "
            f"{len(processus_uuids)} processus distincts"
        )
        
        # Récupérer le code de l'action
        action_code = instance.permission_action.code if hasattr(instance, 'permission_action') and instance.permission_action else None
        
        # Invalider le cache pour tous ces utilisateurs
        print(f"[PermissionCache]  Invalidation du cache pour {len(user_ids)} utilisateurs")
        for user_id in user_ids:
            if app_name and action_code and processus_uuids:
                # Invalider pour chaque processus et action spécifique
                print(f"[PermissionCache] Invalidation ciblée pour user_id={user_id}, app={app_name}, action={action_code}, processus={len(processus_uuids)} processus")
                for processus_uuid in processus_uuids:
                    PermissionService.invalidate_user_cache(
                        user_id, 
                        app_name=app_name, 
                        processus_uuid=processus_uuid, 
                        action=action_code
                    )
                    print(f"[PermissionCache] Cache invalidé pour user_id={user_id}, processus={processus_uuid}, action={action_code}")
            else:
                # Invalidation générale si on n'a pas les détails
                print(f"[PermissionCache]  Invalidation générale pour user_id={user_id}, app={app_name}")
                PermissionService.invalidate_user_cache(user_id, app_name=app_name)
        
        logger.info(
            f"[PermissionCache]  Cache invalidé pour {len(user_ids)} utilisateurs "
            f"(RolePermissionMapping modifié pour rôle={role.code}, app={app_name})"
        )
    except Exception as e:
        logger.error(
            f"[PermissionCache] Erreur lors de l'invalidation du cache "
            f"pour RolePermissionMapping: {str(e)}"
        )


@receiver(post_save, sender=PermissionOverride)
@receiver(post_delete, sender=PermissionOverride)
def invalidate_cache_on_override_change(sender, instance, **kwargs):
    """
    Invalide le cache des permissions quand un PermissionOverride est modifié
    """
    try:
        user_id = instance.user.id if hasattr(instance, 'user') else None
        app_name = instance.app_name if hasattr(instance, 'app_name') else None
        
        if user_id:
            PermissionService.invalidate_user_cache(user_id, app_name=app_name)
            logger.info(
                f"[PermissionCache] Cache invalidé pour user_id={user_id}, "
                f"app_name={app_name} (PermissionOverride modifié/supprimé)"
            )
    except Exception as e:
        logger.error(
            f"[PermissionCache] Erreur lors de l'invalidation du cache "
            f"pour PermissionOverride: {str(e)}"
        )
