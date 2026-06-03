"""
Signaux Django pour synchroniser le scheduler APScheduler avec l'admin.

Seule la suppression d'un DjangoJob nécessite une action en temps réel :
le job doit être retiré de la mémoire du scheduler.
Les modifications de planning passent par l'endpoint API dédié
(parametre/views.py → admin_scheduler_job_update) qui utilise reschedule_job().
"""
import logging

logger = logging.getLogger(__name__)

DISPATCH_UID_DELETE = 'kora_scheduler_job_deleted'


def handle_job_deleted(sender, instance, **kwargs):
    """Retire le job du scheduler en mémoire quand il est supprimé de la DB."""
    from .scheduler import scheduler
    if not scheduler or not scheduler.running:
        return
    try:
        scheduler.remove_job(instance.id)
        logger.info("Job %s retiré du scheduler", instance.id)
    except Exception:
        logger.debug("Job %s déjà absent du scheduler", instance.id)


def register():
    """Connecte le signal post_delete sur DjangoJob."""
    try:
        from django_apscheduler.models import DjangoJob
        from django.db.models.signals import post_delete

        post_delete.connect(handle_job_deleted, sender=DjangoJob, dispatch_uid=DISPATCH_UID_DELETE)
        logger.info("Signal de suppression scheduler enregistré")
    except ImportError:
        logger.warning("django_apscheduler non disponible — signal scheduler non enregistré")
    except Exception as e:
        logger.error("Erreur enregistrement signal scheduler: %s", e, exc_info=True)
