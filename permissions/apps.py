from django.apps import AppConfig


class PermissionsConfig(AppConfig):
    """
    Configuration de l'application générique de gestion des permissions
    Supporte plusieurs applications : CDR, Dashboard, PAC, etc.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'permissions'
    verbose_name = 'Gestion des Permissions'
    
    def ready(self):
        """
        Enregistre les signals Django pour l'invalidation automatique du cache
        """
        import permissions.middleware  # noqa: F401
