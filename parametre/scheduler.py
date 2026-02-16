"""
Configuration du scheduler APScheduler pour les notifications automatiques
"""
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django.core.management import call_command
import logging
import atexit

logger = logging.getLogger(__name__)

# Variable globale pour le scheduler
scheduler = None


def send_reminders_job():
    """Job pour envoyer les rappels de traitements"""
    try:
        print("=" * 70)
        print("🔄 DÉMARRAGE AUTOMATIQUE - Envoi des rappels de traitements")
        print("=" * 70)
        logger.info("Démarrage de l'envoi des rappels de traitements...")
        call_command('send_reminders_secure')
        logger.info("Envoi des rappels de traitements terminé")
        print("✅ Envoi des rappels de traitements terminé avec succès")
        print("=" * 70)
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi des rappels de traitements: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print("=" * 70)
        print(f"❌ ERREUR: {error_msg}")
        print("=" * 70)
        import traceback
        traceback.print_exc()


def send_dashboard_reminders_job():
    """Job pour envoyer les rappels de tableaux de bord"""
    try:
        print("=" * 70)
        print("🔄 DÉMARRAGE AUTOMATIQUE - Envoi des rappels de tableaux de bord")
        print("=" * 70)
        logger.info("Démarrage de l'envoi des rappels de tableaux de bord...")
        call_command('send_dashboard_reminders')
        logger.info("Envoi des rappels de tableaux de bord terminé")
        print("✅ Envoi des rappels de tableaux de bord terminé avec succès")
        print("=" * 70)
    except Exception as e:
        error_msg = f"Erreur lors de l'envoi des rappels de tableaux de bord: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print("=" * 70)
        print(f"❌ ERREUR: {error_msg}")
        print("=" * 70)
        import traceback
        traceback.print_exc()


def start_scheduler():
    """
    Démarre le scheduler pour les notifications automatiques
    """
    global scheduler
    
    # Éviter de démarrer plusieurs fois
    if scheduler and scheduler.running:
        logger.warning("Le scheduler est déjà en cours d'exécution")
        return scheduler
    
    try:
        # Créer le scheduler
        scheduler = BackgroundScheduler()
        
        # Utiliser DjangoJobStore pour persister les jobs dans la base de données
        scheduler.add_jobstore(DjangoJobStore(), "default")
        
        # Enregistrer les événements pour le logging
        register_events(scheduler)
        
        # Démarrer le scheduler AVANT d'ajouter les jobs
        # Cela permet au DjangoJobStore de charger les jobs existants depuis la base de données
        scheduler.start()
        
        # Attendre un peu pour que DjangoJobStore charge les jobs depuis la DB
        import time
        time.sleep(0.2)  # Attendre 200ms pour que DjangoJobStore charge les jobs
        
        # IMPORTANT: Ne PAS recréer les jobs s'ils existent déjà dans le scheduler
        # DjangoJobStore charge automatiquement les jobs depuis la base de données au démarrage
        # Si on appelle add_job() avec replace_existing=True, cela écrase les valeurs de la DB
        
        # Vérifier si les jobs existent déjà dans le scheduler (chargés depuis la DB)
        job_id_reminders = 'send_reminders_daily'
        job_id_dashboard = 'send_dashboard_reminders_daily'
        
        existing_jobs = {job.id for job in scheduler.get_jobs()}
        logger.info(f"🔍 Jobs existants dans le scheduler après démarrage: {existing_jobs}")
        
        # Afficher les détails des jobs chargés
        for job in scheduler.get_jobs():
            logger.info(f"🔍 Job chargé: {job.id}, next_run: {job.next_run_time}, trigger: {job.trigger}")
            print(f"🔍 Job chargé depuis DB: {job.id}, prochaine exécution: {job.next_run_time}")
        
        # Job pour les rappels de traitements
        if job_id_reminders not in existing_jobs:
            # Le job n'existe pas dans le scheduler, vérifier s'il existe dans la DB
            from django_apscheduler.models import DjangoJob
            if not DjangoJob.objects.filter(id=job_id_reminders).exists():
                # Le job n'existe nulle part, le créer avec des valeurs par défaut
                scheduler.add_job(
                    send_reminders_job,
                    trigger='cron',
                    hour=8,
                    minute=0,
                    id=job_id_reminders,
                    name='Envoi quotidien des rappels de traitements',
                    replace_existing=False,  # Ne pas remplacer si existe déjà
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=3600
                )
                logger.info(f"✅ Job {job_id_reminders} créé avec les valeurs par défaut (8h00)")
            else:
                logger.info(f"ℹ️ Job {job_id_reminders} existe dans la DB mais pas dans le scheduler - DjangoJobStore devrait le charger")
        else:
            logger.info(f"ℹ️ Job {job_id_reminders} existe déjà dans le scheduler (chargé depuis la DB)")
        
        # Job pour les rappels de tableaux de bord
        if job_id_dashboard not in existing_jobs:
            # Le job n'existe pas dans le scheduler, vérifier s'il existe dans la DB
            from django_apscheduler.models import DjangoJob
            if not DjangoJob.objects.filter(id=job_id_dashboard).exists():
                # Le job n'existe nulle part, le créer avec des valeurs par défaut
                scheduler.add_job(
                    send_dashboard_reminders_job,
                    trigger='cron',
                    hour=8,
                    minute=30,
                    id=job_id_dashboard,
                    name='Envoi quotidien des rappels de tableaux de bord',
                    replace_existing=False,  # Ne pas remplacer si existe déjà
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=3600
                )
                logger.info(f"✅ Job {job_id_dashboard} créé avec les valeurs par défaut (8h30)")
            else:
                logger.info(f"ℹ️ Job {job_id_dashboard} existe dans la DB mais pas dans le scheduler - DjangoJobStore devrait le charger")
        else:
            logger.info(f"ℹ️ Job {job_id_dashboard} existe déjà dans le scheduler (chargé depuis la DB)")
        
        # Vérifier que le scheduler est bien actif
        if scheduler.running:
            logger.info("✅ Scheduler démarré avec succès")
            # Afficher aussi dans la console pour être sûr que c'est visible
            print("=" * 70)
            print("✅ SCHEDULER DÉMARRÉ AVEC SUCCÈS")
            print("=" * 70)
            print(f"  - Scheduler actif: {scheduler.running}")
            print(f"  - Nombre de jobs: {len(scheduler.get_jobs())}")
            for job in scheduler.get_jobs():
                if job.next_run_time:
                    # Extraire l'heure et la minute pour affichage
                    next_run = job.next_run_time
                    hour_min = f"{next_run.hour:02d}:{next_run.minute:02d}"
                    print(f"    • {job.id}: prochaine exécution à {hour_min} ({job.next_run_time})")
                    logger.info(f"  - {job.id}: prochaine exécution à {hour_min}")
                else:
                    print(f"    • {job.id}: pas de prochaine exécution programmée")
                    logger.info(f"  - {job.id}: pas de prochaine exécution programmée")
            print("=" * 70)
        else:
            error_msg = "❌ Le scheduler n'est pas actif après le démarrage"
            logger.error(error_msg)
            print(error_msg)
            raise RuntimeError(error_msg)
        
        # Arrêter le scheduler proprement à la sortie
        atexit.register(lambda: scheduler.shutdown())
        
        return scheduler
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du démarrage du scheduler: {str(e)}", exc_info=True)
        raise


def stop_scheduler():
    """
    Arrête le scheduler proprement
    """
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler arrêté")
        scheduler = None
