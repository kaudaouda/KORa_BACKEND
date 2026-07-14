import logging
import os
import sys

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

        # Signaux de sécurité — chargés inconditionnellement (pas liés au scheduler)
        from . import signals  # noqa: F401

        # Ne démarrer le scheduler que dans un vrai serveur web (devserver ou Gunicorn),
        # jamais lors des commandes de management.
        is_devserver = os.environ.get('RUN_MAIN') == 'true'
        is_gunicorn  = sys.argv[0].endswith('gunicorn') if sys.argv else False
        if not is_devserver and not is_gunicorn:
            return

        skip_commands = {
            'migrate', 'makemigrations', 'test', 'collectstatic',
            'shell', 'dbshell', 'flush', 'loaddata', 'dumpdata',
        }
        if len(sys.argv) > 1 and sys.argv[1] in skip_commands:
            return

        try:
            from django.conf import settings as django_settings
            if getattr(django_settings, 'TESTING', False):
                return
        except Exception:
            pass

        # Signaux de synchronisation scheduler ↔ admin
        from . import scheduler_signals
        scheduler_signals.register()

        # Démarrage différé : attend que la DB et les tables APScheduler soient prêtes
        import threading
        from .scheduler import start_scheduler

        def _wait_for_db(max_attempts=20, delay=0.5):
            import time
            from django.db import connection
            for attempt in range(max_attempts):
                try:
                    connection.ensure_connection()
                    if 'django_apscheduler_djangojob' in connection.introspection.table_names():
                        return True
                except Exception:
                    pass
                if attempt < max_attempts - 1:
                    time.sleep(delay)
            return False

        def _start_delayed():
            if not _wait_for_db():
                logger.error("DB non disponible — scheduler non démarré")
                return
            try:
                start_scheduler()
            except Exception as e:
                logger.error("Erreur démarrage scheduler: %s", e, exc_info=True)

        threading.Thread(target=_start_delayed, daemon=True).start()
