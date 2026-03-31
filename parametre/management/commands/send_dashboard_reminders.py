from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.conf import settings

from parametre.models import ReminderEmailLog, EmailSettings
from parametre.services.dashboard_notification_service import (
    get_dashboard_notifications,
    is_already_sent_today,
    build_subject,
    render_email_bodies,
)

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send reminder emails for dashboard indicators based on frequency periods"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be sent without actually sending emails')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        email_settings = EmailSettings.get_solo()
        if not email_settings.email_host_user or not email_settings.get_password():
            self.stderr.write(self.style.ERROR(
                "Configuration email incomplete. Veuillez configurer EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans l'admin."
            ))
            return

        self._apply_email_config(email_settings)

        total_sent = 0
        total_skipped = 0
        recipients = set()

        for user, indicateur, periode_name, periode_date, notif_type, message, context_hash in get_dashboard_notifications():

            if is_already_sent_today(context_hash):
                total_skipped += 1
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f"[DRY-RUN] Deja envoye aujourd'hui a {user.email} pour {indicateur.libelle[:40]} ({periode_name})"
                    ))
                continue

            subject = build_subject(notif_type, indicateur)

            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"[DRY-RUN] Email serait envoye a {user.email} - {subject}"
                ))
                total_sent += 1
                recipients.add(user.email)
                continue

            try:
                html_body, text_body = render_email_bodies(
                    user, indicateur, periode_name, periode_date, message
                )
                send_mail(
                    subject=subject,
                    message=text_body,
                    html_message=html_body,
                    from_email=f"{email_settings.email_from_name} <{email_settings.email_host_user}>",
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                ReminderEmailLog.objects.create(
                    recipient=user.email,
                    subject=subject,
                    context_hash=context_hash,
                    success=True,
                    user=user,
                )
                self.stdout.write(self.style.SUCCESS(f"Email envoye a {user.email} - {subject}"))
                total_sent += 1
                recipients.add(user.email)

            except Exception as e:
                error_msg = str(e)[:500]
                try:
                    ReminderEmailLog.objects.create(
                        recipient=user.email,
                        subject=subject,
                        context_hash=context_hash,
                        success=False,
                        error_message=error_msg,
                        user=user,
                    )
                except Exception as log_err:
                    logger.error(f"Erreur log: {log_err}")
                self.stderr.write(self.style.ERROR(f"Echec pour {user.email}: {error_msg[:100]}"))

        label = "seraient envoyes" if dry_run else "envoyes"
        self.stdout.write(self.style.SUCCESS(f"{total_sent} emails {label}, {total_skipped} ignores (doublons)"))

        if recipients:
            self.stdout.write(self.style.SUCCESS(f"Destinataires: {', '.join(sorted(recipients))}"))
        else:
            self.stdout.write(self.style.WARNING("Aucun email de rappel pour ce lancement."))

    def _apply_email_config(self, email_settings):
        config = email_settings.get_email_config()
        for key, value in config.items():
            setattr(settings, key, value)
