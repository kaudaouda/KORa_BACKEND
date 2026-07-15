"""
Management command: démarre le scheduler APScheduler comme service standalone.
Utilisé exclusivement par kora-scheduler.service (systemd), jamais par Gunicorn.
"""
import logging
import os
import signal
import sys
import threading

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Démarre le scheduler APScheduler comme processus dédié (service systemd)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            f'Démarrage scheduler standalone (PID {os.getpid()})...'
        ))

        from parametre.scheduler import start_scheduler, _shutdown

        scheduler_instance = start_scheduler(standalone=True)
        if not scheduler_instance:
            self.stderr.write(self.style.ERROR('Échec du démarrage du scheduler'))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(
            'Scheduler opérationnel. En attente (SIGTERM/SIGINT pour arrêter).'
        ))

        stop_event = threading.Event()

        def _on_signal(signum, frame):
            logger.info("Signal %s reçu — arrêt propre du scheduler", signum)
            stop_event.set()

        signal.signal(signal.SIGTERM, _on_signal)
        signal.signal(signal.SIGINT, _on_signal)

        # Boucle principale : le scheduler tourne dans un thread daemon,
        # ce thread principal attend juste le signal d'arrêt.
        stop_event.wait()

        self.stdout.write('Arrêt du scheduler...')
        _shutdown()
        self.stdout.write(self.style.SUCCESS('Scheduler arrêté proprement.'))
