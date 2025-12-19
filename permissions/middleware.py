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
            f"[PermissionCache] Erreur lors de l'invalidation du cache "
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
        
        # Récupérer tous les utilisateurs ayant ce rôle
        user_ids = list(UserProcessusRole.objects.filter(
            role=role,
            is_active=True
        ).values_list('user_id', flat=True).distinct())
        
        # Invalider le cache pour tous ces utilisateurs
        for user_id in user_ids:
            PermissionService.invalidate_user_cache(user_id, app_name=app_name)
        
        logger.info(
            f"[PermissionCache] Cache invalidé pour {len(user_ids)} utilisateurs "
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
