"""
Configuration du scheduler APScheduler pour les notifications automatiques.

IMPORTANT — contrainte mono-process :
  Ce scheduler tourne en thread dans le process Django (APScheduler BackgroundScheduler).
  En déploiement multi-workers (Gunicorn N workers), chaque worker démarrerait
  son propre scheduler. Un lock PID-file empêche ce double-fire.
  Si tu passes un jour à plusieurs workers, migrer vers django-q2 ou Celery Beat.
"""
import atexit
import logging
import os
import platform
import tempfile

from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django.core.management import call_command

logger = logging.getLogger(__name__)

# Variable globale pour le scheduler
scheduler = None

# Chemin du fichier PID — un seul scheduler actif à la fois
SCHEDULER_LOCK_FILE = os.path.join(tempfile.gettempdir(), 'kora_scheduler.pid')


# ─────────────────────────────────────────────
# Lock PID-file (protection multi-process)
# ─────────────────────────────────────────────

def _is_pid_alive(pid):
    """Vérifie si un PID est vivant (compatible Windows et Linux)."""
    if platform.system() == 'Windows':
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            still_active = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return bool(still_active) and exit_code.value == 259  # STILL_ACTIVE
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def acquire_scheduler_lock():
    """
    Tente d'acquérir le lock via un fichier PID.
    Retourne True si ce process peut démarrer le scheduler, False sinon.
    En cas d'erreur IO, fail-open (retourne True) pour ne pas bloquer les notifs.
    """
    current_pid = os.getpid()

    if os.path.exists(SCHEDULER_LOCK_FILE):
        try:
            with open(SCHEDULER_LOCK_FILE) as f:
                existing_pid = int(f.read().strip())

            if existing_pid != current_pid and _is_pid_alive(existing_pid):
                logger.info(
                    "Scheduler deja actif dans le process PID %s — "
                    "ce process (%s) ne demarrera pas de scheduler",
                    existing_pid, current_pid
                )
                return False

            logger.info("Ancien scheduler (PID %s) termine, reprise du lock", existing_pid)
        except (ValueError, IOError, OSError):
            pass

    try:
        with open(SCHEDULER_LOCK_FILE, 'w') as f:
            f.write(str(current_pid))
        logger.info("Scheduler lock acquis par PID %s", current_pid)
        return True
    except IOError as e:
        logger.warning("Impossible d'ecrire le fichier lock scheduler: %s — demarrage sans lock", e)
        return True  # fail-open


def release_scheduler_lock():
    """Libère le lock PID à l'arrêt du scheduler."""
    try:
        if os.path.exists(SCHEDULER_LOCK_FILE):
            with open(SCHEDULER_LOCK_FILE) as f:
                pid = int(f.read().strip())
            if pid == os.getpid():
                os.remove(SCHEDULER_LOCK_FILE)
                logger.info("Scheduler lock libere")
    except Exception as e:
        logger.warning("Impossible de liberer le lock scheduler: %s", e)


# ─────────────────────────────────────────────
# Jobs
# ─────────────────────────────────────────────

def send_reminders_job():
    """Job pour envoyer les rappels de traitements PAC."""
    try:
        logger.info("SCHEDULER — demarrage envoi rappels traitements")
        call_command('send_reminders_secure')
        logger.info("SCHEDULER — envoi rappels traitements termine")
    except Exception as e:
        logger.error("SCHEDULER — erreur rappels traitements: %s", e, exc_info=True)


def send_dashboard_reminders_job():
    """Job pour envoyer les rappels de tableaux de bord."""
    try:
        logger.info("SCHEDULER — demarrage envoi rappels dashboard")
        call_command('send_dashboard_reminders')
        logger.info("SCHEDULER — envoi rappels dashboard termine")
    except Exception as e:
        logger.error("SCHEDULER — erreur rappels dashboard: %s", e, exc_info=True)


