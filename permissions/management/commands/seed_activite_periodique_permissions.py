"""
Commande de management pour créer les permissions et mappings de rôles pour l'application Activité Périodique
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from permissions.models import PermissionAction, RolePermissionMapping
from parametre.models import Role
from .activite_periodique_permissions import get_activite_periodique_actions

RP = 'RESPONSABLE DE PROCESSUS'
PP = 'PILOTE DE PROCESSUS'
CP = 'CO-PILOTE DE APROCESSUS'


class Command(BaseCommand):
    help = 'Crée les actions de permissions et les mappings de rôles pour l\'application Activité Périodique'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprime les PermissionAction existantes avant de créer les nouvelles'
        )

    def handle(self, *args, **options):
        app_name = 'activite_periodique'
        clear_existing = options.get('clear', False)

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[SEED] SEEDING PERMISSIONS - Activité Périodique'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        if clear_existing:
            self.stdout.write(self.style.WARNING('[WARNING] Suppression des PermissionAction existantes...'))
            deleted_count = PermissionAction.objects.filter(app_name=app_name).delete()[0]
            self.stdout.write(self.style.SUCCESS(f'[OK] {deleted_count} PermissionAction supprimées\n'))

        actions = get_activite_periodique_actions()

        # Étape 1 : Créer les PermissionAction
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[ACTIONS] Création des actions de permissions...'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        total_actions_created = 0
        total_actions_updated = 0

        with transaction.atomic():
            for action_data in actions:
                action, created = PermissionAction.objects.update_or_create(
                    app_name=app_name,
                    code=action_data['code'],
                    defaults={
                        'nom': action_data['nom'],
                        'description': action_data.get('description', ''),
                        'category': action_data.get('category', 'main'),
                        'is_active': True,
                    }
                )

                if created:
                    total_actions_created += 1
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Créé: {action.code} - {action.nom}'))
                else:
                    total_actions_updated += 1
                    self.stdout.write(self.style.WARNING(f'  [UPDATE] Mis à jour: {action.code} - {action.nom}'))

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Actions créées: {total_actions_created} | '
                f'Mis à jour: {total_actions_updated} | '
                f'Total: {total_actions_created + total_actions_updated}'
            )
        )

        # Étape 2 : Créer les mappings de rôles
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[LINK] Création des mappings rôle -> permission'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        total_mappings_created = 0
        total_mappings_updated = 0

        roles = {
            RP: Role.objects.filter(code=RP).first(),
            PP: Role.objects.filter(code=PP).first(),
            CP: Role.objects.filter(code=CP).first(),
            'admin': Role.objects.filter(code='admin').first(),
        }

        missing_roles = [code for code, role in roles.items() if role is None]
        if missing_roles:
            self.stdout.write(
                self.style.ERROR(
                    f'[ERROR] Rôles manquants: {", ".join(missing_roles)}\n'
                    f'   Exécutez d\'abord: python manage.py seed_roles'
                )
            )
            return

        with transaction.atomic():
            for action_data in actions:
                action = PermissionAction.objects.get(app_name=app_name, code=action_data['code'])
                mappings = action_data.get('role_mappings', {})

                for role_code, mapping_config in mappings.items():
                    role = roles.get(role_code)
                    if not role:
                        self.stdout.write(
                            self.style.WARNING(f'  [WARNING] Rôle "{role_code}" non trouvé, ignoré')
                        )
                        continue

                    mapping, created = RolePermissionMapping.objects.update_or_create(
                        role=role,
                        permission_action=action,
                        defaults={
                            'granted': mapping_config.get('granted', True),
                            'conditions': mapping_config.get('conditions'),
                            'priority': mapping_config.get('priority', 0),
                            'is_active': True,
                        }
                    )

                    if created:
                        total_mappings_created += 1
                        status = "[OK]" if mapping.granted else "[X]"
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  {status} [{role.code}] -> {action.code} '
                                f'({"Accordé" if mapping.granted else "Refusé"})'
                            )
                        )
                    else:
                        total_mappings_updated += 1
                        self.stdout.write(
                            self.style.WARNING(f'  [UPDATE] [{role.code}] -> {action.code} (mis à jour)')
                        )

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Mappings créés: {total_mappings_created} | '
                f'Mis à jour: {total_mappings_updated} | '
                f'Total: {total_mappings_created + total_mappings_updated}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*80}\n'
                f'Resume final:\n'
                f'  - Application: {app_name}\n'
                f'  - Actions créées/mises à jour: {total_actions_created + total_actions_updated}\n'
                f'  - Mappings créés/mis à jour  : {total_mappings_created + total_mappings_updated}\n'
                f'{"="*80}\n'
            )
        )
