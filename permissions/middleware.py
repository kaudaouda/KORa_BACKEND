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
    quand les permissions sont modifiÃ©es (USERPROCESSUSROLE, etc.)
    
    Note: L'invalidation principale se fait via les signals Django
    Ce middleware peut Ãªtre utilisÃ© pour des invalidations supplÃ©mentaires
    """
    
    def process_response(self, request, response):
        """
        DÃ©tecte les modifications de permissions et invalide le cache
        """
        # L'invalidation principale est gÃ©rÃ©e par les signals Django
        # Ce middleware peut Ãªtre utilisÃ© pour des cas spÃ©cifiques si nÃ©cessaire
        
        return response


# ==================== SIGNALS POUR INVALIDATION AUTOMATIQUE ====================

@receiver(post_save, sender=UserProcessusRole)
@receiver(post_delete, sender=UserProcessusRole)
def invalidate_cache_on_user_processus_role_change(sender, instance, **kwargs):
    """
    Invalide le cache des permissions quand un UserProcessusRole est modifiÃ© ou supprimÃ©
    """
    try:
        user_id = instance.user.id if hasattr(instance, 'user') else None
        
        if user_id:
            # Invalider le cache pour toutes les apps pour cet utilisateur
            PermissionService.invalidate_user_cache(user_id, app_name=None)
            logger.info(
                "[PermissionCache] Cache invalid\u00e9 pour user_id=%s (UserProcessusRole modifi\u00e9/supprim\u00e9)", user_id           )
    except Exception as e:
        logger.error(
            "[PermissionCache] Erreur lors de l'invalidation du cachepour UserProcessusRole: %s", str(e)
        )


@receiver(post_save, sender=RolePermissionMapping)
@receiver(post_delete, sender=RolePermissionMapping)
def invalidate_cache_on_role_mapping_change(sender, instance, **kwargs):
    """
    Invalide le cache des permissions quand un RolePermissionMapping est modifiÃ©
    Tous les utilisateurs ayant ce rÃ´le doivent avoir leur cache invalidÃ©
    """
    try:
        if not hasattr(instance, 'role') or not instance.role:
            return
        
        role = instance.role
        app_name = instance.permission_action.app_name if hasattr(instance, 'permission_action') and instance.permission_action else None
        
        action_code = instance.permission_action.code if hasattr(instance, 'permission_action') and instance.permission_action else 'N/A'
        granted_value = instance.granted if hasattr(instance, 'granted') else 'N/A'
        
        logger.debug(
            "[PermissionCache] Signal déclenché pour RolePermissionMapping: role=%s, action=%s, granted=%s, app_name=%s",
            role.code, action_code, granted_value, app_name
        )
        
        # RÃ©cupÃ©rer tous les utilisateurs ayant ce rÃ´le avec leurs processus
        user_processus_roles = UserProcessusRole.objects.filter(
            role=role,
            is_active=True
        ).select_related('processus').values('user_id', 'processus__uuid').distinct()
        
        user_ids = list(set([upr['user_id'] for upr in user_processus_roles]))
        processus_uuids = list(set([str(upr['processus__uuid']) for upr in user_processus_roles if upr['processus__uuid']]))
        
        logger.info(
            "[PermissionCache] %s utilisateurs trouv\u00e9s avec le r\u00f4le %s, %s processus distincts", len(user_ids), role.code, len(processus_uuids)
        )
        
        # RÃ©cupÃ©rer le code de l'action
        action_code = instance.permission_action.code if hasattr(instance, 'permission_action') and instance.permission_action else None
        
        # Invalider le cache pour tous ces utilisateurs
        print(f"[PermissionCache]  Invalidation du cache pour {len(user_ids)} utilisateurs")
        for user_id in user_ids:
            if app_name and action_code and processus_uuids:
                # Invalider pour chaque processus et action spÃ©cifique
                print(f"[PermissionCache] Invalidation ciblÃ©e pour user_id={user_id}, app={app_name}, action={action_code}, processus={len(processus_uuids)} processus")
                for processus_uuid in processus_uuids:
                    PermissionService.invalidate_user_cache(
                        user_id, 
                        app_name=app_name, 
                        processus_uuid=processus_uuid, 
                        action=action_code
                    )
                    print(f"[PermissionCache] Cache invalidÃ© pour user_id={user_id}, processus={processus_uuid}, action={action_code}")
            else:
                # Invalidation gÃ©nÃ©rale si on n'a pas les dÃ©tails
                print(f"[PermissionCache]  Invalidation gÃ©nÃ©rale pour user_id={user_id}, app={app_name}")
                PermissionService.invalidate_user_cache(user_id, app_name=app_name)
        
        logger.info(
            "[PermissionCache]  Cache invalid\u00e9 pour %s utilisateurs (RolePermissionMapping modifi\u00e9 pour r\u00f4le=%s, app=%s)", len(user_ids), role.code, app_name       )
    except Exception as e:
        logger.error(
            "[PermissionCache] Erreur lors de l'invalidation du cache pour RolePermissionMapping: %s", str(e)
        )


@receiver(post_save, sender=PermissionOverride)
@receiver(post_delete, sender=PermissionOverride)
def invalidate_cache_on_override_change(sender, instance, **kwargs):
    """
    Invalide le cache des permissions quand un PermissionOverride est modifiÃ©
    """
    try:
        user_id = instance.user.id if hasattr(instance, 'user') else None
        app_name = instance.app_name if hasattr(instance, 'app_name') else None
        
        if user_id:
            PermissionService.invalidate_user_cache(user_id, app_name=app_name)
            logger.info(
                "[PermissionCache] Cache invalid\u00e9 pour user_id=%s, app_name=%s (PermissionOverride modifi\u00e9/supprim\u00e9)", user_id, app_name           )
    except Exception as e:
        logger.error(
            "[PermissionCache] Erreur lors de l'invalidation du cache pour PermissionOverride: %s", str(e)
        )
