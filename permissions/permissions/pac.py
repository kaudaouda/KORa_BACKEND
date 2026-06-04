from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
import logging
from permissions.services.permission_service import PermissionService
from .base import AppActionPermission

logger = logging.getLogger(__name__)

# ==================== PAC (Plan d'Action de Conformité) ====================

class PACCreatePermission(AppActionPermission):
    """Permission pour créer un PAC"""
    app_name = 'pac'
    action = 'create_pac'


class PACUpdatePermission(AppActionPermission):
    """Permission pour modifier un PAC"""
    app_name = 'pac'
    action = 'update_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        # Si obj est fourni et c'est un objet Pac
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grâce à select_related)
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
                # Si c'est une chaîne (cas improbable mais géré)
                elif isinstance(obj.processus, str):
                    return obj.processus
        
        # Depuis view.kwargs si uuid fourni (pour compatibilité avec les autres méthodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            pac_uuid = view.kwargs['uuid']
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    return str(pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACUpdatePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class PACDeletePermission(AppActionPermission):
    """Permission pour supprimer un PAC"""
    app_name = 'pac'
    action = 'delete_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        # Si obj est fourni et c'est un objet Pac
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grâce à select_related)
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
                # Si c'est une chaîne (cas improbable mais géré)
                elif isinstance(obj.processus, str):
                    return obj.processus
        
        # Depuis view.kwargs si uuid fourni (pour compatibilité avec les autres méthodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            pac_uuid = view.kwargs['uuid']
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    return str(pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDeletePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


class PACValidatePermission(AppActionPermission):
    """Permission pour valider un PAC"""
    app_name = 'pac'
    action = 'validate_pac'


class PacListPermission(BasePermission):
    """
    Permission pour pac_list qui gère GET
    GET : Autorise si authentifié, le filtrage se fait dans la vue avec get_user_processus_list
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.method == 'GET':
            # Pour GET, autoriser si authentifié, le filtrage se fait dans la vue
            return True
        return False


class PacDetailPermission(BasePermission):
    """
    Permission pour pac_detail et pac_complet qui gèrent GET, PATCH et DELETE
    GET : PACReadPermission
    PATCH : PACUpdatePermission
    DELETE : PACDeletePermission
    
    Note: Pour les @api_view, DRF ne passe pas automatiquement par has_object_permission.
    On doit donc vérifier dans has_permission en extrayant l'objet depuis view.kwargs.
    """
    def has_permission(self, request, view):
        """
        Security by Design : Vérifie les permissions AVANT toute requête DB
        Refus par défaut si l'objet n'existe pas ou si les permissions échouent
        """
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"[PacDetailPermission] Utilisateur non authentifié")
            raise PermissionDenied("Authentification requise")
        
        # Extraire l'UUID depuis les kwargs de la vue
        pac_uuid = view.kwargs.get('uuid')
        if not pac_uuid:
            logger.warning(f"[PacDetailPermission] UUID du PAC manquant pour user={request.user.username}")
            raise PermissionDenied("UUID du PAC manquant")
        
        logger.info(
            f"[PacDetailPermission] 🔍 Début vérification permission: "
            f"user={request.user.username}, method={request.method}, pac_uuid={pac_uuid}"
        )
        
        # Récupérer l'objet Pac pour avoir le processus_uuid
        # Security by Design : On doit récupérer l'objet pour vérifier les permissions,
        # mais on le fait dans la permission pour garantir que la vérification se fait avant
        try:
            from pac.models import Pac
            from parametre.permissions import user_has_access_to_processus
            pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
            logger.info(
                f"[PacDetailPermission] ✅ PAC trouvé: uuid={pac.uuid}, processus_uuid={pac.processus.uuid if pac.processus else None}"
            )
        except Pac.DoesNotExist:
            # Security by Design : Refus par défaut - ne pas révéler si l'objet existe ou non
            logger.warning(f"[PacDetailPermission] ❌ PAC non trouvé: uuid={pac_uuid}")
            raise PermissionDenied("Accès refusé à ce PAC")
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not pac.processus:
            logger.warning(f"[PacDetailPermission] ❌ PAC sans processus: uuid={pac_uuid}")
            raise PermissionDenied("Ce PAC n'est associé à aucun processus")
        
        processus_uuid = str(pac.processus.uuid)
        has_access = user_has_access_to_processus(request.user, processus_uuid)
        logger.info(
            f"[PacDetailPermission] 🔍 Vérification accès processus: "
            f"user={request.user.username}, processus_uuid={processus_uuid}, has_access={has_access}"
        )
        
        if not has_access:
            logger.warning(
                f"[PacDetailPermission] ❌ Accès refusé au processus: "
                f"user={request.user.username}, processus_uuid={processus_uuid}"
            )
            raise PermissionDenied("Vous n'avez pas accès au processus de ce PAC")
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier selon la méthode HTTP
        try:
            if request.method == 'GET':
                logger.info(f"[PacDetailPermission] 🔍 Vérification permission read_pac pour user={request.user.username}")
                permission = PACReadPermission()
                permission.has_object_permission(request, view, pac)
                logger.info(f"[PacDetailPermission] ✅ Permission read_pac accordée")
            elif request.method in ['PATCH', 'PUT']:
                logger.info(f"[PacDetailPermission] 🔍 Vérification permission update_pac pour user={request.user.username}")
                permission = PACUpdatePermission()
                permission.has_object_permission(request, view, pac)
                logger.info(f"[PacDetailPermission] ✅ Permission update_pac accordée")
            elif request.method == 'DELETE':
                logger.info(f"[PacDetailPermission] 🔍 Vérification permission delete_pac pour user={request.user.username}")
                permission = PACDeletePermission()
                permission.has_object_permission(request, view, pac)
                logger.info(f"[PacDetailPermission] ✅ Permission delete_pac accordée")
            else:
                logger.warning(f"[PacDetailPermission] ❌ Méthode HTTP non autorisée: {request.method}")
                raise PermissionDenied(f"Méthode HTTP '{request.method}' non autorisée")
        except PermissionDenied as e:
            # Re-lever l'exception pour que DRF la gère correctement
            logger.warning(f"[PacDetailPermission] ❌ Permission refusée: {e}")
            raise
        except Exception as e:
            # Logger l'erreur et refuser l'accès par sécurité
            logger.error(f"[PacDetailPermission] ❌ Erreur lors de la vérification de permission: {e}", exc_info=True)
            raise PermissionDenied("Erreur lors de la vérification des permissions")
        
        logger.info(f"[PacDetailPermission] ✅ Permission accordée pour user={request.user.username}, method={request.method}")
        return True


class PACReadPermission(AppActionPermission):
    """Permission pour lire un PAC"""
    app_name = 'pac'
    action = 'read_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        logger.info(
            f"[PACReadPermission._extract_processus_uuid] 🔍 Extraction processus_uuid: "
            f"obj={obj}, obj_type={type(obj).__name__ if obj else None}"
        )
        
        # Si obj est fourni et c'est un objet Pac
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grâce à select_related)
                if hasattr(obj.processus, 'uuid'):
                    processus_uuid = str(obj.processus.uuid)
                    logger.info(f"[PACReadPermission._extract_processus_uuid] ✅ Extrait depuis obj.processus.uuid: {processus_uuid}")
                    return processus_uuid
                # Si c'est une chaîne (cas improbable mais géré)
                elif isinstance(obj.processus, str):
                    logger.info(f"[PACReadPermission._extract_processus_uuid] ✅ Extrait depuis obj.processus (str): {obj.processus}")
                    return obj.processus
            else:
                logger.warning(
                    f"[PACReadPermission._extract_processus_uuid] ⚠️ obj.processus manquant: "
                    f"has_attr_processus={hasattr(obj, 'processus')}, processus={getattr(obj, 'processus', None)}"
                )
        
        # Depuis view.kwargs si uuid fourni (pour compatibilité avec les autres méthodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            pac_uuid = view.kwargs['uuid']
            logger.info(f"[PACReadPermission._extract_processus_uuid] 🔍 Tentative extraction depuis view.kwargs: pac_uuid={pac_uuid}")
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    processus_uuid = str(pac.processus.uuid)
                    logger.info(f"[PACReadPermission._extract_processus_uuid] ✅ Extrait depuis DB: {processus_uuid}")
                    return processus_uuid
            except Exception as e:
                logger.warning(f"[PACReadPermission._extract_processus_uuid] ⚠️ Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        logger.info(f"[PACReadPermission._extract_processus_uuid] 🔍 Fallback sur méthode parent")
        result = super()._extract_processus_uuid(request, view, obj)
        logger.info(f"[PACReadPermission._extract_processus_uuid] {'✅' if result else '❌'} Résultat méthode parent: {result}")
        return result


class PACAmendementCreatePermission(AppActionPermission):
    """Permission pour créer un amendement PAC"""
    app_name = 'pac'
    action = 'create_amendement_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """
        Extrait le processus_uuid depuis initial_ref ou depuis le processus fourni dans request.data
        Pour créer un amendement, on doit récupérer le PAC initial pour obtenir son processus
        """
        # 1. Depuis l'objet (si fourni)
        if obj:
            if hasattr(obj, 'processus'):
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
            if hasattr(obj, 'processus_uuid'):
                return str(obj.processus_uuid)
        
        # 2. Depuis request.data : initial_ref (cas spécifique pour create_amendement_pac)
        if hasattr(request, 'data') and request.data:
            initial_ref_uuid = request.data.get('initial_ref')
            if initial_ref_uuid:
                # Récupérer le PAC initial pour obtenir son processus
                try:
                    from pac.models import Pac
                    initial_pac = Pac.objects.select_related('processus').get(uuid=initial_ref_uuid)
                    if initial_pac.processus:
                        return str(initial_pac.processus.uuid)
                except Exception as e:
                    logger.warning(
                        f"[PACAmendementCreatePermission] Erreur lors de la récupération "
                        f"du PAC initial {initial_ref_uuid}: {str(e)}"
                    )
            
            # Fallback : processus_uuid ou processus dans request.data
            processus_uuid = request.data.get('processus') or request.data.get('processus_uuid')
            if processus_uuid:
                return str(processus_uuid)
        
        # 3. Depuis view.kwargs si fourni
        if hasattr(view, 'kwargs') and view.kwargs:
            processus_uuid = view.kwargs.get('processus_uuid') or view.kwargs.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        # 4. Depuis query params
        if hasattr(request, 'query_params'):
            processus_uuid = request.query_params.get('processus_uuid') or request.query_params.get('processus')
            if processus_uuid:
                return str(processus_uuid)
        
        return super()._extract_processus_uuid(request, view, obj)


class PACDetailCreatePermission(AppActionPermission):
    """Permission pour créer un détail PAC"""
    app_name = 'pac'
    action = 'create_detail_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (pac) ou depuis obj.pac.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'pac') and obj.pac:
                if hasattr(obj.pac, 'processus') and obj.pac.processus:
                    return str(obj.pac.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            pac_uuid = request.data.get('pac')
            if pac_uuid:
                try:
                    from pac.models import Pac
                    pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                    if pac.processus:
                        return str(pac.processus.uuid)
                except Exception as e:
                    logger.warning(f"[PACDetailCreatePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from pac.models import DetailsPac
                detail = DetailsPac.objects.select_related('pac__processus').get(uuid=detail_uuid)
                if detail.pac and detail.pac.processus:
                    return str(detail.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDetailCreatePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACDetailUpdatePermission(AppActionPermission):
    """Permission pour modifier un détail PAC"""
    app_name = 'pac'
    action = 'update_detail_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.pac.processus"""
        if obj:
            if hasattr(obj, 'pac') and obj.pac:
                if hasattr(obj.pac, 'processus') and obj.pac.processus:
                    return str(obj.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from pac.models import DetailsPac
                detail = DetailsPac.objects.select_related('pac__processus').get(uuid=detail_uuid)
                if detail.pac and detail.pac.processus:
                    return str(detail.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDetailUpdatePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACDetailDeletePermission(AppActionPermission):
    """Permission pour supprimer un détail PAC"""
    app_name = 'pac'
    action = 'delete_detail_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.pac.processus"""
        if obj:
            if hasattr(obj, 'pac') and obj.pac:
                if hasattr(obj.pac, 'processus') and obj.pac.processus:
                    return str(obj.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            detail_uuid = view.kwargs['uuid']
            try:
                from pac.models import DetailsPac
                detail = DetailsPac.objects.select_related('pac__processus').get(uuid=detail_uuid)
                if detail.pac and detail.pac.processus:
                    return str(detail.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACDetailDeletePermission] Erreur extraction processus depuis detail {detail_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACTraitementCreatePermission(AppActionPermission):
    """Permission pour créer un traitement"""
    app_name = 'pac'
    action = 'create_traitement'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (details_pac) ou depuis obj.details_pac.pac.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'details_pac') and obj.details_pac:
                if hasattr(obj.details_pac, 'pac') and obj.details_pac.pac:
                    if hasattr(obj.details_pac.pac, 'processus') and obj.details_pac.pac.processus:
                        return str(obj.details_pac.pac.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            details_pac_uuid = request.data.get('details_pac')
            if details_pac_uuid:
                try:
                    from pac.models import DetailsPac
                    detail = DetailsPac.objects.select_related('pac__processus').get(uuid=details_pac_uuid)
                    if detail.pac and detail.pac.processus:
                        return str(detail.pac.processus.uuid)
                except Exception as e:
                    logger.warning(f"[PACTraitementCreatePermission] Erreur extraction processus depuis details_pac {details_pac_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACTraitementUpdatePermission(AppActionPermission):
    """Permission pour modifier un traitement"""
    app_name = 'pac'
    action = 'update_traitement'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'details_pac') and obj.details_pac:
                if hasattr(obj.details_pac, 'pac') and obj.details_pac.pac:
                    if hasattr(obj.details_pac.pac, 'processus') and obj.details_pac.pac.processus:
                        return str(obj.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            traitement_uuid = view.kwargs['uuid']
            try:
                from pac.models import TraitementPac
                traitement = TraitementPac.objects.select_related('details_pac__pac__processus').get(uuid=traitement_uuid)
                if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                    return str(traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACTraitementUpdatePermission] Erreur extraction processus depuis traitement {traitement_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACTraitementDeletePermission(AppActionPermission):
    """Permission pour supprimer un traitement"""
    app_name = 'pac'
    action = 'delete_traitement'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'details_pac') and obj.details_pac:
                if hasattr(obj.details_pac, 'pac') and obj.details_pac.pac:
                    if hasattr(obj.details_pac.pac, 'processus') and obj.details_pac.pac.processus:
                        return str(obj.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            traitement_uuid = view.kwargs['uuid']
            try:
                from pac.models import TraitementPac
                traitement = TraitementPac.objects.select_related('details_pac__pac__processus').get(uuid=traitement_uuid)
                if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                    return str(traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACTraitementDeletePermission] Erreur extraction processus depuis traitement {traitement_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACSuiviCreatePermission(AppActionPermission):
    """Permission pour créer un suivi"""
    app_name = 'pac'
    action = 'create_suivi'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis request.data (traitement) ou depuis obj.traitement.details_pac.pac.processus"""
        # Depuis obj si fourni
        if obj:
            if hasattr(obj, 'traitement') and obj.traitement:
                if hasattr(obj.traitement, 'details_pac') and obj.traitement.details_pac:
                    if hasattr(obj.traitement.details_pac, 'pac') and obj.traitement.details_pac.pac:
                        if hasattr(obj.traitement.details_pac.pac, 'processus') and obj.traitement.details_pac.pac.processus:
                            return str(obj.traitement.details_pac.pac.processus.uuid)
        
        # Depuis request.data (pour POST)
        if hasattr(request, 'data') and request.data:
            traitement_uuid = request.data.get('traitement')
            if traitement_uuid:
                try:
                    from pac.models import TraitementPac
                    traitement = TraitementPac.objects.select_related('details_pac__pac__processus').get(uuid=traitement_uuid)
                    if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                        return str(traitement.details_pac.pac.processus.uuid)
                except Exception as e:
                    logger.warning(f"[PACSuiviCreatePermission] Erreur extraction processus depuis traitement {traitement_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACSuiviUpdatePermission(AppActionPermission):
    """Permission pour modifier un suivi"""
    app_name = 'pac'
    action = 'update_suivi'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.traitement.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'traitement') and obj.traitement:
                if hasattr(obj.traitement, 'details_pac') and obj.traitement.details_pac:
                    if hasattr(obj.traitement.details_pac, 'pac') and obj.traitement.details_pac.pac:
                        if hasattr(obj.traitement.details_pac.pac, 'processus') and obj.traitement.details_pac.pac.processus:
                            return str(obj.traitement.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            suivi_uuid = view.kwargs['uuid']
            try:
                from pac.models import PacSuivi
                suivi = PacSuivi.objects.select_related('traitement__details_pac__pac__processus').get(uuid=suivi_uuid)
                if suivi.traitement and suivi.traitement.details_pac and suivi.traitement.details_pac.pac and suivi.traitement.details_pac.pac.processus:
                    return str(suivi.traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACSuiviUpdatePermission] Erreur extraction processus depuis suivi {suivi_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACSuiviDeletePermission(AppActionPermission):
    """Permission pour supprimer un suivi"""
    app_name = 'pac'
    action = 'delete_suivi'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.traitement.details_pac.pac.processus"""
        if obj:
            if hasattr(obj, 'traitement') and obj.traitement:
                if hasattr(obj.traitement, 'details_pac') and obj.traitement.details_pac:
                    if hasattr(obj.traitement.details_pac, 'pac') and obj.traitement.details_pac.pac:
                        if hasattr(obj.traitement.details_pac.pac, 'processus') and obj.traitement.details_pac.pac.processus:
                            return str(obj.traitement.details_pac.pac.processus.uuid)
        
        # Depuis view.kwargs si uuid fourni
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            suivi_uuid = view.kwargs['uuid']
            try:
                from pac.models import PacSuivi
                suivi = PacSuivi.objects.select_related('traitement__details_pac__pac__processus').get(uuid=suivi_uuid)
                if suivi.traitement and suivi.traitement.details_pac and suivi.traitement.details_pac.pac and suivi.traitement.details_pac.pac.processus:
                    return str(suivi.traitement.details_pac.pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACSuiviDeletePermission] Erreur extraction processus depuis suivi {suivi_uuid}: {e}")
        
        return super()._extract_processus_uuid(request, view, obj)


class PACUnvalidatePermission(AppActionPermission):
    """Permission pour dévalider un PAC"""
    app_name = 'pac'
    action = 'unvalidate_pac'
    
    def _extract_processus_uuid(self, request, view, obj=None):
        """Extrait le processus_uuid depuis obj.processus (si obj est un Pac)"""
        # Si obj est fourni et c'est un objet Pac
        if obj:
            if hasattr(obj, 'processus') and obj.processus:
                # obj.processus est un objet Processus (grâce à select_related)
                if hasattr(obj.processus, 'uuid'):
                    return str(obj.processus.uuid)
                # Si c'est une chaîne (cas improbable mais géré)
                elif isinstance(obj.processus, str):
                    return obj.processus
        
        # Depuis view.kwargs si uuid fourni (pour compatibilité avec les autres méthodes)
        if hasattr(view, 'kwargs') and view.kwargs.get('uuid'):
            pac_uuid = view.kwargs['uuid']
            try:
                from pac.models import Pac
                pac = Pac.objects.select_related('processus').get(uuid=pac_uuid)
                if pac.processus:
                    return str(pac.processus.uuid)
            except Exception as e:
                logger.warning(f"[PACUnvalidatePermission] Erreur extraction processus depuis pac {pac_uuid}: {e}")
        
        # Fallback sur la méthode parent pour les autres cas
        return super()._extract_processus_uuid(request, view, obj)


# ==================== ACTIVITÉ PÉRIODIQUE ====================
