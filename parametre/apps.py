from django.apps import AppConfig
from django.db.models.signals import post_save, post_delete
import logging
import sys
import os

logger = logging.getLogger(__name__)


# Variable globale pour éviter les boucles infinies
_reloading_jobs = set()

def reload_job_in_scheduler(sender, instance, **kwargs):
    """
    Recharge un job dans le scheduler quand il est modifié ou supprimé dans l'admin Django
    """
    global _reloading_jobs
    
    job_id = instance.id
    
    # Éviter les boucles infinies : si on est déjà en train de recharger ce job, ignorer
    if job_id in _reloading_jobs:
        return
    
    try:
        from .scheduler import scheduler, send_reminders_job, send_dashboard_reminders_job
        
        if not scheduler or not scheduler.running:
            logger.warning("Scheduler non actif, impossible de recharger le job")
            return
        
        # Mapping des IDs de jobs vers leurs fonctions
        job_functions = {
            'send_reminders_daily': send_reminders_job,
            'send_dashboard_reminders_daily': send_dashboard_reminders_job,
        }
        
        # Si c'est une suppression, supprimer le job du scheduler
        if sender == post_delete:
            try:
                scheduler.remove_job(job_id)
                logger.info(f"✅ Job {job_id} supprimé du scheduler")
                print(f"✅ Job {job_id} supprimé du scheduler")
            except Exception as e:
                logger.debug(f"Job {job_id} non trouvé dans le scheduler: {str(e)}")
            return
        
        # Pour une modification, recharger le job
        # Ne traiter que les modifications (pas les créations)
        if kwargs.get('created', False):
            # C'est une création, ne rien faire (le scheduler le gère déjà)
            return
        
        # Vérifier si c'est une mise à jour depuis le scheduler lui-même
        # (pour éviter les boucles infinies)
        import inspect
        frame = inspect.currentframe()
        try:
            # Vérifier la stack trace pour voir si l'appel provient de django_apscheduler
            caller_frames = inspect.getouterframes(frame)
            for frame_info in caller_frames[1:6]:  # Vérifier les 5 premiers frames
                if 'django_apscheduler' in frame_info.filename:
                    logger.debug(f"Ignorant le signal pour {job_id} car provient du scheduler lui-même")
                    return
        finally:
            del frame
        
        try:
            # Récupérer la fonction correspondante
            job_func = job_functions.get(job_id)
            if not job_func:
                logger.debug(f"Fonction non trouvée pour le job {job_id} (peut-être un autre type de job)")
                return
            
            # IMPORTANT: Attendre un peu pour que django-apscheduler mette à jour job_state
            # Le signal post_save se déclenche avant que django-apscheduler ne mette à jour job_state
            import time
            import threading
            
            def reload_job_delayed():
                """Recharge le job après un court délai pour laisser django-apscheduler mettre à jour job_state"""
                time.sleep(0.5)  # Attendre 500ms
                
                # Marquer qu'on est en train de recharger ce job pour éviter les boucles
                if job_id in _reloading_jobs:
                    return
                _reloading_jobs.add(job_id)
                
                try:
                    # Recharger le job depuis la base de données pour avoir les dernières valeurs
                    from django_apscheduler.models import DjangoJob
                    try:
                        django_job = DjangoJob.objects.get(id=job_id)
                    except DjangoJob.DoesNotExist:
                        logger.warning(f"Job {job_id} non trouvé dans la base de données")
                        _reloading_jobs.discard(job_id)
                        return
                    
                    try:
                        # Recharger le trigger depuis job_state (sérialisé avec pickle)
                        from apscheduler.triggers.cron import CronTrigger
                        import pickle
                        
                        trigger = None
                        
                        # Essayer de récupérer le trigger depuis job_state
                        try:
                            if django_job.job_state:
                                # job_state est sérialisé avec pickle
                                if isinstance(django_job.job_state, bytes):
                                    job_state = pickle.loads(django_job.job_state)
                                else:
                                    job_state = django_job.job_state
                                
                                logger.info(f"🔍 DEBUG: job_state type pour {job_id}: {type(job_state)}")
                                
                                # Extraire le trigger depuis job_state
                                if isinstance(job_state, dict):
                                    trigger_data = job_state.get('trigger')
                                    logger.info(f"🔍 DEBUG: trigger_data type pour {job_id}: {type(trigger_data)}")
                                    logger.info(f"🔍 DEBUG: trigger_data pour {job_id}: {trigger_data}")
                                    
                                    if trigger_data:
                                        # Si c'est déjà un CronTrigger, l'utiliser directement
                                        if isinstance(trigger_data, CronTrigger):
                                            trigger = trigger_data
                                            logger.info(f"✅ Trigger récupéré directement (CronTrigger) pour {job_id}")
                                        elif isinstance(trigger_data, dict):
                                            # Reconstruire depuis le dictionnaire
                                            trigger_kwargs = {}
                                            for key in ['year', 'month', 'day', 'week', 'day_of_week', 'hour', 'minute', 'second']:
                                                if key in trigger_data and trigger_data[key] is not None:
                                                    trigger_kwargs[key] = trigger_data[key]
                                            if trigger_kwargs:
                                                trigger = CronTrigger(**trigger_kwargs)
                                                logger.info(f"✅ Trigger reconstruit depuis job_state pour {job_id}: {trigger_kwargs}")
                                                print(f"🔍 DEBUG: Trigger reconstruit - {trigger_kwargs}")
                                        else:
                                            logger.warning(f"⚠️ trigger_data n'est ni CronTrigger ni dict pour {job_id}: {type(trigger_data)}")
                                elif hasattr(job_state, 'trigger'):
                                    # Si job_state est un objet avec un attribut trigger
                                    trigger = job_state.trigger if isinstance(job_state.trigger, CronTrigger) else None
                                    if trigger:
                                        logger.info(f"✅ Trigger récupéré depuis attribut pour {job_id}")
                                else:
                                    logger.warning(f"⚠️ job_state n'est ni dict ni objet avec trigger pour {job_id}: {type(job_state)}")
                        except Exception as e:
                            logger.error(f"❌ Erreur lors de la récupération du trigger depuis job_state pour {job_id}: {str(e)}", exc_info=True)
                            print(f"❌ Erreur lors de la récupération du trigger: {str(e)}")
                        
                        # Si on n'a pas pu récupérer le trigger depuis job_state, utiliser next_run_time comme fallback
                        if trigger is None:
                            logger.warning(f"⚠️ Trigger non récupéré depuis job_state pour {job_id}, utilisation de next_run_time comme fallback")
                            if django_job.next_run_time:
                                next_run = django_job.next_run_time
                                # Extraire l'heure et la minute depuis next_run_time
                                trigger = CronTrigger(hour=next_run.hour, minute=next_run.minute)
                                logger.info(f"⚠️ Trigger reconstruit depuis next_run_time pour {job_id}: {next_run.hour}:{next_run.minute}")
                                print(f"⚠️ ATTENTION: Utilisation de next_run_time comme fallback - {next_run.hour}:{next_run.minute}")
                            else:
                                # Valeurs par défaut si next_run_time n'est pas disponible
                                trigger = CronTrigger(hour=8, minute=0)
                                logger.warning(f"⚠️ next_run_time non disponible pour {job_id}, utilisation des valeurs par défaut: 8h00")
                                print(f"⚠️ ATTENTION: Utilisation des valeurs par défaut - 8h00")
                        
                        # Désactiver temporairement le signal pour éviter la boucle infinie
                        from django.db.models.signals import post_save
                        from django_apscheduler.models import DjangoJob
                        post_save.disconnect(reload_job_in_scheduler, sender=DjangoJob, dispatch_uid='reload_job_in_scheduler')
                        
                        try:
                            # Vérifier si le job existe déjà dans le scheduler
                            existing_job = scheduler.get_job(job_id)
                            
                            if existing_job:
                                # Si le job existe, utiliser reschedule_job pour modifier le trigger
                                scheduler.reschedule_job(job_id, trigger=trigger)
                                logger.info(f"✅ Job {job_id} rechargé dans le scheduler (trigger modifié)")
                                print(f"✅ Job {job_id} rechargé dans le scheduler (prochaine exécution: {django_job.next_run_time})")
                            else:
                                # Si le job n'existe pas, le créer
                                scheduler.add_job(
                                    job_func,
                                    trigger=trigger,
                                    id=job_id,
                                    name=job_id,  # Utiliser l'ID comme nom
                                    replace_existing=True,
                                    max_instances=1,
                                    coalesce=True,
                                    misfire_grace_time=3600
                                )
                                logger.info(f"✅ Job {job_id} créé dans le scheduler")
                                print(f"✅ Job {job_id} créé dans le scheduler (prochaine exécution: {django_job.next_run_time})")
                        finally:
                            # Réactiver le signal avec le même dispatch_uid
                            post_save.connect(reload_job_in_scheduler, sender=DjangoJob, dispatch_uid='reload_job_in_scheduler')
                    
                    finally:
                        # Retirer le job de la liste des jobs en cours de rechargement
                        _reloading_jobs.discard(job_id)
                        
                except Exception as e:
                    _reloading_jobs.discard(job_id)
                    logger.error(f"Erreur lors du rechargement du job {job_id}: {str(e)}", exc_info=True)
                    print(f"⚠️ Erreur lors du rechargement du job {job_id}: {str(e)}")
            
            # Lancer le rechargement dans un thread séparé avec un délai
            thread = threading.Thread(target=reload_job_delayed, daemon=True)
            thread.start()
            return  # Sortir immédiatement, le rechargement se fera dans le thread
                
        except Exception as e:
            _reloading_jobs.discard(job_id)
            logger.error(f"Erreur lors du rechargement du job dans le scheduler: {str(e)}", exc_info=True)
            
    except Exception as e:
        _reloading_jobs.discard(job_id)
        logger.error(f"Erreur lors du rechargement du job dans le scheduler: {str(e)}", exc_info=True)


class ParametreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parametre'
    
    def ready(self):
        # Importer l'admin personnalisé pour les jobs
        try:
            from . import admin_jobs
        except ImportError:
            pass
        """
        Démarre le scheduler APScheduler lorsque Django est prêt
        """
        # Éviter le double démarrage avec le serveur de développement Django
        # Le serveur de développement Django utilise deux processus (parent et enfant)
        # On ne démarre le scheduler que dans le processus enfant (RUN_MAIN='true')
        if os.environ.get('RUN_MAIN') != 'true':
            return
        
        # Éviter de démarrer pendant les migrations, les tests, ou les commandes de management
        if len(sys.argv) > 1:
            command = sys.argv[1]
            if command in ['migrate', 'makemigrations', 'test', 'collectstatic', 'shell', 'dbshell', 'flush', 'loaddata', 'dumpdata']:
                return
        
        # Éviter de démarrer si on est dans un contexte de test
        try:
            from django.conf import settings
            if hasattr(settings, 'TESTING') and settings.TESTING:
                return
        except Exception:
            pass
        
        # Enregistrer les signals pour recharger les jobs quand ils sont modifiés dans l'admin
        try:
            from django_apscheduler.models import DjangoJob
            # Utiliser dispatch_uid pour pouvoir désactiver/réactiver le signal de manière fiable
            post_save.connect(reload_job_in_scheduler, sender=DjangoJob, dispatch_uid='reload_job_in_scheduler')
            post_delete.connect(reload_job_in_scheduler, sender=DjangoJob, dispatch_uid='reload_job_on_delete')
            logger.info("Signals Django enregistrés pour recharger les jobs automatiquement")
        except ImportError:
            logger.warning("django_apscheduler non disponible, les signals ne seront pas enregistrés")
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement des signals: {str(e)}", exc_info=True)
        
        # Démarrer le scheduler après que Django soit complètement prêt
        # Utiliser un thread pour différer le démarrage et éviter le warning DB
        try:
            import threading
            from .scheduler import start_scheduler
            
            def start_scheduler_delayed():
                """Démarre le scheduler dans un thread séparé après un court délai"""
                import time
                time.sleep(1)  # Attendre 1 seconde que Django soit complètement prêt
                try:
                    start_scheduler()
                except Exception as e:
                    logger.error(f"Erreur lors du démarrage du scheduler: {str(e)}", exc_info=True)
                    print(f"❌ Erreur lors du démarrage du scheduler: {str(e)}")
            
            # Démarrer dans un thread pour éviter le warning
            thread = threading.Thread(target=start_scheduler_delayed, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"Erreur lors de la configuration du scheduler: {str(e)}", exc_info=True)
            print(f"❌ Erreur lors de la configuration du scheduler: {str(e)}")