"""
Configuration du scheduler APScheduler pour les notifications automatiques.

Architecture production : le scheduler tourne comme service systemd séparé
(python manage.py run_scheduler), indépendamment des workers Gunicorn.
Les workers Gunicorn communiquent avec lui via des fichiers de commandes JSON
déposés dans /tmp (préfixe kora_cmd_*.json) et lus toutes les 30 secondes
par le job _kora_command_poller.
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


def send_cdr_reminders_job():
    """Job pour envoyer les rappels de plans d'action CDR."""
    try:
        logger.info("SCHEDULER — demarrage envoi rappels CDR")
        call_command('send_cdr_reminders')
        logger.info("SCHEDULER — envoi rappels CDR termine")
    except Exception as e:
        logger.error("SCHEDULER — erreur rappels CDR: %s", e, exc_info=True)


def flush_expired_tokens_job():
    """Purge les tokens JWT expirés de la blacklist simplejwt (OutstandingToken / BlacklistedToken)."""
    try:
        logger.info("SCHEDULER — purge des tokens JWT expirés")
        call_command('flushexpiredtokens')
        logger.info("SCHEDULER — purge des tokens JWT expirés terminée")
    except Exception as e:
        logger.error("SCHEDULER — erreur purge tokens JWT: %s", e, exc_info=True)


# ─────────────────────────────────────────────
# IPC cross-process (Gunicorn ↔ scheduler service)
# ─────────────────────────────────────────────

# Préfixe des fichiers de commandes déposés par les workers Gunicorn.
_CMD_PREFIX = 'kora_cmd_'


def write_scheduler_command(action, job_id, **kwargs):
    """
    Dépose un fichier de commande JSON dans /tmp pour le scheduler service.
    Appelé depuis les workers Gunicorn (endpoints admin).

    Actions supportées : 'reschedule' (+ hour, minute), 'trigger'.
    """
    import json
    import uuid
    cmd = {'action': action, 'job_id': job_id, **kwargs}
    cmd_file = os.path.join(tempfile.gettempdir(), f'{_CMD_PREFIX}{uuid.uuid4().hex}.json')
    try:
        with open(cmd_file, 'w') as f:
            json.dump(cmd, f)
        logger.debug("Commande scheduler écrite: %s → %s", action, cmd_file)
    except Exception as e:
        logger.error("Impossible d'écrire la commande scheduler: %s", e)
        raise


def _poll_scheduler_commands():
    """
    Job interne : lit les fichiers de commandes déposés par les workers Gunicorn
    et les applique au scheduler en mémoire.
    Tourne toutes les 30 secondes dans le process scheduler service.
    """
    import glob
    import json
    from apscheduler.triggers.cron import CronTrigger

    pattern = os.path.join(tempfile.gettempdir(), f'{_CMD_PREFIX}*.json')
    for cmd_file in sorted(glob.glob(pattern)):
        cmd = None
        try:
            with open(cmd_file) as f:
                cmd = json.load(f)
            os.remove(cmd_file)
        except Exception as e:
            logger.error("Erreur lecture commande %s: %s", cmd_file, e)
            try:
                os.remove(cmd_file)
            except Exception:
                pass
            continue

        action = cmd.get('action')
        job_id = cmd.get('job_id')

        try:
            if action == 'reschedule':
                h = int(cmd['hour'])
                m = int(cmd['minute'])
                scheduler.reschedule_job(job_id, trigger=CronTrigger(hour=h, minute=m))
                logger.info("Job %s reprogrammé à %02dh%02d (commande externe)", job_id, h, m)
            elif action == 'trigger':
                job = scheduler.get_job(job_id)
                if job:
                    import threading
                    threading.Thread(target=job.func, daemon=True).start()
                    logger.info("Job %s déclenché manuellement (commande externe)", job_id)
                else:
                    logger.warning("Trigger demandé pour job inconnu: %s", job_id)
            else:
                logger.warning("Action inconnue dans commande scheduler: %s", action)
        except Exception as e:
            logger.error("Erreur exécution commande %s/%s: %s", action, job_id, e)


# ─────────────────────────────────────────────
# Démarrage / arrêt
# ─────────────────────────────────────────────

