from django.core.management.base import BaseCommand
from parametre.models import TypeDocument


class Command(BaseCommand):
    help = 'Crée les types de documents par défaut'

    def handle(self, *args, **options):
        # Les types de documents à créer
        types_data = [
            {
                'code': 'REG',
                'nom': 'Règlements',
                'description': 'Documents réglementaires et normatifs'
            },
            {
                'code': 'PROC',
                'nom': 'Procédures',
                'description': 'Procédures opérationnelles et guides de procédures'
            },
            {
                'code': 'POL',
                'nom': 'Politiques',
                'description': 'Politiques organisationnelles et directives'
            },
            {
                'code': 'MAN',
                'nom': 'Manuels',
                'description': 'Manuels d\'utilisation et guides techniques'
            },
            {
                'code': 'FORM',
                'nom': 'Formulaires',
                'description': 'Formulaires et modèles de documents'
            },
            {
                'code': 'RAPP',
                'nom': 'Rapports',
                'description': 'Rapports d\'activité et rapports d\'audit'
            },
            {
                'code': 'AUT',
                'nom': 'Autres',
                'description': 'Autres types de documents'
            },
        ]

        total_created = 0
        total_updated = 0

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('Création des types de documents...'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

        for type_data in types_data:
            type_doc, created = TypeDocument.objects.get_or_create(
                code=type_data['code'],
                defaults={
                    'nom': type_data['nom'],
                    'description': type_data['description'],
                    'is_active': True
                }
            )

            if created:
                total_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Type de document créé: {type_doc.nom} ({type_doc.code})')
                )
            else:
                # Mettre à jour si le type existe déjà mais n'est pas actif
                if not type_doc.is_active:
                    type_doc.is_active = True
                    type_doc.nom = type_data['nom']
                    type_doc.description = type_data['description']
                    type_doc.save()
                    total_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Type de document réactivé: {type_doc.nom} ({type_doc.code})')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'○ Type de document déjà existant: {type_doc.nom} ({type_doc.code})')
                    )

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS(f'Résumé:'))
        self.stdout.write(self.style.SUCCESS(f'  - Types créés: {total_created}'))
        self.stdout.write(self.style.SUCCESS(f'  - Types réactivés: {total_updated}'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

