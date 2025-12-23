"""
Commande pour initialiser les configurations des applications
Security by Design : Toutes les applications sont activées par défaut
"""
from django.core.management.base import BaseCommand
from parametre.models import ApplicationConfig


class Command(BaseCommand):
    help = 'Initialise les configurations des applications (toutes activées par défaut)'

    def handle(self, *args, **options):
        """
        Crée les configurations pour toutes les applications
        Security by Design : is_enabled=True par défaut
        """
        applications = [
            {
                'app_name': 'dashboard',
                'is_enabled': True,
                'maintenance_message': ''
            },
            {
                'app_name': 'pac',
                'is_enabled': True,
                'maintenance_message': ''
            },
            {
                'app_name': 'cdr',
                'is_enabled': True,
                'maintenance_message': ''
            },
            {
                'app_name': 'activite_periodique',
                'is_enabled': True,
                'maintenance_message': ''
            },
            {
                'app_name': 'documentation',
                'is_enabled': True,
                'maintenance_message': ''
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for app_data in applications:
            config, created = ApplicationConfig.objects.get_or_create(
                app_name=app_data['app_name'],
                defaults={
                    'is_enabled': app_data['is_enabled'],
                    'maintenance_message': app_data['maintenance_message']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Configuration créée pour '{config.get_app_name_display()}' (activée)"
                    )
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  Configuration existe déjà pour '{config.get_app_name_display()}' "
                        f"(statut: {'activée' if config.is_enabled else 'maintenance'})"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Initialisation terminée : {created_count} créées, {updated_count} existantes"
            )
        )
