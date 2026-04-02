"""
Commande pour l'envoi des rappels de plans d'action de la Cartographie des Risques (CDR).
Suit le meme pattern que send_reminders_secure (deduplication, rate limiting, dry-run, log).
"""
import hashlib
import logging
from datetime import date, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db import transaction
from django.template.loader import render_to_string

from parametre.models import ReminderEmailLog, EmailSettings, Role, UserProcessusRole
from parametre.services.cdr_notification_service import get_cdr_notifications
from parametre.utils.email_security import (
    EmailValidator,
    EmailContentSanitizer,
    EmailRateLimiter,
    SecureEmailLogger,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envoi des rappels par email pour les plans d'action CDR (Cartographie des Risques)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Afficher ce qui serait envoye sans envoyer reellement',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help="Forcer l'envoi meme si les limites sont atteintes",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force   = options['force']
        User    = get_user_model()

        self.stdout.write(self.style.SUCCESS("Demarrage envoi rappels CDR"))

        # ── 1. Config email ──────────────────────────────────────────────────
        try:
            email_settings = EmailSettings.get_solo()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erreur config email: {e}"))
            return

        if not email_settings.email_host_user or not email_settings.get_password():
            self.stderr.write(self.style.ERROR(
                "Configuration email incomplete. Configurez EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans l'admin."
            ))
            return

        if not dry_run:
            ok, msg = email_settings.test_smtp_connection()
            if not ok:
                self.stderr.write(self.style.ERROR(f"Echec connexion SMTP: {msg}"))
                return
            self.stdout.write(self.style.SUCCESS("Connexion SMTP OK"))

        self._apply_email_config(email_settings)

        # ── 2. Rate limiting global ──────────────────────────────────────────
        if not force and email_settings.enable_rate_limiting:
            if not EmailRateLimiter.check_global_limit():
                self.stderr.write(self.style.ERROR(
                    "Limite globale d'emails atteinte. Utilisez --force pour forcer."
                ))
                return

        # ── 3. Utilisateurs eligibles ────────────────────────────────────────
        normal_roles = Role.objects.filter(
            code__in=['contributeur', 'responsable_processus'],
            is_active=True,
        )
        admin_role = Role.objects.filter(code='admin', is_active=True).first()

        if not normal_roles.exists():
            self.stderr.write(self.style.ERROR(
                "Aucun role 'contributeur' ou 'responsable_processus' trouve."
            ))
            return

        users_qs = User.objects.filter(
            is_active=True,
            email__isnull=False,
            user_processus_roles__role__in=normal_roles,
            user_processus_roles__is_active=True,
        )
        if admin_role:
            users_qs = users_qs.exclude(
                user_processus_roles__role=admin_role,
                user_processus_roles__is_active=True,
            )
        users_qs = users_qs.distinct()

        users_count = users_qs.count()
        self.stdout.write(self.style.SUCCESS(f"{users_count} utilisateur(s) eligible(s)"))

        if users_count == 0:
            self.stdout.write(self.style.WARNING("Aucun utilisateur eligible. Fin."))
            return

        # ── 4. Envoi par utilisateur ─────────────────────────────────────────
        total_sent    = 0
        total_errors  = 0
        total_skipped = 0
        all_notifs_for_admin = []

        for user in users_qs:
            if not EmailValidator.is_valid_email(user.email):
                self.stdout.write(self.style.WARNING(
                    f"Email invalide pour {user.username}: {SecureEmailLogger.mask_email(user.email)}"
                ))
                total_skipped += 1
                continue

            data          = get_cdr_notifications(user)
            notifications = data.get('notifications', [])

            if dry_run:
                if notifications:
                    self.stdout.write(self.style.SUCCESS(
                        f"{user.username}: {len(notifications)} notification(s)"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"{user.username}: aucune notification CDR"
                    ))

            if not notifications:
                total_skipped += 1
                continue

            result = self._send_email_to_user(
                user, notifications, email_settings, dry_run, force
            )
            if result is True:
                total_sent += 1
                all_notifs_for_admin.append({'user': user, 'notifications': notifications})
            elif result is False:
                total_errors += 1
            else:
                total_skipped += 1

        # ── 5. Email recapitulatif admin ─────────────────────────────────────
        if all_notifs_for_admin:
            try:
                self._send_admin_alert(all_notifs_for_admin, email_settings, dry_run)
            except Exception as e:
                logger.error("Erreur alerte admin CDR: %s", e)

        # ── 6. Rapport ───────────────────────────────────────────────────────
        label = "seraient envoyes" if dry_run else "envoyes"
        self.stdout.write(self.style.SUCCESS(
            f"\nRapport CDR:\n"
            f"  - {total_sent} emails {label}\n"
            f"  - {total_errors} echecs\n"
            f"  - {total_skipped} ignores"
        ))

    # ────────────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────────────

    def _send_email_to_user(self, user, notifications, email_settings, dry_run, force):
        """Envoie un email de rappel CDR a un utilisateur. Retourne True/False/None."""

        if not force and email_settings.enable_rate_limiting:
            if not EmailRateLimiter.check_user_limit(user.id):
                self.stdout.write(self.style.WARNING(f"Limite atteinte pour {user.username}"))
                return None

        subject = EmailContentSanitizer.sanitize_subject(
            f"KORA - Rappel CDR ({len(notifications)} plan{'s' if len(notifications) > 1 else ''})"
        )

        # Hash déduplication
        ids_key      = ':'.join(sorted(n.get('id', '') for n in notifications))
        content_hash = hashlib.sha256(ids_key.encode()).hexdigest()
        context_key  = f"{user.email}:{date.today().isoformat()}:{content_hash}"
        context_hash = hashlib.sha256(context_key.encode()).hexdigest()

        # Déduplication
        already_sent = ReminderEmailLog.objects.filter(
            recipient=user.email,
            context_hash=context_hash,
            sent_at__date=date.today(),
        ).exists()

        if already_sent:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"[DRY-RUN] Email identique deja envoye aujourd'hui a {user.username} (serait ignore)"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Email identique deja envoye aujourd'hui a {user.username}, ignore"
                ))
            return None

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY-RUN] Email serait envoye a {SecureEmailLogger.mask_email(user.email)} — {subject}"
            ))
            return True

        # Génération des corps
        html_body = self._render_html(user, notifications)
        text_body = self._render_text(user, notifications)

        try:
            from_email = f"{email_settings.email_from_name} <{email_settings.email_host_user}>"
            msg = EmailMultiAlternatives(subject=subject, body=text_body,
                                         from_email=from_email, to=[user.email])
            msg.attach_alternative(html_body, "text/html")
            msg.send()

            with transaction.atomic():
                ReminderEmailLog.objects.create(
                    recipient=user.email,
                    subject=subject,
                    context_hash=context_hash,
                    success=True,
                    user=user,
                )

            SecureEmailLogger.log_email_sent(user.email, subject, True)
            self.stdout.write(self.style.SUCCESS(
                f"Envoye a {SecureEmailLogger.mask_email(user.email)}"
            ))
            return True

        except Exception as e:
            error_msg = str(e)[:500]
            try:
                with transaction.atomic():
                    ReminderEmailLog.objects.create(
                        recipient=user.email,
                        subject=subject,
                        context_hash=context_hash,
                        success=False,
                        error_message=error_msg,
                        user=user,
                    )
            except Exception as log_err:
                logger.error("Erreur log CDR: %s", log_err)

            SecureEmailLogger.log_email_sent(user.email, subject, False)
            self.stderr.write(self.style.ERROR(
                f"Echec pour {SecureEmailLogger.mask_email(user.email)}: {error_msg[:100]}"
            ))
            return False

    def _render_html(self, user, notifications):
        current_date = datetime.now().strftime("%d/%m/%Y a %H:%M")
        context = {
            'user_name': EmailContentSanitizer.sanitize_html(
                user.get_full_name() or user.username
            ),
            'notifications': self._prepare_notifications(notifications),
            'current_date': current_date,
        }
        return render_to_string('emails/cdr_reminder_email.html', context)

    def _render_text(self, user, notifications):
        current_date = datetime.now().strftime("%d/%m/%Y a %H:%M")
        context = {
            'user_name': user.get_full_name() or user.username,
            'notifications': self._prepare_notifications(notifications),
            'current_date': current_date,
        }
        return render_to_string('emails/cdr_reminder_email.txt', context)

    def _prepare_notifications(self, notifications):
        """Prépare et sanitize les notifications pour les templates."""
        prepared = []
        for n in notifications:
            due = n.get('due_date', '')
            try:
                due_fmt = datetime.fromisoformat(due).strftime("%d/%m/%Y")
            except Exception:
                due_fmt = str(due)

            priority = n.get('priority', 'medium')
            prepared.append({
                'numero_cdr':      EmailContentSanitizer.sanitize_html(n.get('numero_cdr', 'N/A')),
                'processus':       EmailContentSanitizer.sanitize_html(n.get('processus', 'N/A')),
                'action':          EmailContentSanitizer.sanitize_html(n.get('title', '')[:100]),
                'responsables':    [EmailContentSanitizer.sanitize_html(r) for r in n.get('responsables', [])],
                'due_date_formatted': due_fmt,
                'days_remaining':  n.get('days_remaining', 0),
                'priority':        priority,
            })
        return prepared

    def _send_admin_alert(self, all_notifs, email_settings, dry_run):
        """Envoie un email recapitulatif aux admins."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        admin_role = Role.objects.filter(code='admin', is_active=True).first()
        if not admin_role:
            return

        admins = User.objects.filter(
            is_active=True,
            email__isnull=False,
            user_processus_roles__role=admin_role,
            user_processus_roles__is_active=True,
        ).distinct()

        if not admins.exists():
            return

        # Dédupliquer les plans d'action
        seen_plans = set()
        unique_plans = []
        for entry in all_notifs:
            for n in entry['notifications']:
                pid = n.get('entity_id')
                if pid and pid not in seen_plans:
                    seen_plans.add(pid)
                    unique_plans.append(n)

        total = len(unique_plans)
        subject = EmailContentSanitizer.sanitize_subject(
            f"KORA - Alerte Admin CDR : {total} plan{'s' if total > 1 else ''} a echeance"
        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY-RUN] Alerte admin CDR serait envoyee ({total} plans, {admins.count()} admin(s))"
            ))
            return

        current_date = datetime.now().strftime("%d/%m/%Y a %H:%M")
        context = {
            'total_plans': total,
            'notifications': self._prepare_notifications(unique_plans),
            'current_date': current_date,
        }
        html_body = render_to_string('emails/cdr_reminder_email.html', {
            **context, 'user_name': 'Administrateur'
        })
        text_body = render_to_string('emails/cdr_reminder_email.txt', {
            **context, 'user_name': 'Administrateur'
        })

        from_email = f"{email_settings.email_from_name} <{email_settings.email_host_user}>"
        for admin in admins:
            if not EmailValidator.is_valid_email(admin.email):
                continue
            try:
                msg = EmailMultiAlternatives(subject=subject, body=text_body,
                                             from_email=from_email, to=[admin.email])
                msg.attach_alternative(html_body, "text/html")
                msg.send()
                self.stdout.write(self.style.SUCCESS(
                    f"Alerte admin CDR envoyee a {SecureEmailLogger.mask_email(admin.email)}"
                ))
            except Exception as e:
                logger.error("Erreur alerte admin CDR pour %s: %s", admin.email, e)

    def _apply_email_config(self, email_settings):
        config = email_settings.get_email_config()
        for key, value in config.items():
            setattr(settings, key, value)
