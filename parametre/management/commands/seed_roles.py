from django.core.management.base import BaseCommand
from parametre.models import Role


class Command(BaseCommand):
    help = 'Crée les 4 rôles généraux : écrire, lire, supprimer, valider'

    def handle(self, *args, **options):
        # Les 4 rôles généraux à créer
        roles_data = [
            {
                'code': 'ecrire',
                'nom': 'Écrire',
                'description': 'Rôle permettant d\'écrire et de créer des éléments'
            },
            {
                'code': 'lire',
                'nom': 'Lire',
                'description': 'Rôle permettant de lire et de consulter des éléments'
            },
            {
                'code': 'supprimer',
                'nom': 'Supprimer',
                'description': 'Rôle permettant de supprimer des éléments'
            },
            {
                'code': 'valider',
                'nom': 'Valider',
                'description': 'Rôle permettant de valider des éléments'
            },
        ]

        total_created = 0
        total_updated = 0

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('Création des rôles généraux...'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'nom': role_data['nom'],
                    'description': role_data['description'],
                    'is_active': True
                }
            )

            if created:
                total_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Créé: {role.code} - {role.nom}')
                )
            else:
                # Mettre à jour le rôle existant pour s'assurer qu'il est actif et a les bonnes valeurs
                updated = False
                if not role.is_active:
                    role.is_active = True
                    updated = True
                if role.nom != role_data['nom']:
                    role.nom = role_data['nom']
                    updated = True
                if role.description != role_data['description']:
                    role.description = role_data['description']
                    updated = True

                if updated:
                    role.save()
                    total_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ↻ Mis à jour: {role.code} - {role.nom}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'  → Déjà à jour: {role.code} - {role.nom}')
                    )

        # Résumé
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'Résumé:\n'
                f'  - Rôles créés: {total_created}\n'
                f'  - Rôles mis à jour: {total_updated}\n'
                f'  - Total rôles généraux: {len(roles_data)}\n'
                f'{"="*60}\n'
            )
        )

