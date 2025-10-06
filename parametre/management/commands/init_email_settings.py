from django.core.management.base import BaseCommand
from django.conf import settings
from parametre.models import EmailSettings


class Command(BaseCommand):
    help = "Initialize email settings from environment variables"

    def handle(self, *args, **options):
        # Récupérer les paramètres email depuis l'environnement
        env_config = {
            'email_host': getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com'),
            'email_port': getattr(settings, 'EMAIL_PORT', 587),
            'email_host_user': getattr(settings, 'EMAIL_HOST_USER', ''),
            'email_host_password': getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
            'email_use_tls': getattr(settings, 'EMAIL_USE_TLS', True),
            'email_use_ssl': getattr(settings, 'EMAIL_USE_SSL', False),
            'email_from_name': 'KORA',
            'email_timeout': 30
        }

        # Récupérer ou créer l'instance EmailSettings
        email_settings, created = EmailSettings.objects.get_or_create(
            singleton_enforcer=True,
            defaults=env_config
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Configuration email créée avec succès:\n"
                    f"- Host: {email_settings.email_host}\n"
                    f"- Port: {email_settings.email_port}\n"
                    f"- User: {email_settings.email_host_user}\n"
                    f"- TLS: {email_settings.email_use_tls}\n"
                    f"- SSL: {email_settings.email_use_ssl}"
                )
            )
        else:
            # Mettre à jour avec les valeurs de l'environnement si elles sont différentes
            updated = False
            for key, value in env_config.items():
                if getattr(email_settings, key) != value:
                    setattr(email_settings, key, value)
                    updated = True
            
            if updated:
                email_settings.save()
                self.stdout.write(
                    self.style.SUCCESS("Configuration email mise à jour avec les valeurs de l'environnement")
                )
            else:
                self.stdout.write(
                    self.style.WARNING("Configuration email déjà à jour")
                )

        # Afficher la configuration actuelle
        self.stdout.write("\nConfiguration email actuelle:")
        self.stdout.write(f"- Host: {email_settings.email_host}")
        self.stdout.write(f"- Port: {email_settings.email_port}")
        self.stdout.write(f"- User: {email_settings.email_host_user}")
        self.stdout.write(f"- Password: {'*' * len(email_settings.email_host_password) if email_settings.email_host_password else 'Non défini'}")
        self.stdout.write(f"- TLS: {email_settings.email_use_tls}")
        self.stdout.write(f"- SSL: {email_settings.email_use_ssl}")
        self.stdout.write(f"- From Name: {email_settings.email_from_name}")
        self.stdout.write(f"- Timeout: {email_settings.email_timeout}")
