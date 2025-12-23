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
        '/api/documents/': 'documentation',
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
                # Security by Design : Super admin bypass
                # Seuls les utilisateurs avec is_staff ET is_superuser peuvent bypasser
                if request.user.is_authenticated and request.user.is_staff and request.user.is_superuser:
                    logger.debug(
                        f"[ApplicationMaintenance] Super admin bypass pour {app_name} "
                        f"(user: {request.user.username})"
                    )
                    return None  # Laisser passer
                
                # Vérifier si l'app est activée
                try:
                    config = ApplicationConfig.objects.get(app_name=app_name)
                    
                    # Security by Design : Refus par défaut si is_enabled=False
                    if not config.is_enabled:
                        # Logger la tentative d'accès bloquée
                        user_info = f"user: {request.user.username}" if request.user.is_authenticated else "anonymous"
                        logger.warning(
                            f"[ApplicationMaintenance] Accès bloqué à {app_name} "
                            f"({user_info}, IP: {self._get_client_ip(request)})"
                        )
                        
                        # Application en maintenance - retourner 503
                        return JsonResponse({
                            'error': 'Application en maintenance',
                            'message': config.maintenance_message or 'Cette application est temporairement indisponible',
                            'app_name': app_name,
                            'maintenance_start': config.maintenance_start.isoformat() if config.maintenance_start else None,
                            'maintenance_end': config.maintenance_end.isoformat() if config.maintenance_end else None,
                            'code': 'APP_MAINTENANCE'
                        }, status=503)
                    
                    # Application activée, laisser passer
                    return None
                    
                except ApplicationConfig.DoesNotExist:
                    # Security by Design : Si pas de config, laisser passer pour compatibilité
                    # Cela permet de ne pas casser les apps qui n'ont pas encore de config
                    logger.debug(
                        f"[ApplicationMaintenance] Pas de config pour {app_name}, "
                        f"accès autorisé par défaut"
                    )
                    return None
                except Exception as e:
                    # Security by Design : En cas d'erreur, logger mais laisser passer
                    # pour éviter de bloquer tout le système
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
