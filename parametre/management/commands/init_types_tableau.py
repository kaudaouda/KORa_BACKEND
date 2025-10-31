from django.core.management.base import BaseCommand
from parametre.models import Versions


class Command(BaseCommand):
    help = 'Initialise les types de tableau de bord par défaut'

    def handle(self, *args, **options):
        types_tableau = [
            {
                'code': 'INITIAL',
                'nom': 'Tableau Initial',
                'description': 'Tableau de bord de référence pour une année et un processus',
                'is_active': True
            },
            {
                'code': 'AMENDEMENT_1',
                'nom': 'Amendement 1',
                'description': 'Premier amendement du tableau initial',
                'is_active': True
            },
            {
                'code': 'AMENDEMENT_2',
                'nom': 'Amendement 2',
                'description': 'Deuxième amendement du tableau initial',
                'is_active': True
            }
        ]

        created_count = 0
        updated_count = 0

        for type_data in types_tableau:
            version, created = Versions.objects.get_or_create(
                code=type_data['code'],
                defaults=type_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Créé: {version.nom}')
                )
            else:
                # Mettre à jour les champs si nécessaire
                updated = False
                for field, value in type_data.items():
                    if getattr(version, field) != value:
                        setattr(version, field, value)
                        updated = True
                
                if updated:
                    version.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Mis à jour: {version.nom}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Déjà existant: {version.nom}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎯 Résumé: {created_count} créés, {updated_count} mis à jour'
            )
        )
