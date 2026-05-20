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

RP = 'RESPONSABLE DE PROCESSUS'
PP = 'PILOTE DE PROCESSUS'
CP = 'CO-PILOTE DE APROCESSUS'


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

    def handle(self, *args, **options):
        app_filter = options['app']
        clear_existing = options['clear']

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[SEED] SEEDING PERMISSIONS - Phase 3'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        if clear_existing:
            self.stdout.write(self.style.WARNING('[WARNING] Suppression des PermissionAction existantes...'))
            deleted_count = PermissionAction.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f'[OK] {deleted_count} PermissionAction supprimees\n'))

        cdr_actions = self._get_cdr_actions()
        dashboard_actions = get_dashboard_actions()
        pac_actions = get_pac_actions()

        apps_actions = {
            'cdr': cdr_actions,
            'dashboard': dashboard_actions,
            'pac': pac_actions,
        }

        if app_filter != 'all':
            apps_actions = {app_filter: apps_actions[app_filter]}

        # Step 3.1-3.3 : Créer les PermissionAction
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
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Cree: {action.code} - {action.nom}'))
                else:
                    total_actions_updated += 1
                    self.stdout.write(self.style.WARNING(f'  [UPDATE] Mis a jour: {action.code} - {action.nom}'))

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
                    f'[ERROR] Roles manquants: {", ".join(missing_roles)}\n'
                    f'   Executez d\'abord: python manage.py seed_roles'
                )
            )
            return

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
                            self.style.WARNING(f'  [UPDATE] [{role.code}] -> {action.code} (mis a jour)')
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
        """Définit les actions pour l'application CDR

        Roles :
          admin                   — creation, suppression, validation, devalidation
          RESPONSABLE DE PROCESSUS — lecture + modification + suppression des sous-elements
          PILOTE DE PROCESSUS      — lecture + modification des sous-elements (unvalidate refusé)
          CO-PILOTE DE APROCESSUS  — lecture seule
        """
        return [
            # ==================== ENTITE PRINCIPALE ====================
            {
                'code': 'create_cdr',
                'nom': 'Créer une Cartographie des Risques',
                'description': 'Permet de créer un nouveau CDR',
                'category': 'main',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_cdr',
                'nom': 'Modifier une Cartographie des Risques',
                'description': 'Permet de modifier un CDR existant',
                'category': 'main',
                'role_mappings': {
                    RP: {'granted': True, 'priority': 0},
                    PP: {'granted': True, 'priority': 0},
                }
            },
            {
                'code': 'delete_cdr',
                'nom': 'Supprimer une Cartographie des Risques',
                'description': 'Permet de supprimer un CDR',
                'category': 'main',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'validate_cdr',
                'nom': 'Valider une Cartographie des Risques',
                'description': 'Permet de valider un CDR pour permettre la saisie des suivis',
                'category': 'main',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'unvalidate_cdr',
                'nom': 'Dévalider une Cartographie des Risques',
                'description': 'Permet de dévalider un CDR (retour en brouillon)',
                'category': 'main',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    PP: {'granted': False, 'priority': 0},
                }
            },
            {
                'code': 'read_cdr',
                'nom': 'Lire une Cartographie des Risques',
                'description': 'Permet de consulter un CDR',
                'category': 'main',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                    PP: {'granted': True, 'priority': 0},
                    CP: {'granted': True, 'priority': 0},
                }
            },
            # ==================== DETAILS ====================
            {
                'code': 'create_detail_cdr',
                'nom': 'Créer un détail CDR',
                'description': 'Permet de créer un détail dans un CDR',
                'category': 'details',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_detail_cdr',
                'nom': 'Modifier un détail CDR',
                'description': 'Permet de modifier un détail CDR',
                'category': 'details',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                    PP: {'granted': True, 'priority': 0},
                }
            },
            {
                'code': 'delete_detail_cdr',
                'nom': 'Supprimer un détail CDR',
                'description': 'Permet de supprimer un détail CDR',
                'category': 'details',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                }
            },
            # ==================== EVALUATIONS ====================
            {
                'code': 'create_evaluation_risque',
                'nom': 'Créer une évaluation de risque',
                'description': 'Permet de créer une évaluation de risque pour un détail CDR',
                'category': 'evaluation',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_evaluation_risque',
                'nom': 'Modifier une évaluation de risque',
                'description': 'Permet de modifier une évaluation de risque',
                'category': 'evaluation',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                    PP: {'granted': True, 'priority': 0},
                }
            },
            {
                'code': 'delete_evaluation_risque',
                'nom': 'Supprimer une évaluation de risque',
                'description': 'Permet de supprimer une évaluation de risque',
                'category': 'evaluation',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                }
            },
            # ==================== PLANS D'ACTION ====================
            {
                'code': 'create_plan_action',
                'nom': 'Créer un plan d\'action',
                'description': 'Permet de créer un plan d\'action pour un détail CDR',
                'category': 'plans_action',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_plan_action',
                'nom': 'Modifier un plan d\'action',
                'description': 'Permet de modifier un plan d\'action CDR',
                'category': 'plans_action',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                    PP: {'granted': True, 'priority': 0},
                }
            },
            {
                'code': 'delete_plan_action',
                'nom': 'Supprimer un plan d\'action',
                'description': 'Permet de supprimer un plan d\'action CDR',
                'category': 'plans_action',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                }
            },
            # ==================== SUIVIS ====================
            {
                'code': 'create_suivi_action',
                'nom': 'Créer un suivi d\'action',
                'description': 'Permet de créer un suivi d\'action pour un plan d\'action',
                'category': 'suivis',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                }
            },
            {
                'code': 'update_suivi_action',
                'nom': 'Modifier un suivi d\'action',
                'description': 'Permet de modifier un suivi d\'action',
                'category': 'suivis',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                    PP: {'granted': True, 'priority': 0},
                }
            },
            {
                'code': 'delete_suivi_action',
                'nom': 'Supprimer un suivi d\'action',
                'description': 'Permet de supprimer un suivi d\'action',
                'category': 'suivis',
                'role_mappings': {
                    'admin': {'granted': True, 'priority': 8},
                    RP: {'granted': True, 'priority': 0},
                }
            },
        ]
