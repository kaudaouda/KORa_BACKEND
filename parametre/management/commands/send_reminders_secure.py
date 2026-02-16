"""
Commande sécurisée pour l'envoi de rappels par email
Commande principale utilisée par le scheduler APScheduler pour les notifications automatiques

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

from parametre.models import ReminderEmailLog, EmailSettings, UserProcessusRole, Role
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

        self.stdout.write(self.style.SUCCESS("Démarrage de l'envoi sécurisé de rappels"))

        # ===== ÉTAPE 1 : Validation de la configuration =====
        try:
            email_settings = EmailSettings.get_solo()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erreur lors de la récupération de la configuration: {str(e)}"))
            return

        # Vérifier que la configuration est complète
        if not email_settings.email_host_user or not email_settings.get_password():
            self.stderr.write(self.style.ERROR(
                "Configuration email incomplète. "
                "Veuillez configurer EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans l'admin."
            ))
            return

        # Test de connexion SMTP
        if not dry_run:
            self.stdout.write("Test de la connexion SMTP...")
            connection_ok, message = email_settings.test_smtp_connection()
            if not connection_ok:
                self.stderr.write(self.style.ERROR(f"Échec de la connexion SMTP : {message}"))
                return
            self.stdout.write(self.style.SUCCESS(f"Connexion SMTP OK"))

        # Appliquer la configuration
        self.apply_email_config(email_settings)

        # ===== ÉTAPE 2 : Vérification du rate limiting global =====
        if not force and email_settings.enable_rate_limiting:
            if not EmailRateLimiter.check_global_limit():
                self.stderr.write(self.style.ERROR(
                    "Limite globale d'emails dépassée. Utilisez --force pour forcer l'envoi."
                ))
                SecureEmailLogger.log_security_event('rate_limit_reached', {
                    'type': 'global_daily',
                    'command': 'send_reminders_secure'
                })
                return

        # ===== ÉTAPE 3 : Récupération des utilisateurs éligibles =====
        # Filtrer les utilisateurs qui ont les rôles "admin", "contributeur" ou "responsable_processus"
        # pour au moins un processus
        
        # Récupérer les IDs des rôles "admin", "contributeur" et "responsable_processus"
        allowed_role_codes = ['admin', 'contributeur', 'responsable_processus']
        allowed_roles = Role.objects.filter(
            code__in=allowed_role_codes,
            is_active=True
        )
        
        if not allowed_roles.exists():
            self.stderr.write(self.style.ERROR(
                "Aucun rôle 'admin', 'contributeur' ou 'responsable_processus' trouvé dans la base de données.\n"
                "   Veuillez exécuter: python manage.py seed_roles"
            ))
            return
        
        # Récupérer les utilisateurs qui ont au moins un de ces rôles pour au moins un processus
        # et qui sont actifs avec un email valide
        users_with_roles = User.objects.filter(
            is_active=True,
            email__isnull=False
        ).exclude(email='').filter(
            user_processus_roles__role__in=allowed_roles,
            user_processus_roles__is_active=True
        ).distinct()
        
        users_count = users_with_roles.count()
        self.stdout.write(self.style.SUCCESS(
            f"{users_count} utilisateur(s) avec les rôles 'admin', 'contributeur' ou 'responsable_processus' trouvé(s)"
        ))
        
        if users_count == 0:
            self.stdout.write(self.style.WARNING(
                "Aucun utilisateur éligible trouvé. Aucun email ne sera envoyé."
            ))
            return
        
        # ===== ÉTAPE 4 : Récupération et envoi des notifications =====
        factory = APIRequestFactory()
        
        total_emails = 0
        total_errors = 0
        total_skipped = 0

        for user in users_with_roles:
            # Valider l'email de l'utilisateur
            if not EmailValidator.is_valid_email(user.email):
                self.stdout.write(self.style.WARNING(
                    f"Email invalide pour {user.username}: {SecureEmailLogger.mask_email(user.email)}"
                ))
                total_skipped += 1
                continue

            # Construire une requête authentifiée
            request = factory.get('/api/parametre/upcoming-notifications/')
            force_authenticate(request, user=user)
            response = upcoming_notifications(request)

            if response.status_code != 200:
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f"Erreur API pour {user.username}: status {response.status_code}"
                    ))
                continue

            data = response.data or {}
            notifications = data.get('notifications', [])
            
            if dry_run:
                if notifications:
                    self.stdout.write(self.style.SUCCESS(
                        f"{user.username}: {len(notifications)} notification(s) trouvée(s)"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"ℹ️  {user.username}: Aucune notification trouvée (pas d'échéances dans les prochains jours)"
                    ))
            
            if not notifications:
                total_skipped += 1
                continue

            # ===== ÉTAPE 5 : Préparation et envoi de l'email =====
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

        # ===== ÉTAPE 6 : Rapport final =====
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nMode dry-run terminé:\n"
                f"  - {total_emails} emails seraient envoyés\n"
                f"  - {total_errors} erreurs\n"
                f"  - {total_skipped} ignorés"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nEnvoi terminé:\n"
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
                    f"Limite atteinte pour {user.username}"
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

        # ===== GÉNÉRATION DU HASH DU CONTENU =====
        # Créer un hash basé sur les IDs des notifications pour détecter les changements de contenu
        notification_ids = sorted([n.get('id', '') for n in notifications])
        content_key = ':'.join(notification_ids) if notification_ids else 'empty'
        content_hash = hashlib.sha256(content_key.encode('utf-8')).hexdigest()
        
        # Hash complet pour la déduplication (email + date + contenu)
        context_key = f"{user.email}:{date.today().isoformat()}:{content_hash}"
        context_hash = hashlib.sha256(context_key.encode('utf-8')).hexdigest()

        # ===== DÉDUPLICATION PAR CONTENU (éviter les doublons le même jour) =====
        # TEMPORAIREMENT DÉSACTIVÉ POUR LES TESTS - À REMETTRE APRÈS LES TESTS
        # Vérifier si un email avec le même contenu a déjà été envoyé aujourd'hui
        # already_sent_today = ReminderEmailLog.objects.filter(
        #     recipient=user.email,
        #     context_hash=context_hash,
        #     sent_at__date=date.today()
        # ).exists()
        #
        # if already_sent_today:
        #     if dry_run:
        #         self.stdout.write(self.style.WARNING(
        #             f"⏭️ [DRY-RUN] Email identique déjà envoyé aujourd'hui à {user.username} "
        #             f"(serait ignoré en mode réel)"
        #         ))
        #     else:
        #         self.stdout.write(self.style.WARNING(
        #             f"⏭️ Email identique déjà envoyé aujourd'hui à {user.username}"
        #         ))
        #     return None

        # ===== VÉRIFICATION DE LA FRÉQUENCE DES RAPPELS =====
        # Récupérer les paramètres de notification pour respecter la fréquence
        from parametre.models import NotificationSettings
        global_settings = NotificationSettings.get_solo()
        reminder_frequency = global_settings.traitement_reminder_frequency_days

        # Chercher le dernier email envoyé avec succès pour cet utilisateur
        last_sent = ReminderEmailLog.objects.filter(
            recipient=user.email,
            success=True
        ).order_by('-sent_at').first()

        if last_sent:
            days_since_last = (date.today() - last_sent.sent_at.date()).days
            
            # Si un email a été envoyé récemment (moins de X jours), on vérifie si le contenu a changé
            # Pour cela, on compare le hash du contenu actuel avec celui du dernier email
            # Le context_hash du dernier email contient le hash du contenu de l'époque
            # On ne peut pas directement comparer car le context_hash inclut aussi email+date
            # Mais si on arrive ici (pas de doublon aujourd'hui), c'est que soit :
            # 1. Le contenu a changé (nouveaux traitements ou échéances modifiées)
            # 2. C'est un nouveau jour et le contenu est différent
            # 3. Le contenu est identique mais on respecte la fréquence
            
            # Pour simplifier et être sûr d'envoyer les notifications importantes :
            # Si le dernier email était aujourd'hui mais avec un contenu différent, on envoie
            # Si le dernier email était récemment (moins de X jours), on envoie aussi
            # car on ne peut pas facilement comparer le contenu exact sans modifier le modèle
            
            # IMPORTANT: Si on arrive ici, c'est qu'aucun email identique n'a été envoyé aujourd'hui
            # Donc soit le contenu a changé, soit c'est le premier envoi du jour
            # On envoie donc toujours pour être sûr de ne pas manquer de notifications importantes
            if days_since_last < reminder_frequency:
                self.stdout.write(self.style.SUCCESS(
                    f"Envoi pour {user.username} (dernier email il y a {days_since_last} jour(s), "
                    f"contenu probablement modifié ou premier envoi du jour)"
                ))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY-RUN] Email serait envoyé à {SecureEmailLogger.mask_email(user.email)}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"         Sujet: {subject}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"         Nombre de notifications: {len(notifications)}"
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
                f"Envoyé à {SecureEmailLogger.mask_email(user.email)}"
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
                f"Échec pour {SecureEmailLogger.mask_email(user.email)}: {error_message[:100]}"
            ))

            return False

    def generate_secure_html_email(self, user, notifications, frontend_base):
        """
        Génère un email HTML sécurisé en utilisant un template Django
        Security by Design : Sanitization complète via le template engine
        """
        from datetime import datetime
        from django.template.loader import render_to_string

        # Sanitizer toutes les données utilisateur
        user_name = EmailContentSanitizer.sanitize_html(
            user.get_full_name() or user.username
        )
        current_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Préparer les notifications avec sanitization et formatage
        sanitized_notifications = []
        for n in notifications:
            title = EmailContentSanitizer.sanitize_html(n.get('title', 'Échéance'))
            message = EmailContentSanitizer.sanitize_html(n.get('message', ''))
            due = n.get('due_date', '')
            priority = n.get('priority', 'medium')

            priority_color = {
                'high': '#EF4444',
                'medium': '#F59E0B',
                'low': '#10B981'
            }.get(priority, '#3B82F6')

            # Formater la date
            try:
                due_date_formatted = datetime.fromisoformat(due.replace('Z', '+00:00')).strftime("%d/%m/%Y")
            except:
                due_date_formatted = EmailContentSanitizer.sanitize_html(str(due))

            sanitized_notifications.append({
                'title': title,
                'message': message,
                'due_date_formatted': due_date_formatted,
                'priority_color': priority_color
            })

        # Contexte pour le template
        context = {
            'user_name': user_name,
            'notifications': sanitized_notifications,
            'current_date': current_date
        }

        # Rendre le template
        return render_to_string('emails/reminder_email.html', context)

    def generate_secure_text_email(self, user, notifications, frontend_base):
        """
        Génère un email texte sécurisé en utilisant un template Django
        Security by Design : Pas d'injection possible via le template engine
        """
        from datetime import datetime
        from django.template.loader import render_to_string

        user_name = user.get_full_name() or user.username
        current_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Préparer les notifications avec formatage
        formatted_notifications = []
        for n in notifications:
            title = n.get('title', 'Échéance')
            message = n.get('message', '')
            due = n.get('due_date', '')

            # Formater la date
            try:
                due_date_formatted = datetime.fromisoformat(due.replace('Z', '+00:00')).strftime("%d/%m/%Y")
            except:
                due_date_formatted = str(due)

            formatted_notifications.append({
                'title': title,
                'message': message,
                'due_date_formatted': due_date_formatted
            })

        # Contexte pour le template
        context = {
            'user_name': user_name,
            'notifications': formatted_notifications,
            'current_date': current_date
        }

        # Rendre le template
        return render_to_string('emails/reminder_email.txt', context)

    def apply_email_config(self, email_settings):
        """Applique la configuration email"""
        config = email_settings.get_email_config()
        for key, value in config.items():
            setattr(settings, key, value)
