from django.core.management.base import BaseCommand
from parametre.models import Annee
from datetime import datetime


class Command(BaseCommand):
    help = 'Initialise les années par défaut'

    def handle(self, *args, **options):
        # Générer les années de 2020 à l'année courante + 2
        current_year = datetime.now().year
        start_year = 2020
        end_year = current_year + 2
        
        created_count = 0
        updated_count = 0

        for year in range(start_year, end_year + 1):
            annee_data = {
                'annee': year,
                'libelle': f'Année {year}',
                'description': f'Année fiscale {year}',
                'is_active': True
            }
            
            annee, created = Annee.objects.get_or_create(
                annee=year,
                defaults=annee_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Créée: {annee.annee}')
                )
            else:
                # Mettre à jour les champs si nécessaire
                updated = False
                for field, value in annee_data.items():
                    if field != 'annee' and getattr(annee, field) != value:
                        setattr(annee, field, value)
                        updated = True
                
                if updated:
                    annee.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Mise à jour: {annee.annee}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Déjà existante: {annee.annee}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎯 Résumé: {created_count} créées, {updated_count} mises à jour'
            )
        )

