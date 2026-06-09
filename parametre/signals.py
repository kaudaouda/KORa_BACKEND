"""
Signaux Django pour la sécurité applicative.
"""
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

import logging

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User)
def invalidate_jwt_user_cache(sender, instance, **kwargs):
    """
    Invalide le cache JWT de l'utilisateur à chaque sauvegarde.

    Principe Complete Mediation : toute modification de compte (désactivation,
    changement de mot de passe, blocage) doit prendre effet immédiatement.
    Sans cette invalidation, JWTCookieMiddleware peut authentifier un compte
    désactivé pendant jusqu'à 5 minutes (TTL du cache).

    La clé doit correspondre à celle de JWTCookieMiddleware._USER_CACHE_TTL.
    """
    cache_key = f'jwt_user:{instance.pk}'
    cache.delete(cache_key)
    logger.debug("Cache JWT invalidé pour user id=%s", instance.pk)
