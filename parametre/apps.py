import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ParametreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parametre'

    def ready(self):
        try:
            from . import admin_jobs  # noqa: F401
        except ImportError:
            pass

        # Signaux de sécurité — chargés inconditionnellement
        from . import signals  # noqa: F401

        # Le scheduler NE démarre PLUS dans les workers Gunicorn.
        # Il tourne comme service systemd séparé via :
        #   python manage.py run_scheduler
        # Cela élimine les conflits multi-workers et les verrous SQLite.
