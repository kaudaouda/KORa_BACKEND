"""
Command pour initialiser les versions d'évaluation CDR par défaut
Usage: python manage.py init_versions_evaluation
"""
from django.core.management.base import BaseCommand
from parametre.models import VersionEvaluationCDR


class Command(BaseCommand):
    help = 'Initialise les versions d\'évaluation CDR par défaut (Initiale, Réévaluation 1, Réévaluation 2, etc.)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('🚀 Initialisation des versions d\'évaluation CDR...'))

        # Définir les versions par défaut
        versions_defaut = [
            {
                'nom': 'Évaluation Initiale',
                'description': 'Première évaluation des risques identifiés',
                'is_active': True
            },
            {
                'nom': 'Réévaluation 1',
                'description': 'Première réévaluation des risques après mise en place des actions correctives',
                'is_active': True
            },
            {
                'nom': 'Réévaluation 2',
                'description': 'Deuxième réévaluation des risques',
                'is_active': True
            },
            {
                'nom': 'Réévaluation 3',
                'description': 'Troisième réévaluation des risques',
                'is_active': True
            },
        ]

        created_count = 0
        updated_count = 0

        for version_data in versions_defaut:
            version, created = VersionEvaluationCDR.objects.update_or_create(
                nom=version_data['nom'],
                defaults={
                    'description': version_data['description'],
                    'is_active': version_data['is_active']
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✅ Version créée: {version.nom}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'  ℹ️  Version mise à jour: {version.nom}'))

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_LABEL('📊 Résumé:'))
        self.stdout.write(f'  • Versions créées: {created_count}')
        self.stdout.write(f'  • Versions mises à jour: {updated_count}')
        self.stdout.write(f'  • Total: {created_count + updated_count}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✨ Initialisation terminée avec succès!'))
