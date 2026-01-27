"""
Commande sécurisée pour l'envoi de rappels par email
Version sécurisée de send_reminders.py

Security by Design :
- Validation des emails
- Sanitization du contenu
- Rate limiting
- Logging sécurisé
- Gestion d'erreurs robuste
"""
import hashlib
from datetime import date
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from parametre.models import ReminderEmailLog, EmailSettings
from parametre.views import upcoming_notifications, get_client_ip
from parametre.utils.email_security import (
    EmailValidator,
    EmailContentSanitizer,
    EmailRateLimiter,
    SecureEmailLogger
)
from rest_framework.test import APIRequestFactory, force_authenticate

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envoi sécurisé de rappels par email"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Afficher ce qui serait envoyé sans envoyer réellement'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer l\'envoi même si les limites sont atteintes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        User = get_user_model()

        self.stdout.write(self.style.SUCCESS("🔒 Démarrage de l'envoi sécurisé de rappels"))

        # ===== ÉTAPE 1 : Validation de la configuration =====
        try:
            email_settings = EmailSettings.get_solo()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erreur lors de la récupération de la configuration: {str(e)}"))
            return

        # Vérifier que la configuration est complète
        if not email_settings.email_host_user or not email_settings.get_password():
            self.stderr.write(self.style.ERROR(
                "❌ Configuration email incomplète. "
                "Veuillez configurer EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans l'admin."
            ))
            return

        # Test de connexion SMTP
        if not dry_run:
            self.stdout.write("🔌 Test de la connexion SMTP...")
            connection_ok, message = email_settings.test_smtp_connection()
            if not connection_ok:
                self.stderr.write(self.style.ERROR(f"❌ Échec de la connexion SMTP : {message}"))
                return
            self.stdout.write(self.style.SUCCESS(f"✅ Connexion SMTP OK"))

        # Appliquer la configuration
        self.apply_email_config(email_settings)

        # ===== ÉTAPE 2 : Vérification du rate limiting global =====
        if not force and email_settings.enable_rate_limiting:
            if not EmailRateLimiter.check_global_limit():
                self.stderr.write(self.style.ERROR(
                    "❌ Limite globale d'emails dépassée. Utilisez --force pour forcer l'envoi."
                ))
                SecureEmailLogger.log_security_event('rate_limit_reached', {
                    'type': 'global_daily',
                    'command': 'send_reminders_secure'
                })
                return

        # ===== ÉTAPE 3 : Récupération des notifications =====
        factory = APIRequestFactory()
        users = User.objects.filter(is_active=True).exclude(email__isnull=True).exclude(email='')
        
        total_emails = 0
        total_errors = 0
        total_skipped = 0

        for user in users:
            # Valider l'email de l'utilisateur
            if not EmailValidator.is_valid_email(user.email):
                self.stdout.write(self.style.WARNING(
                    f"⚠️ Email invalide pour {user.username}: {SecureEmailLogger.mask_email(user.email)}"
                ))
                total_skipped += 1
                continue

            # Construire une requête authentifiée
            request = factory.get('/api/parametre/upcoming-notifications/')
            force_authenticate(request, user=user)
            response = upcoming_notifications(request)

            if response.status_code != 200:
                continue

            data = response.data or {}
            notifications = data.get('notifications', [])
            if not notifications:
                continue

            # ===== ÉTAPE 4 : Préparation et envoi de l'email =====
            success = self.send_email_to_user(
                user,
                notifications,
                email_settings,
                dry_run,
                force
            )

            if success:
                total_emails += 1
            elif success is False:
                total_errors += 1
            else:  # None = skipped
                total_skipped += 1

        # ===== ÉTAPE 5 : Rapport final =====
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Mode dry-run terminé:\n"
                f"  - {total_emails} emails seraient envoyés\n"
                f"  - {total_errors} erreurs\n"
                f"  - {total_skipped} ignorés"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Envoi terminé:\n"
                f"  - {total_emails} emails envoyés\n"
                f"  - {total_errors} échecs\n"
                f"  - {total_skipped} ignorés"
            ))

    def send_email_to_user(self, user, notifications, email_settings, dry_run, force):
        """
        Envoie un email sécurisé à un utilisateur
        
        Returns:
            True si envoyé, False si erreur, None si ignoré
        """
        # Vérifier le rate limiting utilisateur
        if not force and email_settings.enable_rate_limiting:
            if not EmailRateLimiter.check_user_limit(user.id):
                self.stdout.write(self.style.WARNING(
                    f"⚠️ Limite atteinte pour {user.username}"
                ))
                return None

        # Préparer le sujet (sécurisé)
        subject = EmailContentSanitizer.sanitize_subject(
            f"KORA - Rappel d'échéances ({len(notifications)} élément{'s' if len(notifications) > 1 else ''})"
        )

        frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')

        # Générer les corps (sécurisés)
        html_body = self.generate_secure_html_email(user, notifications, frontend_base)
        text_body = self.generate_secure_text_email(user, notifications, frontend_base)

        # Deduplication
        context_key = f"{user.email}:{date.today().isoformat()}:{hashlib.sha256(html_body.encode('utf-8')).hexdigest()}"
        context_hash = hashlib.sha256(context_key.encode('utf-8')).hexdigest()

        already_sent = ReminderEmailLog.objects.filter(
            recipient=user.email,
            context_hash=context_hash,
            sent_at__date=date.today()
        ).exists()

        if already_sent:
            self.stdout.write(self.style.WARNING(f"⏭️ Déjà envoyé à {user.username}"))
            return None

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[DRY-RUN] Email serait envoyé à {SecureEmailLogger.mask_email(user.email)}: {subject}"
            ))
            return True

        # Envoyer l'email
        try:
            from_email = f"{email_settings.email_from_name} <{email_settings.email_host_user}>"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[user.email]
            )
            email.attach_alternative(html_body, "text/html")
            email.send()

            # Logger le succès
            with transaction.atomic():
                ReminderEmailLog.objects.create(
                    recipient=user.email,
                    subject=subject,
                    context_hash=context_hash,
                    success=True,
                    user=user
                )

            SecureEmailLogger.log_email_sent(user.email, subject, True)
            self.stdout.write(self.style.SUCCESS(
                f"✅ Envoyé à {SecureEmailLogger.mask_email(user.email)}"
            ))

            return True

        except Exception as e:
            # Logger l'échec
            error_message = str(e)[:500]  # Limiter la taille

            try:
                with transaction.atomic():
                    ReminderEmailLog.objects.create(
                        recipient=user.email,
                        subject=subject,
                        context_hash=context_hash,
                        success=False,
                        error_message=error_message,
                        user=user
                    )
            except Exception as log_error:
                logger.error(f"Erreur lors de la création du log: {str(log_error)}")

            SecureEmailLogger.log_email_sent(user.email, subject, False)
            self.stderr.write(self.style.ERROR(
                f"❌ Échec pour {SecureEmailLogger.mask_email(user.email)}: {error_message[:100]}"
            ))

            return False

    def generate_secure_html_email(self, user, notifications, frontend_base):
        """
        Génère un email HTML sécurisé
        Security by Design : Sanitization complète
        """
        from datetime import datetime

        # Sanitizer toutes les données utilisateur
        user_name = EmailContentSanitizer.sanitize_html(
            user.get_full_name() or user.username
        )
        current_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Générer les items de notification (sécurisés)
        notification_items = ""
        for i, n in enumerate(notifications, 1):
            title = EmailContentSanitizer.sanitize_html(n.get('title', 'Échéance'))
            message = EmailContentSanitizer.sanitize_html(n.get('message', ''))
            due = n.get('due_date', '')
            url = EmailContentSanitizer.sanitize_url(n.get('action_url', '/'))
            priority = n.get('priority', 'medium')

            priority_color = {
                'high': '#EF4444',
                'medium': '#F59E0B',
                'low': '#10B981'
            }.get(priority, '#3B82F6')

            # Formater la date
            try:
                due_date = datetime.fromisoformat(due.replace('Z', '+00:00')).strftime("%d/%m/%Y")
            except:
                due_date = EmailContentSanitizer.sanitize_html(str(due))

            notification_items += f"""
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <div style="width: 4px; height: 20px; background: {priority_color}; border-radius: 2px; margin-right: 12px;"></div>
                    <h3 style="margin: 0; color: #111827; font-size: 16px;">{title}</h3>
                </div>
                <p style="margin: 4px 0; color: #4B5563; font-size: 14px;">{message}</p>
                <div style="margin-top: 12px;">
                    <span style="color: #4B5563; font-size: 13px;">Échéance: <strong>{due_date}</strong></span>
                </div>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>KORA - Rappel d'échéances</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #F9FAFB;">
            <div style="max-width: 600px; margin: 0 auto; background: #FFFFFF;">
                <div style="background: linear-gradient(135deg, #F97316 0%, #3B82F6 100%); padding: 24px; text-align: center;">
                    <h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">KORA</h1>
                    <p style="margin: 8px 0 0 0; color: #FFFFFF;">Rappel d'échéances</p>
                </div>
                
                <div style="padding: 24px;">
                    <p style="margin: 0 0 16px 0; color: #111827;">
                        Madame, Monsieur <strong>{user_name}</strong>,
                    </p>
                    
                    <p style="margin: 0 0 20px 0; color: #4B5563;">
                        Vous avez des échéances approchant dans KORA.
                    </p>
                    
                    {notification_items}
                </div>
                
                <div style="background: #F3F4F6; padding: 20px; text-align: center;">
                    <p style="margin: 0; color: #4B5563; font-size: 12px;">
                        Message automatique KORA • {current_date}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def generate_secure_text_email(self, user, notifications, frontend_base):
        """
        Génère un email texte sécurisé
        Security by Design : Pas d'injection possible
        """
        lines = [
            f"Madame, Monsieur {user.get_full_name() or user.username},",
            "",
            "Vous avez des échéances approchant dans KORA.",
            "",
        ]

        for i, n in enumerate(notifications, 1):
            title = n.get('title', 'Échéance')
            message = n.get('message', '')
            due = n.get('due_date', '')

            lines.append(f"{i}. {title}")
            lines.append(f"   {message}")
            lines.append(f"   Échéance: {due}")
            lines.append("")

        lines.extend([
            "Cordialement,",
            "L'équipe KORA"
        ])

        return "\n".join(lines)

    def apply_email_config(self, email_settings):
        """Applique la configuration email"""
        config = email_settings.get_email_config()
        for key, value in config.items():
            setattr(settings, key, value)
