from django.core.management.base import BaseCommand
from parametre.models import Role, UserProcessusRole


class Command(BaseCommand):
    help = 'Crée les 5 rôles métier ANAC : Responsable de processus, Pilote de processus, Co-pilote de processus, Admin, Superviseur SMI'

    def handle(self, *args, **options):
        old_role_codes = [
            'ecrire', 'lire', 'supprimer', 'valider',
            'responsable_processus', 'contributeur', 'validateur', 'lecteur',
        ]

        self.stdout.write(self.style.WARNING(f'\n{"="*60}'))
        self.stdout.write(self.style.WARNING('Suppression des anciens roles...'))
        self.stdout.write(self.style.WARNING(f'{"="*60}\n'))

        total_deleted = 0
        for old_code in old_role_codes:
            try:
                old_role = Role.objects.get(code=old_code)
                user_roles_count = UserProcessusRole.objects.filter(role=old_role).count()
                if user_roles_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Suppression du role "{old_code}" '
                            f'(et {user_roles_count} UserProcessusRole associes)'
                        )
                    )
                old_role.delete()
                total_deleted += 1
                self.stdout.write(self.style.SUCCESS(f'  Supprime: {old_code}'))
            except Role.DoesNotExist:
                self.stdout.write(self.style.SUCCESS(f'  Deja supprime: {old_code}'))

        self.stdout.write(self.style.SUCCESS(f'\n{total_deleted} ancien(s) role(s) supprime(s)\n'))

        roles_data = [
            {
                'code': 'RESPONSABLE DE PROCESSUS',
                'nom': 'Responsable de processus',
                'description': (
                    'Responsable d\'un processus : lecture, modification et suppression '
                    'des sous-elements (sans creation ni validation des entites principales)'
                ),
            },
            {
                'code': 'PILOTE DE PROCESSUS',
                'nom': 'Pilote de processus',
                'description': (
                    'Pilote d\'un processus : lecture et modification partielle '
                    'des sous-elements, sans suppression globale ni acces aux elements structures'
                ),
            },
            {
                'code': 'CO-PILOTE DE APROCESSUS',
                'nom': 'Co-pilote de processus',
                'description': 'Co-pilote d\'un processus : lecture seule sur toutes les applications',
            },
            {
                'code': 'admin',
                'nom': 'Admin',
                'description': 'Role administrateur avec tous les droits (creation, suppression, validation, etc.)',
            },
            {
                'code': 'superviseur_smi',
                'nom': 'Superviseur SMI',
                'description': (
                    'Role de supervision transverse du Systeme de Management Integre. '
                    'Peut etre attribue en mode global (is_global=True) pour couvrir tous les processus '
                    'sans assignation individuelle. Droits complets sur toutes les applications.'
                ),
            },
        ]

        total_created = 0
        total_updated = 0

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('Creation des nouveaux roles...'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'nom': role_data['nom'],
                    'description': role_data['description'],
                    'is_active': True,
                }
            )

            if created:
                total_created += 1
                self.stdout.write(self.style.SUCCESS(f'  Cree: {role.code} - {role.nom}'))
            else:
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
                    self.stdout.write(self.style.WARNING(f'  Mis a jour: {role.code} - {role.nom}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'  Deja a jour: {role.code} - {role.nom}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'Resume:\n'
                f'  - Anciens roles supprimes : {total_deleted}\n'
                f'  - Nouveaux roles crees    : {total_created}\n'
                f'  - Nouveaux roles mis a j. : {total_updated}\n'
                f'  - Total roles actifs      : {len(roles_data)}\n'
                f'{"="*60}\n'
            )
        )
