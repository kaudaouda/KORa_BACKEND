"""
Commande de management pour créer les permissions et mappings de rôles pour l'application Activité Périodique
Similaire à ce qui existe pour PAC, CDR et Dashboard
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from permissions.models import PermissionAction, RolePermissionMapping
from parametre.models import Role
from .activite_periodique_permissions import get_activite_periodique_actions


class Command(BaseCommand):
    help = 'Crée les actions de permissions et les mappings de rôles pour l\'application Activité Périodique'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprime les PermissionAction existantes avant de créer les nouvelles'
        )

    def _add_responsable_processus_to_mappings(self, actions_list):
        """
        Ajoute automatiquement le rôle responsable_processus à tous les mappings
        Le responsable de processus a toutes les permissions avec une priorité élevée (12)
        """
        for action in actions_list:
            role_mappings = action.get('role_mappings', {})
            # Ajouter responsable_processus avec toutes les permissions accordées
            # Priorité 12 (plus élevée que validateur=10 et admin=8)
            role_mappings['responsable_processus'] = {'granted': True, 'priority': 12}
            action['role_mappings'] = role_mappings
        return actions_list

    def handle(self, *args, **options):
        app_name = 'activite_periodique'
        clear_existing = options.get('clear', False)

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[SEED] SEEDING PERMISSIONS - Activité Périodique'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        # Supprimer les actions existantes si demandé
        if clear_existing:
            self.stdout.write(self.style.WARNING('[WARNING] Suppression des PermissionAction existantes...'))
            deleted_count = PermissionAction.objects.filter(app_name=app_name).delete()[0]
            self.stdout.write(self.style.SUCCESS(f'[OK] {deleted_count} PermissionAction supprimées\n'))

        # Récupérer les actions depuis le fichier de définitions
        actions = get_activite_periodique_actions()
        
        # Ajouter automatiquement responsable_processus à tous les mappings
        actions = self._add_responsable_processus_to_mappings(actions)

        # Étape 1: Créer les actions de permissions
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
                    self.stdout.write(
                        self.style.SUCCESS(f'  [OK] Créé: {action.code} - {action.nom}')
                    )
                else:
                    total_actions_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'  [UPDATE] Mis à jour: {action.code} - {action.nom}')
                    )

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Actions créées: {total_actions_created} | '
                f'Mis à jour: {total_actions_updated} | '
                f'Total: {total_actions_created + total_actions_updated}'
            )
        )

        # Étape 2: Créer les mappings de rôles
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[LINK] Création des mappings rôle -> permission'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        total_mappings_created = 0
        total_mappings_updated = 0

        # Récupérer les rôles
        roles = {
            'responsable_processus': Role.objects.filter(code='responsable_processus').first(),
            'contributeur': Role.objects.filter(code='contributeur').first(),
            'validateur': Role.objects.filter(code='validateur').first(),
            'lecteur': Role.objects.filter(code='lecteur').first(),
            'admin': Role.objects.filter(code='admin').first(),
        }

        # Vérifier que tous les rôles existent
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
                            self.style.WARNING(
                                f'  [UPDATE] [{role.code}] -> {action.code} (mis à jour)'
                            )
                        )

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Mappings créés: {total_mappings_created} | '
                f'Mis à jour: {total_mappings_updated} | '
                f'Total: {total_mappings_created + total_mappings_updated}'
            )
        )

        # Résumé final
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*80}\n'
                f'📊 Résumé final:\n'
                f'  - Application: {app_name}\n'
                f'  - Actions de permissions créées/mises à jour: {total_actions_created + total_actions_updated}\n'
                f'  - Mappings de rôles créés/mis à jour: {total_mappings_created + total_mappings_updated}\n'
                f'  - Rôles configurés: {len([r for r in roles.values() if r is not None])}\n'
                f'{"="*80}\n'
            )
        )
