"""
Commande de management pour créer les RolePermissionMapping du rôle superviseur_smi.

Ce rôle est conçu pour être attribué en mode global (UserProcessusRole.is_global=True),
ce qui lui permet de couvrir TOUS les processus sans assignation individuelle.

Droits couverts (sur toutes les apps et tous les processus) :
  - Lecture totale           → toutes les actions read_*
  - Édition des tableaux     → toutes les actions update_tableau* (dashboard)
  - Édition des processus    → toutes les actions update_* (hors tableau)
  - Suppression totale       → toutes les actions delete_*
  - Validation/Dévalidation  → toutes les actions validate_* et unvalidate_*
  - Création                 → toutes les actions create_*

Priorité : 15 — plus haute que responsable_processus (12), validateur (10) et admin (8).
Cela garantit que le superviseur_smi n'est jamais bloqué par un refus venant d'un rôle inférieur.

Security by Design :
  - Ce seed ne crée PAS de UserProcessusRole. Il configure uniquement les mappings de rôle.
  - L'attribution réelle à un utilisateur (avec is_global=True) se fait exclusivement
    depuis l'interface d'administration Django, par un super admin.
  - Le rôle superviseur_smi NE court-circuite PAS le système de permissions :
    il passe par le même PermissionService que tous les autres rôles.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from permissions.models import PermissionAction, RolePermissionMapping
from parametre.models import Role


SUPERVISEUR_SMI_PRIORITY = 15  # Au-dessus de responsable_processus=12, validateur=10, admin=8


class Command(BaseCommand):
    help = (
        'Crée les RolePermissionMapping pour le rôle superviseur_smi '
        'sur toutes les PermissionAction existantes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans rien écrire en base.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('[SEED] SUPERVISEUR SMI — Permissions'))
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Aucune écriture en base.'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

        # 1. Récupérer le rôle superviseur_smi
        role = Role.objects.filter(code='superviseur_smi', is_active=True).first()
        if not role:
            self.stdout.write(
                self.style.ERROR(
                    '[ERROR] Le rôle "superviseur_smi" est introuvable ou inactif.\n'
                    '        Exécutez d\'abord : python manage.py seed_roles'
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'[OK] Rôle trouvé : {role.code} — {role.nom}\n')
        )

        # 2. Récupérer toutes les PermissionAction actives (toutes apps confondues)
        all_actions = list(PermissionAction.objects.filter(is_active=True).order_by('app_name', 'code'))

        if not all_actions:
            self.stdout.write(
                self.style.WARNING(
                    '[WARNING] Aucune PermissionAction trouvée.\n'
                    '          Exécutez d\'abord les seeds de permissions des applications :\n'
                    '          python manage.py seed_permissions\n'
                    '          python manage.py seed_activite_periodique_permissions'
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'[INFO] {len(all_actions)} action(s) trouvée(s) à mapper.\n')
        )

        # 3. Créer ou mettre à jour les mappings
        total_created = 0
        total_updated = 0
        total_skipped = 0

        with transaction.atomic():
            current_app = None
            for action in all_actions:
                # Séparateur visuel par application
                if action.app_name != current_app:
                    current_app = action.app_name
                    self.stdout.write(
                        self.style.SUCCESS(f'\n  [APP] {current_app.upper()}')
                    )

                if dry_run:
                    self.stdout.write(
                        f'    [DRY] superviseur_smi → {action.code} (granted=True, priority={SUPERVISEUR_SMI_PRIORITY})'
                    )
                    total_skipped += 1
                    continue

                mapping, created = RolePermissionMapping.objects.update_or_create(
                    role=role,
                    permission_action=action,
                    defaults={
                        'granted': True,
                        'conditions': None,   # Aucune restriction contextuelle pour le superviseur
                        'priority': SUPERVISEUR_SMI_PRIORITY,
                        'is_active': True,
                    },
                )

                if created:
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'    [OK]     superviseur_smi → {action.code}')
                    )
                else:
                    total_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'    [UPDATE] superviseur_smi → {action.code} (mis à jour)')
                    )

        # 4. Résumé
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY-RUN] {total_skipped} mapping(s) seraient créés/mis à jour.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] Mappings créés   : {total_created}\n'
                    f'[OK] Mappings mis à j.: {total_updated}\n'
                    f'[OK] Total traité     : {total_created + total_updated}'
                )
            )
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
