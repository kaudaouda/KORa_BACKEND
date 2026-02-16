import hashlib
from datetime import date, datetime, timedelta
from django.utils import timezone

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.conf import settings

from parametre.models import ReminderEmailLog, EmailSettings, DashboardNotificationSettings
from dashboard.models import Indicateur
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Send reminder emails for dashboard indicators based on frequency periods"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be sent without actually sending emails')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        User = get_user_model()

        # Récupérer la configuration email depuis la base de données
        email_settings = EmailSettings.get_solo()
        
        # Vérifier que la configuration email est complète
        if not email_settings.email_host_user or not email_settings.get_password():
            self.stderr.write(self.style.ERROR("Configuration email incomplète. Veuillez configurer EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans l'admin."))
            return

        # Appliquer la configuration email
        self.apply_email_config(email_settings)

        # Récupérer les paramètres de notification
        dashboard_settings = DashboardNotificationSettings.get_solo()

        # Récupérer les indicateurs avec leurs fréquences
        indicateurs = Indicateur.objects.select_related('frequence_id', 'objective_id', 'objective_id__tableau_bord').all()

        total_notifications = 0

        for indicateur in indicateurs:
            if not indicateur.frequence_id:
                continue

            # Obtenir les dates de fin des périodes selon la fréquence
            periods_to_check = self.get_periods_to_check(indicateur.frequence_id.nom)
            
            for periode_date, periode_name in periods_to_check:
                # Vérifier si on doit envoyer une notification/relance
                notification_type, message = self.check_and_get_notification(
                    indicateur,
                    periode_date,
                    periode_name,
                    dashboard_settings
                )

                if notification_type:
                    # Décider à qui envoyer l'email
                    users_to_notify = self.get_users_to_notify(indicateur)
                    
                    for user in users_to_notify:
                        sent = self.send_notification_email(
                            user,
                            indicateur,
                            periode_name,
                            periode_date,
                            notification_type,
                            message,
                            email_settings,
                            dry_run
                        )
                        if sent:
                            total_notifications += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Mode dry-run: {total_notifications} emails seraient envoyés"))
        else:
            self.stdout.write(self.style.SUCCESS(f"{total_notifications} emails envoyés avec succès"))

    def get_periods_to_check(self, frequence_nom):
        """
        Retourne les dates de fin des périodes à vérifier selon la fréquence
        """
        today = timezone.now().date()
        periods = []

        if frequence_nom == 'Trimestrielle':
            periods = [
                (date(today.year, 3, 31), '1er Trimestre'),
                (date(today.year, 6, 30), '2ème Trimestre'),
                (date(today.year, 9, 30), '3ème Trimestre'),
                (date(today.year, 12, 31), '4ème Trimestre'),
            ]

        elif frequence_nom == 'Semestrielle':
            periods = [
                (date(today.year, 6, 30), '1er Semestre'),
                (date(today.year, 12, 31), '2ème Semestre'),
            ]

        elif frequence_nom == 'Annuelle':
            periods = [
                (date(today.year, 12, 31), 'Année'),
            ]

        return periods

    def check_and_get_notification(self, indicateur, periode_end_date, periode_name, dashboard_settings):
        """
        Vérifie si on doit envoyer une notification et retourne le type et le message
        Retourne: (type, message) ou (None, None)
        """
        today = timezone.now().date()
        
        # Calculer les dates importantes
        alert_start = periode_end_date - timedelta(days=dashboard_settings.days_before_period_end)
        reminder_start = periode_end_date + timedelta(days=dashboard_settings.days_after_period_end)
        
        # Vérifier si on est dans la période d'alerte avant la fin
        if alert_start <= today <= periode_end_date:
            days_until_end = (periode_end_date - today).days
            return ('before', f"La période se termine dans {days_until_end} jour(s)")
        
        # Vérifier si on est après la période de fin (relance)
        elif today > periode_end_date:
            # Vérifier si on doit envoyer une relance
            days_since_end = (today - periode_end_date).days
            if days_since_end >= dashboard_settings.days_after_period_end:
                # Vérifier si on doit encore relancer selon la fréquence
                reminder_frequency = dashboard_settings.reminder_frequency_days
                if days_since_end % reminder_frequency == 0:
                    return ('after', f"La période est terminée depuis {days_since_end} jour(s)")
        
        return (None, None)

    def get_users_to_notify(self, indicateur):
        """
        Détermine à qui envoyer les notifications pour un indicateur donné
        Pour l'instant, on envoie au créateur du tableau de bord
        """
        tableau_bord = indicateur.objective_id.tableau_bord
        if tableau_bord and tableau_bord.cree_par:
            return [tableau_bord.cree_par]
        return []

    def send_notification_email(self, user, indicateur, periode_name, periode_end_date, 
                                notification_type, message, email_settings, dry_run):
        """
        Envoie une notification email à l'utilisateur
        """
        # Construire le sujet et le message
        subject_prefix = "⚠️ RAPPEL" if notification_type == 'before' else "🔔 RELANCE"
        
        objective = indicateur.objective_id
        tableau_bord = objective.tableau_bord
        
        subject = f"KORA - {subject_prefix} Indicateur {indicateur.objective_id.number}"
        
        # Préparer le contexte pour les templates
        from django.template.loader import render_to_string
        
        context = {
            'user_name': user.first_name or user.username,
            'objective_number': objective.number,
            'objective_libelle': objective.libelle,
            'indicateur_libelle': indicateur.libelle,
            'frequence': indicateur.frequence_id.nom,
            'periode_name': periode_name,
            'periode_end_date': periode_end_date.strftime('%d/%m/%Y'),
            'message': message,
            'dashboard_url': f"{getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')}/dashboard"
        }
        
        # Rendre les templates
        html_body = render_to_string('emails/dashboard_reminder_email.html', context)
        text_body = render_to_string('emails/dashboard_reminder_email.txt', context)
        
        # Générer un hash du contexte pour éviter les doublons
        context_key = f"{user.email}:{indicateur.uuid}:{periode_name}:{periode_end_date}:{notification_type}"
        context_hash = hashlib.sha256(context_key.encode('utf-8')).hexdigest()
        
        # Vérifier si on a déjà envoyé cet email aujourd'hui
        already_sent = ReminderEmailLog.objects.filter(
            recipient=user.email,
            context_hash=context_hash,
            sent_at__date=timezone.now().date()
        ).exists()
        
        if already_sent:
            return False
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: Email serait envoyé à {user.email} - {subject}"
                )
            )
            return True
        
        try:
            send_mail(
                subject=subject,
                message=text_body,
                html_message=html_body,
                from_email=f"{email_settings.email_from_name} <{email_settings.email_host_user}>",
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            # Enregistrer l'envoi dans le log
            ReminderEmailLog.objects.create(
                recipient=user.email,
                subject=subject,
                context_hash=context_hash
            )
            
            self.stdout.write(
                self.style.SUCCESS(f"Email envoyé à {user.email} - {subject}")
            )
            
            return True
            
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Erreur lors de l'envoi à {user.email}: {str(e)}")
            )
            return False

    def apply_email_config(self, email_settings):
        """Applique la configuration email depuis la base de données"""
        config = email_settings.get_email_config()
        for key, value in config.items():
            setattr(settings, key, value)


