from django.core.management.base import BaseCommand
from parametre.models import Role, UserProcessusRole


class Command(BaseCommand):
    help = 'Crée les 5 rôles : Responsable de processus, Contributeur, Validateur, Lecteur, Admin (supprime les anciens)'

    def handle(self, *args, **options):
        # Supprimer les anciens rôles
        old_role_codes = ['ecrire', 'lire', 'supprimer', 'valider']
        
        self.stdout.write(self.style.WARNING(f'\n{"="*60}'))
        self.stdout.write(self.style.WARNING('🗑️  Suppression des anciens rôles...'))
        self.stdout.write(self.style.WARNING(f'{"="*60}\n'))
        
        total_deleted = 0
        for old_code in old_role_codes:
            try:
                old_role = Role.objects.get(code=old_code)
                # Compter les UserProcessusRole qui seront supprimés (CASCADE)
                user_roles_count = UserProcessusRole.objects.filter(role=old_role).count()
                if user_roles_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  Suppression du rôle "{old_code}" '
                            f'(et {user_roles_count} UserProcessusRole associés)'
                        )
                    )
                old_role.delete()
                total_deleted += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Supprimé: {old_code}')
                )
            except Role.DoesNotExist:
                self.stdout.write(
                    self.style.SUCCESS(f'  → Déjà supprimé: {old_code}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ {total_deleted} ancien(s) rôle(s) supprimé(s)\n')
        )

        # Les 5 rôles à créer
        roles_data = [
            {
                'code': 'responsable_processus',
                'nom': 'Responsable de processus',
                'description': 'Rôle responsable d\'un processus avec tous les droits sur ce processus'
            },
            {
                'code': 'contributeur',
                'nom': 'Contributeur',
                'description': 'Rôle permettant d\'écrire, créer et modifier des éléments (équivalent à "écrire")'
            },
            {
                'code': 'validateur',
                'nom': 'Validateur',
                'description': 'Rôle permettant de valider des éléments et d\'avoir tous les droits'
            },
            {
                'code': 'lecteur',
                'nom': 'Lecteur',
                'description': 'Rôle permettant de lire et consulter des éléments (équivalent à "lire")'
            },
            {
                'code': 'admin',
                'nom': 'Admin',
                'description': 'Rôle administrateur avec tous les droits (peut supprimer, valider, etc.)'
            },
        ]

        total_created = 0
        total_updated = 0

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('✨ Création des nouveaux rôles...'))
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
                f'📊 Résumé:\n'
                f'  - Anciens rôles supprimés: {total_deleted}\n'
                f'  - Nouveaux rôles créés: {total_created}\n'
                f'  - Nouveaux rôles mis à jour: {total_updated}\n'
                f'  - Total nouveaux rôles: {len(roles_data)}\n'
                f'{"="*60}\n'
            )
        )

