"""
Commande Django pour créer les PermissionAction et RolePermissionMapping
pour toutes les applications (cdr, dashboard, pac)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from permissions.models import PermissionAction, RolePermissionMapping
from parametre.models import Role
from .pac_permissions import get_pac_actions
from .dashboard_permissions import get_dashboard_actions


class Command(BaseCommand):
    help = 'Crée les PermissionAction et RolePermissionMapping pour les apps cdr, dashboard, pac'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            choices=['cdr', 'dashboard', 'pac', 'all'],
            default='all',
            help='Application spécifique à seed (cdr, dashboard, pac, ou all)'
        )
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
        app_filter = options['app']
        clear_existing = options['clear']

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[SEED] SEEDING PERMISSIONS - Phase 3'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        # Supprimer les actions existantes si demandé
        if clear_existing:
            self.stdout.write(self.style.WARNING('[WARNING] Suppression des PermissionAction existantes...'))
            deleted_count = PermissionAction.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f'[OK] {deleted_count} PermissionAction supprimees\n'))

        # Définir les actions pour chaque application
        cdr_actions = self._get_cdr_actions()
        dashboard_actions = get_dashboard_actions()
        pac_actions = get_pac_actions()
        
        # Ajouter automatiquement responsable_processus à tous les mappings
        cdr_actions = self._add_responsable_processus_to_mappings(cdr_actions)
        dashboard_actions = self._add_responsable_processus_to_mappings(dashboard_actions)
        pac_actions = self._add_responsable_processus_to_mappings(pac_actions)
        
        apps_actions = {
            'cdr': cdr_actions,
            'dashboard': dashboard_actions,
            'pac': pac_actions,
        }

        # Filtrer selon l'option --app
        if app_filter != 'all':
            apps_actions = {app_filter: apps_actions[app_filter]}

        # Step 3.1, 3.2, 3.3 : Créer les PermissionAction
        total_actions_created = 0
        total_actions_updated = 0

        for app_name, actions in apps_actions.items():
            self.stdout.write(self.style.SUCCESS(f'\n[APP] Application: {app_name.upper()}'))
            self.stdout.write(self.style.SUCCESS(f'{"-"*80}'))

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
                        self.style.SUCCESS(f'  [OK] Cree: {action.code} - {action.nom}')
                    )
                else:
                    total_actions_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'  [UPDATE] Mis a jour: {action.code} - {action.nom}')
                    )

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Actions creees: {total_actions_created} | '
                f'Mis a jour: {total_actions_updated} | '
                f'Total: {total_actions_created + total_actions_updated}'
            )
        )

        # Step 3.4 : Créer les RolePermissionMapping
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[LINK] CREATION DES MAPPINGS ROLE -> PERMISSION'))
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
                    f'[ERROR] Roles manquants: {", ".join(missing_roles)}\n'
                    f'   Executez d\'abord: python manage.py seed_roles'
                )
            )
            return

        # Créer les mappings pour chaque app
        for app_name, actions in apps_actions.items():
            self.stdout.write(self.style.SUCCESS(f'\n[APP] Application: {app_name.upper()}'))
            self.stdout.write(self.style.SUCCESS(f'{"-"*80}'))

            for action_data in actions:
                action = PermissionAction.objects.get(app_name=app_name, code=action_data['code'])
                mappings = action_data.get('role_mappings', {})

                for role_code, mapping_config in mappings.items():
                    role = roles.get(role_code)
                    if not role:
                        self.stdout.write(
                            self.style.WARNING(f'  [WARNING] Role "{role_code}" non trouve, ignore')
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
                                f'({"Accorde" if mapping.granted else "Refuse"})'
                            )
                        )
                    else:
                        total_mappings_updated += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'  [UPDATE] [{role.code}] -> {action.code} (mis a jour)'
                            )
                        )

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Mappings crees: {total_mappings_created} | '
                f'Mis a jour: {total_mappings_updated} | '
                f'Total: {total_mappings_created + total_mappings_updated}'
            )
        )
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}\n'))

    def _get_cdr_actions(self):
        """Définit les actions pour l'application CDR"""
        return [
            {
                'code': 'create_cdr',
                'nom': 'Créer une Cartographie des Risques',
                'description': 'Permet de créer un nouveau CDR',
                'category': 'main',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': False, 'priority': 5},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_cdr',
                'nom': 'Modifier une Cartographie des Risques',
                'description': 'Permet de modifier un CDR existant',
                'category': 'main',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                    'lecteur': {'granted': False, 'priority': 0},
                }
            },
            {
                'code': 'delete_cdr',
                'nom': 'Supprimer une Cartographie des Risques',
                'description': 'Permet de supprimer un CDR',
                'category': 'main',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'admin': {'granted': True, 'priority': 8},
                    'contributeur': {'granted': False, 'priority': 0},
                    'lecteur': {'granted': False, 'priority': 0},
                }
            },
            {
                'code': 'validate_cdr',
                'nom': 'Valider une Cartographie des Risques',
                'description': 'Permet de valider un CDR pour permettre la saisie des suivis',
                'category': 'main',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': False, 'priority': 0},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},

                }
            },
            {
                'code': 'read_cdr',
                'nom': 'Lire une Cartographie des Risques',
                'description': 'Permet de consulter un CDR',
                'category': 'main',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5},
                    'lecteur': {'granted': True, 'priority': 5},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'create_detail_cdr',
                'nom': 'Créer un détail CDR',
                'description': 'Permet de créer un détail dans un CDR',
                'category': 'details',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_detail_cdr',
                'nom': 'Modifier un détail CDR',
                'description': 'Permet de modifier un détail CDR',
                'category': 'details',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'delete_detail_cdr',
                'nom': 'Supprimer un détail CDR',
                'description': 'Permet de supprimer un détail CDR',
                'category': 'details',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'admin': {'granted': True, 'priority': 8},
                    'contributeur': {'granted': False, 'priority': 0},
                    'lecteur': {'granted': False, 'priority': 0},
                }
            },
            {
                'code': 'create_evaluation_risque',
                'nom': 'Créer une évaluation de risque',
                'description': 'Permet de créer une évaluation de risque pour un détail CDR',
                'category': 'evaluation',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_evaluation_risque',
                'nom': 'Modifier une évaluation de risque',
                'description': 'Permet de modifier une évaluation de risque',
                'category': 'evaluation',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'delete_evaluation_risque',
                'nom': 'Supprimer une évaluation de risque',
                'description': 'Permet de supprimer une évaluation de risque',
                'category': 'evaluation',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'admin': {'granted': True, 'priority': 8},
                    'contributeur': {'granted': False, 'priority': 0},
                    'lecteur': {'granted': False, 'priority': 0},
                }
            },
            {
                'code': 'create_plan_action',
                'nom': 'Créer un plan d\'action',
                'description': 'Permet de créer un plan d\'action pour un détail CDR',
                'category': 'plans_action',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            
            {
                'code': 'create_suivi_action',
                'nom': 'Créer un suivi d\'action',
                'description': 'Permet de créer un suivi d\'action pour un plan d\'action',
                'category': 'suivis',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_suivi_action',
                'nom': 'Modifier un suivi d\'action',
                'description': 'Permet de modifier un suivi d\'action',
                'category': 'suivis',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                    'lecteur': {'granted': False, 'priority': 0},
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'delete_suivi_action',
                'nom': 'Supprimer un suivi d\'action',
                'description': 'Permet de supprimer un suivi d\'action',
                'category': 'suivis',
                'role_mappings': {
                    'validateur': {'granted': True, 'priority': 10},
                    'admin': {'granted': True, 'priority': 8},
                    'contributeur': {'granted': False, 'priority': 0},
                    'lecteur': {'granted': False, 'priority': 0},
                }
            },
        ]


