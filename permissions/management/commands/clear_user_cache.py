"""
Commande simple pour invalider le cache des permissions d'un utilisateur
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from permissions.services.permission_service import PermissionService

User = get_user_model()


class Command(BaseCommand):
    help = 'Invalide le cache des permissions pour un utilisateur'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username de l\'utilisateur')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
            
            # Invalider le cache
            PermissionService.invalidate_user_cache(user.id, app_name=None)
            
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Cache invalidé pour {user.username} (ID: {user.id})\n'
                f'🔄 Les nouvelles permissions seront chargées dans 5 secondes maximum\n'
                f'💡 Demandez à l\'utilisateur de rafraîchir sa page (F5)\n'
            ))
                
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Utilisateur "{username}" non trouvé\n'
            ))

