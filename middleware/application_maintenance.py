"""
Middleware pour vérifier si une application est en mode maintenance
Security by Design :
- Refus par défaut : Si config existe et is_enabled=False, bloquer
- Super admin bypass : is_staff ET is_superuser peuvent toujours accéder
- Pas de révélation d'informations : Messages génériques pour les erreurs
- Logging : Tracer les tentatives d'accès aux apps en maintenance
"""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class ApplicationMaintenanceMiddleware(MiddlewareMixin):
    """
    Middleware qui vérifie si l'application demandée est en maintenance
    
    Security by Design :
    - Refus par défaut si application désactivée
    - Super admin bypass (is_staff ET is_superuser)
    - Logging des tentatives d'accès
    - Pas de révélation d'informations sensibles
    """
    
    # Mapping URL -> app_name
    APP_ROUTES = {
        '/api/dashboard/': 'dashboard',
        '/api/pac/': 'pac',
        '/api/cdr/': 'cdr',
        '/api/activite-periodique/': 'activite_periodique',
        '/api/documentation/': 'documentation',
    }
    
    def process_request(self, request):
        """
        Vérifie si la route demandée correspond à une application en maintenance
        
        Security by Design :
        1. Identifier l'application depuis l'URL
        2. Super admin bypass (is_staff ET is_superuser)
        3. Vérifier si config existe
        4. Si config existe et is_enabled=False, bloquer (refus par défaut)
        5. Si config n'existe pas, laisser passer (pour compatibilité)
        6. Logger les tentatives d'accès bloquées
        """
        # Importer ici pour éviter les imports circulaires
        from parametre.models import ApplicationConfig
        
        # Vérifier si la route correspond à une application
        for url_prefix, app_name in self.APP_ROUTES.items():
            if request.path.startswith(url_prefix):
                user = request.user
                is_auth = user.is_authenticated
                is_admin = is_auth and getattr(user, 'is_staff', False) and getattr(user, 'is_superuser', False)

                # Super admin bypass
                if is_admin:
                    return None

                # Vérifier si l'app est activée
                try:
                    config = ApplicationConfig.objects.get(app_name=app_name)

                    # Security by Design : Refus par défaut si is_enabled=False
                    if not config.is_enabled:
                        user_info = f"user: {user.username}" if is_auth else "anonymous"
                        logger.warning(
                            f"[ApplicationMaintenance] Accès bloqué à {app_name} ({user_info})"
                        )
                        return JsonResponse({
                            'error': 'Application en maintenance',
                            'message': config.maintenance_message or 'Cette application est temporairement indisponible',
                            'app_name': app_name,
                            'maintenance_start': config.maintenance_start.isoformat() if config.maintenance_start else None,
                            'maintenance_end': config.maintenance_end.isoformat() if config.maintenance_end else None,
                            'code': 'APP_MAINTENANCE'
                        }, status=503)

                    return None

                except ApplicationConfig.DoesNotExist:
                    return None
                except Exception as e:
                    logger.error(
                        f"[ApplicationMaintenance] Erreur lors de la vérification de {app_name}: {e}",
                        exc_info=True
                    )
                    return None
        
        # Route ne correspond à aucune application, continuer normalement
        return None
    
    def _get_client_ip(self, request):
        """
        Récupère l'IP du client de manière sécurisée
        Security by Design : Vérifier les headers de proxy
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Prendre la première IP (client réel)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
