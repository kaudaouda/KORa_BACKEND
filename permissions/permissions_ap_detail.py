"""
Permission pour activite_periodique_detail
Basé sur le modèle de PacDetailPermission
"""
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


class ActivitePeriodiqueDetailPermission(BasePermission):
    """
    Permission pour activite_periodique_detail qui gère GET
    GET : ActivitePeriodiqueReadPermission
    
    Security by Design : Refus par défaut, vérifie l'authentification puis les permissions
    Gère automatiquement les super admins via user_has_access_to_processus
    
    Note: Pour les @api_view, DRF ne passe pas automatiquement par has_object_permission.
    On doit donc vérifier dans has_permission en extrayant l'objet depuis view.kwargs.
    """
    def has_permission(self, request, view):
        """
        Security by Design : Vérifie les permissions AVANT toute requête DB
        Refus par défaut si l'objet n'existe pas ou si les permissions échouent
        """
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"[ActivitePeriodiqueDetailPermission] Utilisateur non authentifié")
            raise PermissionDenied("Authentification requise")
        
        # Extraire l'UUID depuis les kwargs de la vue
        ap_uuid = view.kwargs.get('uuid')
        if not ap_uuid:
            logger.warning(f"[ActivitePeriodiqueDetailPermission] UUID de l'AP manquant pour user={request.user.username}")
            raise PermissionDenied("UUID de l'Activité Périodique manquant")
        
        logger.info(
            f"[ActivitePeriodiqueDetailPermission] 🔍 Début vérification permission: "
            f"user={request.user.username}, method={request.method}, ap_uuid={ap_uuid}"
        )
        
        # Récupérer l'objet ActivitePeriodique pour avoir le processus_uuid
        # Security by Design : On doit récupérer l'objet pour vérifier les permissions
        try:
            from activite_periodique.models import ActivitePeriodique
            from parametre.permissions import user_has_access_to_processus
            ap = ActivitePeriodique.objects.select_related('processus').get(uuid=ap_uuid)
            logger.info(
                f"[ActivitePeriodiqueDetailPermission] ✅ AP trouvé: uuid={ap.uuid}, processus_uuid={ap.processus.uuid if ap.processus else None}"
            )
        except ActivitePeriodique.DoesNotExist:
            # Security by Design : Refus par défaut - ne pas révéler si l'objet existe ou non
            logger.warning(f"[ActivitePeriodiqueDetailPermission] ❌ AP non trouvé: uuid={ap_uuid}")
            raise PermissionDenied("Accès refusé à cette Activité Périodique")
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not ap.processus:
            logger.warning(f"[ActivitePeriodiqueDetailPermission] ❌ AP sans processus: uuid={ap_uuid}")
            raise PermissionDenied("Cette Activité Périodique n'est associée à aucun processus")
        
        # Vérifier que l'utilisateur a accès au processus (gère automatiquement les super admins)
        if not user_has_access_to_processus(request.user, ap.processus.uuid):
            logger.warning(
                f"[ActivitePeriodiqueDetailPermission] ❌ Accès refusé: user={request.user.username}, "
                f"ap_uuid={ap_uuid}, processus_uuid={ap.processus.uuid}"
            )
            raise PermissionDenied(
                "Vous n'avez pas accès à cette Activité Périodique. "
                "Vous n'avez pas de rôle actif pour ce processus."
            )
        # ========== FIN VÉRIFICATION ==========
        
        if request.method == 'GET':
            # Vérifier read_activite_periodique si besoin (optionnel)
            # Pour l'instant, on autorise GET si l'utilisateur a accès au processus
            logger.info(
                f"[ActivitePeriodiqueDetailPermission] ✅ Permission accordée: user={request.user.username}, "
                f"method={request.method}, ap_uuid={ap_uuid}"
            )
            return True
        
        return False
