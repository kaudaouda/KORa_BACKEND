from django.core.management.base import BaseCommand
from parametre.models import Versions


class Command(BaseCommand):
    help = 'Seed les types de tableau de bord (Tableau Initial, Amendement 1, Amendement 2)'

    def handle(self, *args, **options):
        types_tableau = [
            {
                'code': 'INITIAL',
                'nom': 'Tableau Initial',
                'description': 'Tableau de bord de référence pour une année et un processus',
                'is_active': True,
            },
            {
                'code': 'AMENDEMENT_1',
                'nom': 'Amendement 1',
                'description': 'Premier amendement du tableau initial',
                'is_active': True,
            },
            {
                'code': 'AMENDEMENT_2',
                'nom': 'Amendement 2',
                'description': 'Deuxième amendement du tableau initial',
                'is_active': True,
            },
        ]

        total_created = 0
        total_updated = 0

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed des types de tableau...'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

        for data in types_tableau:
            version, created = Versions.objects.get_or_create(
                code=data['code'],
                defaults=data,
            )

            if created:
                total_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  + Cree: {version.nom} ({version.code})')
                )
            else:
                updated = False
                for field, value in data.items():
                    if getattr(version, field) != value:
                        setattr(version, field, value)
                        updated = True
                if updated:
                    version.save()
                    total_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ~ Mis a jour: {version.nom} ({version.code})')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'  o Deja existant: {version.nom} ({version.code})')
                    )

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS(f'Resume:'))
        self.stdout.write(self.style.SUCCESS(f'  - Types crees: {total_created}'))
        self.stdout.write(self.style.SUCCESS(f'  - Types mis a jour: {total_updated}'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))
