from django.core.management.base import BaseCommand
from parametre.models import Processus, Role, UserProcessusRole
import re


class Command(BaseCommand):
    help = 'Crée automatiquement les rôles (écrire, lire, supprimer, valider) pour chaque processus'

    def get_short_code(self, processus):
        """
        Extrait un code court du nom du processus en utilisant le numéro du processus pour garantir l'unicité
        Ex: "PRS-DIR-001" -> "prs-dir-001"
            "PRS-SD-002" -> "prs-sd-002"
        """
        # Utiliser le numéro du processus pour garantir l'unicité
        numero = processus.numero_processus.lower().replace('prs-', '').replace('-', '')
        
        return f"prs-{numero}"

    def handle(self, *args, **options):
        # Les 4 types de rôles à créer pour chaque processus
        role_types = [
            ('ecrire', 'écrire'),
            ('lire', 'lire'),
            ('supprimer', 'supprimer'),
            ('valider', 'valider'),
        ]

        # Récupérer tous les processus actifs
        processus_list = Processus.objects.filter(is_active=True)

        total_created = 0
        total_deleted = 0

        self.stdout.write(self.style.SUCCESS(f'\nTrouvé {processus_list.count()} processus actifs\n'))

        # Étape 1: Supprimer tous les anciens rôles qui commencent par "prs-"
        self.stdout.write(self.style.WARNING(f'\n{"="*60}'))
        self.stdout.write(self.style.WARNING('Suppression de tous les anciens rôles...'))
        self.stdout.write(self.style.WARNING(f'{"="*60}\n'))
        
        # Récupérer tous les rôles qui commencent par "prs-"
        all_prs_roles = Role.objects.filter(code__startswith='prs-')
        count_before_delete = all_prs_roles.count()
        
        # Compter les UserProcessusRole qui seront supprimés (CASCADE)
        user_roles_count = UserProcessusRole.objects.filter(
            role__code__startswith='prs-'
        ).count()
        
        if user_roles_count > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ {user_roles_count} attributions de rôles utilisateurs seront également supprimées (CASCADE)\n')
            )
        
        # Supprimer tous les rôles "prs-" (les UserProcessusRole seront supprimés automatiquement via CASCADE)
        deleted_count, deleted_details = all_prs_roles.delete()
        total_deleted = deleted_count
        
        self.stdout.write(
            self.style.ERROR(f'  ✗ {total_deleted} rôles supprimés\n')
        )

        # Étape 2: Créer uniquement les 4 nouveaux rôles pour chaque processus
        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('Création des nouveaux rôles...'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

        for processus in processus_list:
            self.stdout.write(f'\nProcessus: {processus.numero_processus} - {processus.nom}')

            # Obtenir le code court (ex: "prs-si" pour "DAAF - SDSI")
            processus_prefix = self.get_short_code(processus)

            for role_code_suffix, role_nom_suffix in role_types:
                # Créer le code et le nom du rôle
                code = f"{processus_prefix}-{role_code_suffix}"
                nom = f"{processus_prefix} {role_nom_suffix}"

                # Créer le nouveau rôle (get_or_create pour éviter les erreurs si le rôle existe déjà)
                role, created = Role.objects.get_or_create(
                    code=code,
                    defaults={
                        'nom': nom,
                        'description': f"Rôle {role_nom_suffix} pour le processus {processus.nom}",
                        'is_active': True
                    }
                )

                if created:
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Créé: {role.code} - {role.nom}')
                    )
                else:
                    # Mettre à jour le rôle existant
                    role.nom = nom
                    role.description = f"Rôle {role_nom_suffix} pour le processus {processus.nom}"
                    role.is_active = True
                    role.save()
                    total_created += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ↻ Mis à jour: {role.code} - {role.nom}')
                    )

        # Résumé
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}\n'
                f'Résumé:\n'
                f'  - Processus traités: {processus_list.count()}\n'
                f'  - Anciens rôles supprimés: {total_deleted}\n'
                f'  - Nouveaux rôles créés: {total_created}\n'
                f'  - Total rôles actifs: {total_created}\n'
                f'{"="*60}\n'
            )
        )
