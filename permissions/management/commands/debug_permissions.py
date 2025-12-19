"""
Commande Django pour déboguer les permissions
Vérifie que les permissions sont correctement calculées
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from permissions.models import PermissionAction, RolePermissionMapping
from parametre.models import Role, UserProcessusRole, Processus
from permissions.services.permission_service import PermissionService


class Command(BaseCommand):
    help = 'Débogue les permissions pour un utilisateur'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID de l\'utilisateur à déboguer'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Nom d\'utilisateur à déboguer'
        )
        parser.add_argument(
            '--app',
            type=str,
            default='dashboard',
            help='Application à vérifier (dashboard, cdr, pac)'
        )
        parser.add_argument(
            '--processus-uuid',
            type=str,
            help='UUID du processus (optionnel)'
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        username = options.get('username')
        app_name = options.get('app', 'dashboard')
        processus_uuid = options.get('processus_uuid')

        # Récupérer l'utilisateur
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Utilisateur avec ID {user_id} non trouvé'))
                return
        elif username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Utilisateur "{username}" non trouvé'))
                return
        else:
            self.stdout.write(self.style.ERROR('❌ Vous devez spécifier --user-id ou --username'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS(f'🔍 DÉBOGAGE DES PERMISSIONS'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
        self.stdout.write(self.style.SUCCESS(f'Utilisateur: {user.username} (ID: {user.id})'))
        self.stdout.write(self.style.SUCCESS(f'Application: {app_name}\n'))

        # Vérifier si super admin
        is_super_admin = PermissionService._is_super_admin(user)
        self.stdout.write(self.style.WARNING(f'Super Admin: {"OUI" if is_super_admin else "NON"}'))
        if is_super_admin:
            self.stdout.write(self.style.WARNING('⚠️  Super admin a toutes les permissions\n'))

        # Récupérer les rôles de l'utilisateur
        user_roles_query = UserProcessusRole.objects.filter(
            user=user,
            is_active=True
        ).select_related('role', 'processus')

        if processus_uuid:
            try:
                processus = Processus.objects.get(uuid=processus_uuid)
                user_roles_query = user_roles_query.filter(processus=processus)
                self.stdout.write(self.style.SUCCESS(f'Processus: {processus.nom} (UUID: {processus_uuid})\n'))
            except Processus.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Processus avec UUID {processus_uuid} non trouvé'))
                return

        user_roles = list(user_roles_query)

        if not user_roles:
            self.stdout.write(self.style.WARNING('⚠️  Aucun rôle actif trouvé pour cet utilisateur'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n📋 Rôles de l\'utilisateur:'))
        for user_role in user_roles:
            self.stdout.write(
                self.style.SUCCESS(
                    f'  - {user_role.role.code} ({user_role.role.nom}) '
                    f'pour {user_role.processus.nom} (UUID: {user_role.processus.uuid})'
                )
            )

        # Récupérer toutes les actions pour cette app
        actions = PermissionAction.objects.filter(
            app_name=app_name,
            is_active=True
        )

        self.stdout.write(self.style.SUCCESS(f'\n📋 Actions disponibles pour {app_name}:'))
        for action in actions:
            self.stdout.write(f'  - {action.code}')

        # Pour chaque processus, vérifier les permissions
        processus_list = {str(ur.processus.uuid): ur.processus for ur in user_roles}

        for processus_uuid_str, processus in processus_list.items():
            if processus_uuid and str(processus.uuid) != processus_uuid:
                continue

            self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
            self.stdout.write(self.style.SUCCESS(f'📊 Processus: {processus.nom} (UUID: {processus_uuid_str})'))
            self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

            # Rôles de l'utilisateur pour ce processus
            roles_for_processus = [ur.role for ur in user_roles if str(ur.processus.uuid) == processus_uuid_str]

            self.stdout.write(self.style.SUCCESS(f'Rôles pour ce processus:'))
            for role in roles_for_processus:
                self.stdout.write(f'  - {role.code} ({role.nom})')

            # Pour chaque action, vérifier les mappings
            self.stdout.write(self.style.SUCCESS(f'\n🔍 Vérification des permissions:\n'))

            for action in actions:
                self.stdout.write(f'\n  Action: {action.code}')
                self.stdout.write(f'  {"-"*60}')

                # Vérifier les mappings pour chaque rôle
                found_mapping = False
                for role in roles_for_processus:
                    mappings = RolePermissionMapping.objects.filter(
                        role=role,
                        permission_action=action,
                        is_active=True
                    ).order_by('-priority')

                    if mappings.exists():
                        found_mapping = True
                        for mapping in mappings:
                            status = "✓ ACCORDÉ" if mapping.granted else "✗ REFUSÉ"
                            self.stdout.write(
                                f'    [{role.code}] → Priority: {mapping.priority} → {status}'
                            )
                    else:
                        self.stdout.write(f'    [{role.code}] → Aucun mapping trouvé')

                if not found_mapping:
                    self.stdout.write(self.style.WARNING('    ⚠️  Aucun mapping trouvé pour aucun rôle → Permission refusée par défaut'))

            # Récupérer les permissions calculées par le service
            self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
            self.stdout.write(self.style.SUCCESS(f'📊 Permissions calculées par PermissionService:'))
            self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

            permissions = PermissionService.get_user_permissions(
                user=user,
                app_name=app_name,
                processus_uuid=processus_uuid_str
            )

            if processus_uuid_str in permissions:
                processus_perms = permissions[processus_uuid_str]
                for action_code, perm_data in processus_perms.items():
                    status = "✓ ACCORDÉ" if perm_data.get('granted') else "✗ REFUSÉ"
                    source = perm_data.get('source', 'unknown')
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  {action_code}: {status} (source: {source})'
                        )
                    )
            else:
                self.stdout.write(self.style.WARNING('  ⚠️  Aucune permission trouvée pour ce processus'))

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}\n'))