def start_scheduler(standalone=False):
    """
    Démarre le scheduler pour les notifications automatiques.

    standalone=True : mode service systemd dédié — écrit le PID sans vérifier
                      si un autre process le détient (systemd garantit l'unicité).
    standalone=False : mode legacy (désormais inutilisé) — vérifie le lock PID.
    """
    global scheduler

    if scheduler and scheduler.running:
        logger.warning("Scheduler deja en cours d'execution dans ce process")
        return scheduler

    if standalone:
        # Service dédié : écrire le PID directement, systemd empêche les doublons.
        try:
            with open(SCHEDULER_LOCK_FILE, 'w') as f:
                f.write(str(os.getpid()))
            logger.info("Scheduler standalone — PID %s enregistré", os.getpid())
        except IOError as e:
            logger.warning("Impossible d'écrire le fichier PID: %s", e)
    else:
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
        job_id_cdr       = 'send_cdr_reminders_daily'

        # Correction des triggers invalides : si un job a été chargé depuis la DB
        # avec un trigger qui ne correspond pas aux valeurs attendues (ex. créé avec
        # l'heure de démarrage par une ancienne version du code), on le replanifie
        # immédiatement avec les valeurs correctes.  reschedule_job met à jour à la
        # fois le scheduler en mémoire ET le pickle en DB via DjangoJobStore.
        from apscheduler.triggers.cron import CronTrigger as _CT
        _EXPECTED_DAILY = {
            job_id_reminders: (8,  0),
            job_id_dashboard:  (8, 30),
            job_id_cdr:        (9,  0),
        }
        for _jid, (_exp_h, _exp_m) in _EXPECTED_DAILY.items():
            if _jid not in existing_jobs:
                continue
            _live = scheduler.get_job(_jid)
            if not _live or not isinstance(_live.trigger, _CT):
                continue
            _cur_h = _cur_m = None
            for _f in _live.trigger.fields:
                if _f.name == 'hour'   and str(_f) != '*':
                    try: _cur_h = int(str(_f))
                    except ValueError: pass
                elif _f.name == 'minute' and str(_f) != '*':
                    try: _cur_m = int(str(_f))
                    except ValueError: pass
            if _cur_h != _exp_h or _cur_m != _exp_m:
                logger.warning(
                    "Trigger invalide pour %s: cron[hour=%s, minute=%s] attendu %02dh%02d — correction automatique",
                    _jid, _cur_h, _cur_m, _exp_h, _exp_m,
                )
                try:
                    scheduler.reschedule_job(_jid, trigger=_CT(hour=_exp_h, minute=_exp_m))
                    logger.info("Trigger %s corrige → %02dh%02d", _jid, _exp_h, _exp_m)
                except Exception as _e:
                    logger.error("Echec correction trigger %s: %s", _jid, _e)

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

        if job_id_cdr not in existing_jobs:
            if not DjangoJob.objects.filter(id=job_id_cdr).exists():
                scheduler.add_job(
                    send_cdr_reminders_job,
                    trigger='cron', hour=9, minute=0,
                    id=job_id_cdr,
                    name='Envoi quotidien des rappels de plans d action CDR',
                    replace_existing=False,
                    max_instances=1, coalesce=True, misfire_grace_time=3600,
                )
                logger.info("Job %s cree (defaut 9h00)", job_id_cdr)
            else:
                logger.info("Job %s present en DB, DjangoJobStore doit le charger", job_id_cdr)
        else:
            logger.info("Job %s deja charge depuis la DB", job_id_cdr)

        job_id_flush_tokens = 'flush_expired_tokens_weekly'
        if job_id_flush_tokens not in existing_jobs:
            if not DjangoJob.objects.filter(id=job_id_flush_tokens).exists():
                scheduler.add_job(
                    flush_expired_tokens_job,
                    trigger='cron', day_of_week='sun', hour=2, minute=0,
                    id=job_id_flush_tokens,
                    name='Purge hebdomadaire des tokens JWT expirés',
                    replace_existing=False,
                    max_instances=1, coalesce=True, misfire_grace_time=3600,
                )
                logger.info("Job %s cree (dimanche 2h00)", job_id_flush_tokens)
            else:
                logger.info("Job %s present en DB, DjangoJobStore doit le charger", job_id_flush_tokens)
        else:
            logger.info("Job %s deja charge depuis la DB", job_id_flush_tokens)

        # Job interne : lit les commandes déposées par les workers Gunicorn toutes les 30 s.
        # Ne pas stocker dans DjangoJobStore (jobstore par défaut) — on utilise 'memory'.
        scheduler.add_jobstore('memory', alias='memory')
        scheduler.add_job(
            _poll_scheduler_commands,
            trigger='interval', seconds=30,
            id='_kora_command_poller',
            jobstore='memory',
            replace_existing=True,
            max_instances=1, coalesce=True,
        )
        logger.info("Job poller de commandes enregistré (interval 30s)")

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
