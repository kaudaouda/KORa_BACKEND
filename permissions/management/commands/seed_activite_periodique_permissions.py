"""
Commande de management pour créer les permissions et mappings de rôles pour l'application Activité Périodique
Similaire à ce qui existe pour PAC, CDR et Dashboard
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from permissions.models import PermissionAction, RolePermissionMapping
from parametre.models import Role


class Command(BaseCommand):
    help = 'Crée les actions de permissions et les mappings de rôles pour l\'application Activité Périodique'

    def handle(self, *args, **options):
        app_name = 'activite_periodique'
        
        # Définir toutes les actions de permissions pour Activité Périodique
        permission_actions = [
            # Actions principales
            {
                'code': 'create_activite_periodique',
                'nom': 'Créer une Activité Périodique',
                'description': 'Permission de créer une nouvelle Activité Périodique',
                'category': 'main'
            },
            {
                'code': 'update_activite_periodique',
                'nom': 'Modifier une Activité Périodique',
                'description': 'Permission de modifier une Activité Périodique existante',
                'category': 'main'
            },
            {
                'code': 'delete_activite_periodique',
                'nom': 'Supprimer une Activité Périodique',
                'description': 'Permission de supprimer une Activité Périodique',
                'category': 'main'
            },
            {
                'code': 'validate_activite_periodique',
                'nom': 'Valider une Activité Périodique',
                'description': 'Permission de valider une Activité Périodique',
                'category': 'main'
            },
            {
                'code': 'read_activite_periodique',
                'nom': 'Lire une Activité Périodique',
                'description': 'Permission de lire et consulter une Activité Périodique',
                'category': 'main'
            },
            {
                'code': 'create_amendement_activite_periodique',
                'nom': 'Créer un amendement d\'Activité Périodique',
                'description': 'Permission de créer un amendement pour une Activité Périodique',
                'category': 'main'
            },
            # Actions détails
            {
                'code': 'create_detail_activite_periodique',
                'nom': 'Créer un détail d\'Activité Périodique',
                'description': 'Permission de créer un détail pour une Activité Périodique',
                'category': 'details'
            },
            {
                'code': 'update_detail_activite_periodique',
                'nom': 'Modifier un détail d\'Activité Périodique',
                'description': 'Permission de modifier un détail d\'Activité Périodique',
                'category': 'details'
            },
            {
                'code': 'delete_detail_activite_periodique',
                'nom': 'Supprimer un détail d\'Activité Périodique',
                'description': 'Permission de supprimer un détail d\'Activité Périodique',
                'category': 'details'
            },
            # Actions suivis
            {
                'code': 'create_suivi_activite_periodique',
                'nom': 'Créer un suivi d\'Activité Périodique',
                'description': 'Permission de créer un suivi pour une Activité Périodique',
                'category': 'suivis'
            },
            {
                'code': 'update_suivi_activite_periodique',
                'nom': 'Modifier un suivi d\'Activité Périodique',
                'description': 'Permission de modifier un suivi d\'Activité Périodique',
                'category': 'suivis'
            },
            {
                'code': 'delete_suivi_activite_periodique',
                'nom': 'Supprimer un suivi d\'Activité Périodique',
                'description': 'Permission de supprimer un suivi d\'Activité Périodique',
                'category': 'suivis'
            },
        ]

        # Définir les mappings de rôles (qui peut faire quoi)
        # Structure: {role_code: [list of action codes]}
        role_permissions = {
            'admin': [
                # Admin peut tout faire
                'create_activite_periodique',
                'update_activite_periodique',
                'delete_activite_periodique',
                'validate_activite_periodique',
                'read_activite_periodique',
                'create_amendement_activite_periodique',
                'create_detail_activite_periodique',
                'update_detail_activite_periodique',
                'delete_detail_activite_periodique',
                'create_suivi_activite_periodique',
                'update_suivi_activite_periodique',
                'delete_suivi_activite_periodique',
            ],
            'responsable_processus': [
                # Responsable peut tout faire sur son processus
                'create_activite_periodique',
                'update_activite_periodique',
                'delete_activite_periodique',
                'validate_activite_periodique',
                'read_activite_periodique',
                'create_amendement_activite_periodique',
                'create_detail_activite_periodique',
                'update_detail_activite_periodique',
                'delete_detail_activite_periodique',
                'create_suivi_activite_periodique',
                'update_suivi_activite_periodique',
                'delete_suivi_activite_periodique',
            ],
            'validateur': [
                # Validateur peut lire, créer, modifier et valider
                'create_activite_periodique',
                'update_activite_periodique',
                'validate_activite_periodique',
                'read_activite_periodique',
                'create_amendement_activite_periodique',
                'create_detail_activite_periodique',
                'update_detail_activite_periodique',
                'create_suivi_activite_periodique',
                'update_suivi_activite_periodique',
            ],
            'contributeur': [
                # Contributeur peut créer, modifier et lire (mais pas valider ni supprimer)
                'create_activite_periodique',
                'update_activite_periodique',
                'read_activite_periodique',
                'create_amendement_activite_periodique',
                'create_detail_activite_periodique',
                'update_detail_activite_periodique',
                'create_suivi_activite_periodique',
                'update_suivi_activite_periodique',
            ],
            'lecteur': [
                # Lecteur peut seulement lire
                'read_activite_periodique',
            ],
        }

        with transaction.atomic():
            # Étape 1: Créer les actions de permissions
            self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
            self.stdout.write(self.style.SUCCESS('✨ Création des actions de permissions...'))
            self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

            created_actions = 0
            updated_actions = 0

            for action_data in permission_actions:
                action, created = PermissionAction.objects.get_or_create(
                    app_name=app_name,
                    code=action_data['code'],
                    defaults={
                        'nom': action_data['nom'],
                        'description': action_data.get('description', ''),
                        'category': action_data.get('category', 'main'),
                        'is_active': True
                    }
                )

                if created:
                    created_actions += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Créé: {action.code} - {action.nom}')
                    )
                else:
                    # Mettre à jour si nécessaire
                    updated = False
                    if action.nom != action_data['nom']:
                        action.nom = action_data['nom']
                        updated = True
                    if action.description != action_data.get('description', ''):
                        action.description = action_data.get('description', '')
                        updated = True
                    if action.category != action_data.get('category', 'main'):
                        action.category = action_data.get('category', 'main')
                        updated = True
                    if not action.is_active:
                        action.is_active = True
                        updated = True

                    if updated:
                        action.save()
                        updated_actions += 1
                        self.stdout.write(
                            self.style.WARNING(f'  ↻ Mis à jour: {action.code} - {action.nom}')
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'  → Déjà à jour: {action.code} - {action.nom}')
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Actions créées: {created_actions}, Actions mises à jour: {updated_actions}\n'
                )
            )

            # Étape 2: Créer les mappings de rôles
            self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
            self.stdout.write(self.style.SUCCESS('🔗 Création des mappings de rôles...'))
            self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

            created_mappings = 0
            updated_mappings = 0
            skipped_mappings = 0

            for role_code, allowed_actions in role_permissions.items():
                try:
                    role = Role.objects.get(code=role_code, is_active=True)
                    self.stdout.write(f'\n📋 Rôle: {role.nom} ({role.code})')

                    # Récupérer toutes les actions de permissions pour cette app
                    all_actions = PermissionAction.objects.filter(
                        app_name=app_name,
                        is_active=True
                    )

                    for action in all_actions:
                        should_grant = action.code in allowed_actions
                        
                        mapping, created = RolePermissionMapping.objects.get_or_create(
                            role=role,
                            permission_action=action,
                            defaults={
                                'granted': should_grant,
                                'priority': 0,
                                'is_active': True,
                                'conditions': {}
                            }
                        )

                        if created:
                            created_mappings += 1
                            status = '✓ Accordé' if should_grant else '✗ Refusé'
                            self.stdout.write(
                                self.style.SUCCESS(f'  {status}: {action.code}')
                            )
                        else:
                            # Mettre à jour si nécessaire
                            updated = False
                            if mapping.granted != should_grant:
                                mapping.granted = should_grant
                                updated = True
                            if not mapping.is_active:
                                mapping.is_active = True
                                updated = True

                            if updated:
                                mapping.save()
                                updated_mappings += 1
                                status = '✓ Accordé' if should_grant else '✗ Refusé'
                                self.stdout.write(
                                    self.style.WARNING(f'  ↻ {status}: {action.code}')
                                )
                            else:
                                skipped_mappings += 1

                except Role.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'  ⚠️  Rôle "{role_code}" non trouvé - ignoré')
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Mappings créés: {created_mappings}, '
                    f'Mappings mis à jour: {updated_mappings}, '
                    f'Mappings inchangés: {skipped_mappings}\n'
                )
            )

        # Résumé final
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'📊 Résumé final:\n'
                f'  - Application: {app_name}\n'
                f'  - Actions de permissions créées/mises à jour: {created_actions + updated_actions}\n'
                f'  - Mappings de rôles créés/mis à jour: {created_mappings + updated_mappings}\n'
                f'  - Rôles configurés: {len(role_permissions)}\n'
                f'{"="*60}\n'
            )
        )
