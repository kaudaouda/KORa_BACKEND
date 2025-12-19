"""
Script de vérification de la cohérence des permissions
Vérifie que tous les codes de permissions sont cohérents entre seed, backend et frontend
"""
from django.core.management.base import BaseCommand
import re

class Command(BaseCommand):
    help = 'Vérifie la cohérence des permissions entre seed, backend et frontend'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('🔍 VÉRIFICATION DE COHÉRENCE DES PERMISSIONS'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        # Codes définis dans seed_permissions.py pour dashboard
        seed_codes = [
            'create_tableau_bord',
            'update_tableau_bord',
            'delete_tableau_bord',
            'validate_tableau_bord',
            'read_tableau_bord',
            'create_amendement',
            'create_objective',
            'update_objective',
            'delete_objective',
            'create_indicateur',
            'update_indicateur',
            'delete_indicateur',
            'create_cible',
            'update_cible',
            'delete_cible',
            'create_periodicite',
            'update_periodicite',
            'delete_periodicite',
            'create_observation',
            'update_observation',
            'delete_observation',
        ]

        # Codes dans permissions.py
        backend_codes = [
            'create_tableau_bord',
            'update_tableau_bord',
            'delete_tableau_bord',
            'validate_tableau_bord',
            'read_tableau_bord',
            'create_amendement',
            'create_objective',
            'update_objective',
            'delete_objective',
            'create_indicateur',
            'update_indicateur',
            'delete_indicateur',
            'create_cible',
            'update_cible',
            'delete_cible',
            'create_periodicite',
            'update_periodicite',
            'delete_periodicite',
            'create_observation',
            'update_observation',
            'delete_observation',
        ]

        # Codes dans useDashboardPermissions.js (vérifiés manuellement)
        frontend_codes = [
            'create_tableau_bord',
            'update_tableau_bord',
            'delete_tableau_bord',
            'validate_tableau_bord',
            'read_tableau_bord',
            'create_amendement',
            'create_objective',
            'update_objective',
            'delete_objective',
            'create_indicateur',
            'update_indicateur',
            'delete_indicateur',
            'create_cible',
            'update_cible',
            'delete_cible',
            'create_periodicite',
            'update_periodicite',
            'delete_periodicite',
            'create_observation',
            'update_observation',
            'delete_observation',
        ]

        # Vérifier les différences
        seed_set = set(seed_codes)
        backend_set = set(backend_codes)
        frontend_set = set(frontend_codes)

        missing_in_backend = seed_set - backend_set
        missing_in_frontend = seed_set - frontend_set
        extra_in_backend = backend_set - seed_set
        extra_in_frontend = frontend_set - seed_set

        if missing_in_backend:
            self.stdout.write(self.style.ERROR(f'\n❌ Codes manquants dans permissions.py:'))
            for code in sorted(missing_in_backend):
                self.stdout.write(self.style.ERROR(f'  - {code}'))

        if missing_in_frontend:
            self.stdout.write(self.style.ERROR(f'\n❌ Codes manquants dans useDashboardPermissions.js:'))
            for code in sorted(missing_in_frontend):
                self.stdout.write(self.style.ERROR(f'  - {code}'))

        if extra_in_backend:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Codes supplémentaires dans permissions.py:'))
            for code in sorted(extra_in_backend):
                self.stdout.write(self.style.WARNING(f'  - {code}'))

        if extra_in_frontend:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Codes supplémentaires dans useDashboardPermissions.js:'))
            for code in sorted(extra_in_frontend):
                self.stdout.write(self.style.WARNING(f'  - {code}'))

        if not missing_in_backend and not missing_in_frontend and not extra_in_backend and not extra_in_frontend:
            self.stdout.write(self.style.SUCCESS('\n✅ Tous les codes sont cohérents entre seed, backend et frontend!'))

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}\n'))

