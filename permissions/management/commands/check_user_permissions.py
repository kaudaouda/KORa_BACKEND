"""
Commande Django pour vérifier les permissions d'un utilisateur spécifique
Utile pour déboguer les problèmes de permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.cache import cache
from permissions.models import PermissionAction, RolePermissionMapping
from parametre.models import Role, UserProcessusRole, Processus
from permissions.services.permission_service import PermissionService


class Command(BaseCommand):
    help = 'Vérifie les permissions d\'un utilisateur pour déboguer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Nom d\'utilisateur à vérifier'
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
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Vider le cache avant de vérifier'
        )

    def handle(self, *args, **options):
        username = options['username']
        app_name = options['app']
        processus_uuid = options.get('processus_uuid')
        clear_cache = options.get('clear_cache', False)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Utilisateur "{username}" non trouvé'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS(f'🔍 VÉRIFICATION DES PERMISSIONS'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
        self.stdout.write(self.style.SUCCESS(f'Utilisateur: {user.username} (ID: {user.id})'))
        self.stdout.write(self.style.SUCCESS(f'Application: {app_name}\n'))

        # Vider le cache si demandé
        if clear_cache:
            self.stdout.write(self.style.WARNING('🗑️  Vidage du cache...'))
            PermissionService.invalidate_user_cache(user.id, app_name=app_name)
            self.stdout.write(self.style.SUCCESS('✓ Cache vidé\n'))

        # Vérifier si super admin
        is_super_admin = PermissionService._is_super_admin(user)
        if is_super_admin:
            self.stdout.write(self.style.WARNING('⚠️  Super admin détecté - toutes les permissions accordées\n'))
            return

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

        # Grouper les rôles par processus
        roles_by_processus = {}
        for user_role in user_roles:
            processus_uuid_str = str(user_role.processus.uuid)
            if processus_uuid_str not in roles_by_processus:
                roles_by_processus[processus_uuid_str] = []
            roles_by_processus[processus_uuid_str].append(user_role.role)

        # Pour chaque processus, vérifier les permissions
        for processus_uuid_str, roles in roles_by_processus.items():
            if processus_uuid and str(processus_uuid_str) != processus_uuid:
                continue

            processus = user_roles[0].processus
            self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
            self.stdout.write(self.style.SUCCESS(f'📊 Processus: {processus.nom} (UUID: {processus_uuid_str})'))
            self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))

            # Vérifier les permissions pour chaque action
            self.stdout.write(self.style.SUCCESS(f'\n🔍 Détail des permissions:\n'))

            for action in actions:
                self.stdout.write(f'\n  Action: {action.code}')
                self.stdout.write(f'  {"-"*60}')

                # Vérifier les mappings pour chaque rôle
                mappings_by_role = {}
                for role in roles:
                    role_mappings = RolePermissionMapping.objects.filter(
                        role=role,
                        permission_action=action,
                        is_active=True
                    ).order_by('-priority')

                    if role_mappings.exists():
                        mappings_by_role[role.code] = list(role_mappings)
                        for mapping in role_mappings:
                            status = "✓ ACCORDÉ" if mapping.granted else "✗ REFUSÉ"
                            self.stdout.write(
                                f'    [{role.code}] Priority: {mapping.priority} → {status}'
                            )
                    else:
                        self.stdout.write(f'    [{role.code}] → Aucun mapping trouvé')

                # Calculer la permission finale (comme le fait PermissionService)
                granted = False
                conditions = {}
                max_priority = -1
                winning_role = None

                for role in roles:
                    role_mappings = RolePermissionMapping.objects.filter(
                        role=role,
                        permission_action=action,
                        is_active=True
                    ).order_by('-priority')

                    for mapping in role_mappings:
                        if mapping.priority > max_priority:
                            max_priority = mapping.priority
                            granted = mapping.granted
                            conditions = mapping.conditions or {}
                            winning_role = role.code

                if winning_role:
                    status = "✓ ACCORDÉ" if granted else "✗ REFUSÉ"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\n  🎯 RÉSULTAT FINAL: {status} '
                            f'(Rôle gagnant: {winning_role}, Priority: {max_priority})'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING('\n  ⚠️  RÉSULTAT FINAL: ✗ REFUSÉ (Aucun mapping trouvé)')
                    )

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
                granted_count = sum(1 for p in processus_perms.values() if p.get('granted'))
                total_count = len(processus_perms)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Total: {granted_count}/{total_count} permissions accordées\n'
                    )
                )
                
                for action_code, perm_data in sorted(processus_perms.items()):
                    status = "✓ ACCORDÉ" if perm_data.get('granted') else "✗ REFUSÉ"
                    source = perm_data.get('source', 'unknown')
                    self.stdout.write(
                        f'  {action_code}: {status} (source: {source})'
                    )
            else:
                self.stdout.write(self.style.WARNING('  ⚠️  Aucune permission trouvée pour ce processus'))

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}\n'))

