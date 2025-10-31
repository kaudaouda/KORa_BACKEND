"""
Commande Django pour initialiser les années et types de tableaux PAC
Usage: python manage.py init_annee_typetableaupac
"""

from django.core.management.base import BaseCommand
from parametre.models import Annee, TypeTableauPac
from django.utils import timezone


class Command(BaseCommand):
    help = 'Initialise les années et types de tableaux PAC'

    def handle(self, *args, **options):
        self.stdout.write('Initialisation des années...')
        
        # Créer les années de 2020 à 2030
        for year in range(2020, 2031):
            Annee.objects.get_or_create(
                annee=year,
                defaults={
                    'is_active': True
                }
            )
        
        self.stdout.write(self.style.SUCCESS('✓ Années créées avec succès'))
        
        # Créer les types de tableaux PAC
        self.stdout.write('Initialisation des types de tableaux PAC...')
        
        types_tableaux = [
            {
                'code': 'INITIAL',
                'nom': 'Révision initiale',
                'description': 'Plan d\'action initiale de conformité'
            },
            {
                'code': 'REVISION_01',
                'nom': 'Révision 01',
                'description': 'Première révision du plan d\'action'
            },
            {
                'code': 'REVISION_02',
                'nom': 'Révision 02',
                'description': 'Deuxième révision du plan d\'action'
            }
        ]
        
        for type_data in types_tableaux:
            TypeTableauPac.objects.get_or_create(
                code=type_data['code'],
                defaults={
                    'nom': type_data['nom'],
                    'description': type_data['description'],
                    'is_active': True
                }
            )
        
        self.stdout.write(self.style.SUCCESS('✓ Types de tableaux PAC créés avec succès'))
        self.stdout.write(self.style.SUCCESS('\n✅ Initialisation terminée avec succès!'))

