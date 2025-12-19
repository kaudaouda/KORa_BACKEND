"""
Commande de diagnostic pour vérifier les permissions d'un utilisateur
et invalider son cache si nécessaire
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from permissions.models import RolePermissionMapping, PermissionAction
from parametre.models import UserProcessusRole
from permissions.services.permission_service import PermissionService

User = get_user_model()


class Command(BaseCommand):
    help = 'Diagnostique les permissions d\'un utilisateur et invalide son cache'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username de l\'utilisateur')
        parser.add_argument(
            '--invalidate',
            action='store_true',
            help='Invalider le cache de l\'utilisateur'
        )

    def handle(self, *args, **options):
        username = options['username']
        should_invalidate = options.get('invalidate', False)
        
        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Utilisateur trouvé: {user.username} (ID: {user.id})'
            ))
            
            # 1. Vérifier ses rôles actifs
            user_roles = UserProcessusRole.objects.filter(
                user=user, 
                is_active=True
            ).select_related('role', 'processus')
            
            self.stdout.write(self.style.WARNING(
                f'\n📋 Rôles actifs de l\'utilisateur ({user_roles.count()}):'
            ))
            
            for ur in user_roles:
                self.stdout.write(
                    f'  - {ur.role.nom} ({ur.role.code}) '
                    f'dans processus {ur.processus.nom} ({ur.processus.uuid})'
                )
            
            # 2. Vérifier la permission create_objective
            try:
                create_obj_action = PermissionAction.objects.get(
                    app_name='dashboard', 
                    code='create_objective'
                )
                
                self.stdout.write(self.style.WARNING(
                    f'\n🎯 Permission create_objective (ID: {create_obj_action.id})'
                ))
                
                # 3. Vérifier les mappings pour cette permission
                mappings = RolePermissionMapping.objects.filter(
                    permission_action=create_obj_action
                ).select_related('role').order_by('-priority')
                
                self.stdout.write(self.style.WARNING(
                    f'\n🗺️ Mappings pour create_objective ({mappings.count()}):'
                ))
                
                for m in mappings:
                    granted_str = self.style.SUCCESS('✅ GRANTED') if m.granted else self.style.ERROR('❌ DENIED')
                    self.stdout.write(
                        f'  - {m.role.nom} ({m.role.code}): {granted_str}, priority={m.priority}'
                    )
                    
                    # Vérifier si l'utilisateur a ce rôle
                    has_role = user_roles.filter(role=m.role).exists()
                    if has_role:
                        self.stdout.write(
                            self.style.SUCCESS(f'    👤 L\'utilisateur possède ce rôle !')
                        )
                        
            except PermissionAction.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    '❌ Permission create_objective non trouvée dans la BDD'
                ))
            
            # 4. Tester avec PermissionService
            if user_roles.exists():
                first_processus = user_roles.first().processus
                self.stdout.write(self.style.WARNING(
                    f'\n🧪 Test avec PermissionService pour processus {first_processus.nom}:'
                ))
                
                permissions = PermissionService.get_user_permissions(
                    user=user,
                    app_name='dashboard',
                    processus_uuid=str(first_processus.uuid)
                )
                
                create_obj_perm = permissions.get('create_objective', {})
                if create_obj_perm:
                    granted = create_obj_perm.get('granted', False)
                    source = create_obj_perm.get('source', 'unknown')
                    granted_str = self.style.SUCCESS('✅ GRANTED') if granted else self.style.ERROR('❌ DENIED')
                    self.stdout.write(
                        f'  create_objective: {granted_str} (source: {source})'
                    )
                else:
                    self.stdout.write(self.style.ERROR(
                        '  ❌ create_objective non trouvé dans les permissions calculées'
                    ))
            
            # 5. Invalider le cache si demandé
            if should_invalidate:
                self.stdout.write(self.style.WARNING(
                    f'\n🔄 Invalidation du cache pour user_id={user.id}...'
                ))
                PermissionService.invalidate_user_cache(user.id, app_name=None)
                self.stdout.write(self.style.SUCCESS(
                    '✅ Cache invalidé pour toutes les apps (cdr, dashboard, pac)'
                ))
                self.stdout.write(self.style.WARNING(
                    '⚠️  Demandez à l\'utilisateur de rafraîchir sa page (F5)'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    '\n💡 Utilisez --invalidate pour invalider le cache de cet utilisateur'
                ))
                
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'❌ Utilisateur "{username}" non trouvé'
            ))

