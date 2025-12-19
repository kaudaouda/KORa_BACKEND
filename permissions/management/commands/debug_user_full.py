"""
Commande de diagnostic COMPLET pour vérifier les permissions d'un utilisateur
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from permissions.models import RolePermissionMapping, PermissionAction
from parametre.models import UserProcessusRole, Processus
from permissions.services.permission_service import PermissionService

User = get_user_model()


class Command(BaseCommand):
    help = 'Diagnostic COMPLET des permissions d\'un utilisateur'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username de l\'utilisateur')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
            
            self.stdout.write(self.style.SUCCESS(
                '\n╔═══════════════════════════════════════════════════════════════╗'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'║  DIAGNOSTIC COMPLET DES PERMISSIONS                          ║'
            ))
            self.stdout.write(self.style.SUCCESS(
                '╠═══════════════════════════════════════════════════════════════╣'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'║  Utilisateur: {user.username:<48}║'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'║  User ID: {user.id:<52}║'
            ))
            self.stdout.write(self.style.SUCCESS(
                '╚═══════════════════════════════════════════════════════════════╝\n'
            ))
            
            # 1. Lister tous les rôles actifs
            user_roles = UserProcessusRole.objects.filter(
                user=user, 
                is_active=True
            ).select_related('role', 'processus')
            
            self.stdout.write(self.style.WARNING(
                f'\n📋 RÔLES ACTIFS ({user_roles.count()}):'
            ))
            self.stdout.write('─' * 70)
            
            for ur in user_roles:
                self.stdout.write(
                    f'\n  🔹 {ur.role.nom} ({ur.role.code})'
                )
                self.stdout.write(
                    f'     Processus: {ur.processus.nom}'
                )
                self.stdout.write(
                    f'     UUID: {ur.processus.uuid}'
                )
            
            if user_roles.count() == 0:
                self.stdout.write(self.style.ERROR(
                    '  ❌ Aucun rôle actif trouvé!'
                ))
                return
            
            # 2. Pour chaque processus, afficher les permissions
            for ur in user_roles:
                processus = ur.processus
                
                self.stdout.write(self.style.SUCCESS(
                    f'\n\n╔═══════════════════════════════════════════════════════════════╗'
                ))
                self.stdout.write(self.style.SUCCESS(
                    f'║  PROCESSUS: {processus.nom:<50}║'
                ))
                self.stdout.write(self.style.SUCCESS(
                    '╚═══════════════════════════════════════════════════════════════╝'
                ))
                
                # Obtenir les permissions pour ce processus
                permissions = PermissionService.get_user_permissions(
                    user=user,
                    app_name='dashboard',
                    processus_uuid=str(processus.uuid)
                )
                
                if not permissions:
                    self.stdout.write(self.style.ERROR(
                        '  ❌ Aucune permission trouvée pour ce processus'
                    ))
                    continue
                
                # Afficher les permissions
                self.stdout.write('\n  🎯 PERMISSIONS DASHBOARD:')
                self.stdout.write('  ' + '─' * 66)
                
                for action_code, perm_detail in sorted(permissions.items()):
                    granted = perm_detail.get('granted', False)
                    source = perm_detail.get('source', 'unknown')
                    priority = perm_detail.get('priority', 'N/A')
                    role = perm_detail.get('role', 'N/A')
                    
                    if granted:
                        status = self.style.SUCCESS('✅ GRANTED')
                    else:
                        status = self.style.ERROR('❌ DENIED ')
                    
                    self.stdout.write(
                        f'\n    {status} | {action_code:<25} | '
                        f'Role: {role} (priority: {priority})'
                    )
                
                # Vérifier spécifiquement create_objective
                create_obj = permissions.get('create_objective', {})
                
                self.stdout.write(self.style.WARNING(
                    f'\n  ⚡ FOCUS: create_objective'
                ))
                self.stdout.write('  ' + '─' * 66)
                
                if create_obj:
                    self.stdout.write(
                        f'    Granted: {create_obj.get("granted", False)}'
                    )
                    self.stdout.write(
                        f'    Source: {create_obj.get("source", "unknown")}'
                    )
                    self.stdout.write(
                        f'    Priority: {create_obj.get("priority", "N/A")}'
                    )
                    self.stdout.write(
                        f'    Role: {create_obj.get("role", "N/A")}'
                    )
                    
                    if create_obj.get('granted', False):
                        self.stdout.write(self.style.SUCCESS(
                            '\n    ✅ L\'utilisateur PEUT créer des objectifs!'
                        ))
                    else:
                        self.stdout.write(self.style.ERROR(
                            '\n    ❌ L\'utilisateur NE PEUT PAS créer des objectifs!'
                        ))
                else:
                    self.stdout.write(self.style.ERROR(
                        '    ❌ Permission create_objective non trouvée'
                    ))
            
            # 3. Vérifier les mappings pour create_objective
            self.stdout.write(self.style.WARNING(
                f'\n\n╔═══════════════════════════════════════════════════════════════╗'
            ))
            self.stdout.write(self.style.WARNING(
                f'║  MAPPINGS create_objective                                    ║'
            ))
            self.stdout.write(self.style.WARNING(
                '╚═══════════════════════════════════════════════════════════════╝'
            ))
            
            try:
                create_obj_action = PermissionAction.objects.get(
                    app_name='dashboard',
                    code='create_objective'
                )
                
                mappings = RolePermissionMapping.objects.filter(
                    permission_action=create_obj_action
                ).select_related('role').order_by('-priority')
                
                self.stdout.write(f'\n  📊 {mappings.count()} mappings trouvés:\n')
                
                for m in mappings:
                    granted_str = self.style.SUCCESS('✅ GRANTED') if m.granted else self.style.ERROR('❌ DENIED')
                    has_role = user_roles.filter(role=m.role).exists()
                    
                    self.stdout.write(
                        f'    {granted_str} | {m.role.nom:<20} | priority: {m.priority}'
                    )
                    
                    if has_role:
                        self.stdout.write(self.style.SUCCESS(
                            f'               👤 L\'utilisateur possède ce rôle!'
                        ))
                    
            except PermissionAction.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    '  ❌ PermissionAction create_objective non trouvée en BDD'
                ))
            
            # 4. Invalider le cache
            self.stdout.write(self.style.WARNING(
                f'\n\n╔═══════════════════════════════════════════════════════════════╗'
            ))
            self.stdout.write(self.style.WARNING(
                f'║  INVALIDATION DU CACHE                                        ║'
            ))
            self.stdout.write(self.style.WARNING(
                '╚═══════════════════════════════════════════════════════════════╝'
            ))
            
            PermissionService.invalidate_user_cache(user.id, app_name=None)
            
            self.stdout.write(self.style.SUCCESS(
                '\n  ✅ Cache invalidé pour toutes les apps'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  🔄 Nouvelles permissions chargées en 5-10 secondes max'
            ))
            self.stdout.write(self.style.SUCCESS(
                '  💡 Demandez à l\'utilisateur de rafraîchir (F5) ou changer d\'onglet\n'
            ))
                
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Utilisateur "{username}" non trouvé\n'
            ))