# ─────────────────────────────────────────────
# Démarrage / arrêt
# ─────────────────────────────────────────────

def start_scheduler():
    """
    Démarre le scheduler pour les notifications automatiques.
    Refuse de démarrer si un autre process détient déjà le lock.
    """
    global scheduler

    if scheduler and scheduler.running:
        logger.warning("Scheduler deja en cours d'execution dans ce process")
        return scheduler

    if not acquire_scheduler_lock():
        logger.info("Scheduler non demarré — lock détenu par un autre process")
        return None

    try:
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")
        register_events(scheduler)
        scheduler.start()

        # Laisser DjangoJobStore charger les jobs depuis la DB
        import time
        time.sleep(0.2)

        existing_jobs = {job.id for job in scheduler.get_jobs()}
        logger.info("Jobs charges depuis la DB: %s", existing_jobs)

        for job in scheduler.get_jobs():
            logger.info("Job: %s | prochaine exec: %s | trigger: %s",
                        job.id, job.next_run_time, job.trigger)

        job_id_reminders = 'send_reminders_daily'
        job_id_dashboard = 'send_dashboard_reminders_daily'

        from django_apscheduler.models import DjangoJob

        if job_id_reminders not in existing_jobs:
            if not DjangoJob.objects.filter(id=job_id_reminders).exists():
                scheduler.add_job(
                    send_reminders_job,
                    trigger='cron', hour=8, minute=0,
                    id=job_id_reminders,
                    name='Envoi quotidien des rappels de traitements',
                    replace_existing=False,
                    max_instances=1, coalesce=True, misfire_grace_time=3600,
                )
                logger.info("Job %s cree (defaut 8h00)", job_id_reminders)
            else:
                logger.info("Job %s present en DB, DjangoJobStore doit le charger", job_id_reminders)
        else:
            logger.info("Job %s deja charge depuis la DB", job_id_reminders)

        if job_id_dashboard not in existing_jobs:
            if not DjangoJob.objects.filter(id=job_id_dashboard).exists():
                scheduler.add_job(
                    send_dashboard_reminders_job,
                    trigger='cron', hour=8, minute=30,
                    id=job_id_dashboard,
                    name='Envoi quotidien des rappels de tableaux de bord',
                    replace_existing=False,
                    max_instances=1, coalesce=True, misfire_grace_time=3600,
                )
                logger.info("Job %s cree (defaut 8h30)", job_id_dashboard)
            else:
                logger.info("Job %s present en DB, DjangoJobStore doit le charger", job_id_dashboard)
        else:
            logger.info("Job %s deja charge depuis la DB", job_id_dashboard)

        if not scheduler.running:
            raise RuntimeError("Le scheduler n'est pas actif apres le demarrage")

        logger.info("Scheduler demarre avec succes — %d job(s) actif(s)", len(scheduler.get_jobs()))
        print("=" * 70)
        print("SCHEDULER DEMARRE AVEC SUCCES")
        print("=" * 70)
        print(f"  - Scheduler actif: {scheduler.running}")
        print(f"  - Nombre de jobs: {len(scheduler.get_jobs())}")
        for job in scheduler.get_jobs():
            if job.next_run_time:
                hour_min = f"{job.next_run_time.hour:02d}:{job.next_run_time.minute:02d}"
                print(f"    * {job.id}: prochaine execution a {hour_min} ({job.next_run_time})")
            else:
                print(f"    * {job.id}: pas de prochaine execution programmee")
        print("=" * 70)

        atexit.register(_shutdown)
        return scheduler

    except Exception as e:
        release_scheduler_lock()
        logger.error("Erreur lors du demarrage du scheduler: %s", e, exc_info=True)
        raise


def _shutdown():
    """Arrêt propre du scheduler + libération du lock."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler arrete")
    release_scheduler_lock()
    scheduler = None


def stop_scheduler():
    """Arrête le scheduler proprement (appel externe)."""
    _shutdown()
