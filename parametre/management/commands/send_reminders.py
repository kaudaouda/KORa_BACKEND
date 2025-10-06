import hashlib
from datetime import date

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.conf import settings

from parametre.models import ReminderEmailLog
from parametre.views import upcoming_notifications
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Send reminder emails to users based on upcoming notifications logic"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print emails without sending')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        User = get_user_model()

        factory = APIRequestFactory()

        # Iterate over active users with email
        users = User.objects.filter(is_active=True).exclude(email__isnull=True).exclude(email='')
        total_emails = 0

        for user in users:
            # Build an authenticated request to reuse the existing view logic
            request = factory.get('/api/parametre/upcoming-notifications/')
            force_authenticate(request, user=user)
            response = upcoming_notifications(request)

            if response.status_code != 200:
                continue

            data = response.data or {}
            notifications = data.get('notifications', [])
            if not notifications:
                continue

            # Compose a formal HTML email with KORA design
            subject = f"KORA - Rappel d'échéances ({len(notifications)} élément{'s' if len(notifications) > 1 else ''})"

            frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')
            
            # Generate HTML email with KORA design
            html_body = self.generate_html_email(user, notifications, frontend_base)
            
            # Also generate plain text version for email clients that don't support HTML
            text_body = self.generate_text_email(user, notifications, frontend_base)

            # Dedup: avoid sending multiple emails with same content per user per day
            context_key = f"{user.email}:{date.today().isoformat()}:{hashlib.sha256(html_body.encode('utf-8')).hexdigest()}"
            context_hash = hashlib.sha256(context_key.encode('utf-8')).hexdigest()

            already_sent = ReminderEmailLog.objects.filter(
                recipient=user.email,
                context_hash=context_hash,
                sent_at__date=date.today()
            ).exists()

            if already_sent:
                continue

            if dry_run:
                self.stdout.write(self.style.WARNING(f"[DRY-RUN] Would send to {user.email}: {subject}"))
                self.stdout.write("HTML Email:")
                self.stdout.write(html_body)
                self.stdout.write("\n" + "="*50 + "\n")
                self.stdout.write("Text Email:")
                self.stdout.write(text_body)
            else:
                try:
                    from django.core.mail import EmailMultiAlternatives
                    
                    # Create email with both HTML and text versions
                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[user.email]
                    )
                    email.attach_alternative(html_body, "text/html")
                    email.send()
                    
                    ReminderEmailLog.objects.create(
                        recipient=user.email,
                        subject=subject,
                        context_hash=context_hash,
                    )
                    total_emails += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Failed to send to {user.email}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done. Emails sent: {total_emails}"))

    def generate_html_email(self, user, notifications, frontend_base):
        """Generate HTML email with KORA design"""
        from datetime import datetime
        
        # KORA color palette
        colors = {
            'primary': '#F97316',      
            'secondary': '#3B82F6',
            'neutral_50': '#F9FAFB',   
            'neutral_100': '#F3F4F6',  
            'neutral_200': '#E5E7EB',  
            'neutral_600': '#4B5563',  
            'neutral_900': '#111827',  
            'white': '#FFFFFF',
        }
        
        # Get current date
        current_date = datetime.now().strftime("%d/%m/%Y à %H:%M")
        
        # Generate notification items HTML
        notification_items = ""
        for i, n in enumerate(notifications, 1):
            title = n.get('title', 'Échéance')
            message = n.get('message', '')
            due = n.get('due_date', '')
            url = n.get('action_url', '/')
            priority = n.get('priority', 'medium')
            
            # Priority color
            priority_color = {
                'high': '#EF4444',    
                'medium': '#F59E0B',  
                'low': '#10B981'      
            }.get(priority, colors['secondary'])
            
            # Format date
            try:
                due_date = datetime.fromisoformat(due.replace('Z', '+00:00')).strftime("%d/%m/%Y")
            except:
                due_date = due
            
            notification_items += f"""
            <div style="background: {colors['white']}; border: 1px solid {colors['neutral_200']}; border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <div style="width: 4px; height: 20px; background: {priority_color}; border-radius: 2px; margin-right: 12px;"></div>
                    <h3 style="margin: 0; color: {colors['neutral_900']}; font-size: 16px; font-weight: 600;">{title}</h3>
                </div>
                <p style="margin: 4px 0; color: {colors['neutral_600']}; font-size: 14px;">{message}</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
                    <span style="color: {colors['neutral_600']}; font-size: 13px;">Échéance: <strong>{due_date}</strong></span>
                    <a href="{frontend_base}{url}" style="background: {colors['primary']}; color: {colors['white']}; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 13px; font-weight: 500;">Voir les détails</a>
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
        <body style="margin: 0; padding: 0; font-family: 'Poppins', Arial, sans-serif; background-color: {colors['neutral_50']};">
            <div style="max-width: 600px; margin: 0 auto; background: {colors['white']};">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, {colors['primary']} 0%, {colors['secondary']} 100%); padding: 24px; text-align: center; border-radius: 8px 8px 0 0;">
                    <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 16px;">
                        <div style="width: 40px; height: 40px; background: {colors['white']}; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-right: 12px;">
                            <span style="color: {colors['primary']}; font-size: 20px; font-weight: bold;">K</span>
                        </div>
                        <h1 style="margin: 0; color: {colors['white']}; font-size: 24px; font-weight: 700;">KORA</h1>
                    </div>
                    <p style="margin: 0; color: {colors['white']}; font-size: 16px; opacity: 0.9;">Rappel d'échéances</p>
                </div>
                
                <!-- Content -->
                <div style="padding: 24px;">
                    <p style="margin: 0 0 16px 0; color: {colors['neutral_900']}; font-size: 16px; line-height: 1.5;">
                        Madame, Monsieur <strong>{user.get_full_name() or user.username}</strong>,
                    </p>
                    
                    <p style="margin: 0 0 20px 0; color: {colors['neutral_600']}; font-size: 14px; line-height: 1.6;">
                        Nous vous informons que vous avez des échéances approchant dans le système KORA.
                    </p>
                    
                    <h2 style="margin: 0 0 16px 0; color: {colors['neutral_900']}; font-size: 18px; font-weight: 600;">Détails des échéances :</h2>
                    
                    {notification_items}
                    
                    <div style="background: {colors['neutral_100']}; padding: 16px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {colors['primary']};">
                        <p style="margin: 0; color: {colors['neutral_600']}; font-size: 14px; line-height: 1.6;">
                            Nous vous remercions de votre attention et vous prions de bien vouloir traiter ces éléments dans les délais impartis.
                        </p>
                    </div>
                </div>
                
                <!-- Footer -->
                <div style="background: {colors['neutral_100']}; padding: 20px; text-align: center; border-radius: 0 0 8px 8px; border-top: 1px solid {colors['neutral_200']};">
                    <p style="margin: 0 0 8px 0; color: {colors['neutral_600']}; font-size: 14px;">
                        Cordialement,<br>
                        <strong>L'équipe KORA</strong>
                    </p>
                    <p style="margin: 0; color: {colors['neutral_600']}; font-size: 12px; opacity: 0.7;">
                        Ce message est généré automatiquement par le système KORA • {current_date}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

    def generate_text_email(self, user, notifications, frontend_base):
        """Generate plain text email version"""
        lines = [
            f"Madame, Monsieur {user.get_full_name() or user.username},",
            "",
            "Nous vous informons que vous avez des échéances approchant dans le système KORA.",
            "",
            "Détails des échéances :",
            "",
        ]

        for i, n in enumerate(notifications, 1):
            title = n.get('title', 'Échéance')
            message = n.get('message', '')
            due = n.get('due_date', '')
            url = n.get('action_url', '/')
            
            # Format date
            try:
                from datetime import datetime
                due_date = datetime.fromisoformat(due.replace('Z', '+00:00')).strftime("%d/%m/%Y")
            except:
                due_date = due
            
            lines.append(f"{i}. {title}")
            lines.append(f"   - Détail : {message}")
            lines.append(f"   - Date d'échéance : {due_date}")
            lines.append(f"   - Lien d'accès : {frontend_base}{url}")
            lines.append("")

        lines.extend([
            "Nous vous remercions de votre attention et vous prions de bien vouloir traiter ces éléments dans les délais impartis.",
            "",
            "Cordialement,",
            "L'équipe KORA",
            "",
            "---",
            "Ce message est généré automatiquement par le système KORA."
        ])

        return "\n".join(lines)


