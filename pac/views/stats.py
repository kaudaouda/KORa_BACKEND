"""
Vues API pour l'application PAC
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from shared.throttles import KoraSensitiveThrottle
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime, timedelta
from ..models import Pac, TraitementPac, PacSuivi, DetailsPac
from parametre.models import Processus, Media, Preuve, Notification, FailedLoginAttempt, LoginSecurityConfig, LoginBlock
from parametre.views import log_pac_creation, log_pac_update, log_traitement_creation, log_suivi_creation, log_user_login, log_user_logout, get_client_ip, log_activity
from parametre.utils.email_security import EmailValidator, EmailContentSanitizer, EmailRateLimiter, SecureEmailLogger
from parametre.utils.email_config import load_email_settings_into_django
from parametre.permissions import (
    check_permission_or_403,
    user_can_create_objectives_amendements,
    user_can_create_for_processus,
    get_user_processus_list,
    user_has_access_to_processus,
)
# Import des classes de permissions génériques PAC
from permissions.permissions import (
    PacListPermission,
    PacDetailPermission,
    PACCreatePermission,
    PACUpdatePermission,
    PACDeletePermission,
    PACValidatePermission,
    PACUnvalidatePermission,
    PACReadPermission,
    PACAmendementCreatePermission,
    PACDetailCreatePermission,
    PACDetailUpdatePermission,
    PACDetailDeletePermission,
    PACTraitementCreatePermission,
    PACTraitementUpdatePermission,
    PACTraitementDeletePermission,
    PACSuiviCreatePermission,
    PACSuiviUpdatePermission,
    PACSuiviDeletePermission,
)
from ..serializers import (
    UserSerializer, ProcessusSerializer, ProcessusCreateSerializer,
    PacSerializer, PacCreateSerializer, PacUpdateSerializer, PacCompletSerializer,
    TraitementPacSerializer, TraitementPacCreateSerializer, TraitementPacUpdateSerializer, 
    PacSuiviSerializer, PacSuiviCreateSerializer, PacSuiviUpdateSerializer,
    DetailsPacSerializer, DetailsPacCreateSerializer, DetailsPacUpdateSerializer
)
from shared.authentication import AuthService
from shared.services.recaptcha_service import recaptcha_service, RecaptchaValidationError
import json
import logging

logger = logging.getLogger(__name__)


from .utils import AllowAnyWithJWT, _get_next_num_amendement_for_pac

def pac_upcoming_notifications(request):
    """Récupérer les traitements bientôt à terme pour les notifications"""
    try:
        from datetime import datetime as dt_class
        from django.contrib.contenttypes.models import ContentType

        today = timezone.now().date()
        
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les notifications sans filtre
            traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                delai_realisation__isnull=False
            ).select_related(
                'details_pac', 
                'details_pac__pac',
                'details_pac__pac__processus',
                'details_pac__nature',
                'type_action'
            ).prefetch_related(
                'responsables_directions',
                'responsables_sous_directions'
            )
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucune notification trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Récupérer tous les traitements des processus de l'utilisateur avec leurs délais de réalisation
            traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                details_pac__pac__processus__uuid__in=user_processus_uuids,
            delai_realisation__isnull=False
        ).select_related(
            'details_pac', 
            'details_pac__pac',
            'details_pac__pac__processus',
            'details_pac__nature',
            'type_action'
        ).prefetch_related(
            'responsables_directions',
            'responsables_sous_directions'
        )
        
        notifications = []
        
        for traitement in traitements:
            try:
                # Vérifier que le traitement a bien un details_pac et un pac
                if not traitement.details_pac or not traitement.details_pac.pac:
                    continue
                    
                delai_date = traitement.delai_realisation
                if not delai_date:
                    continue
                
                # Convertir en date si nécessaire
                if isinstance(delai_date, dt_class):
                    delai_date = delai_date.date()
                
                # Calculer la différence en jours
                try:
                    diff_days = (delai_date - today).days
                except (TypeError, AttributeError) as e:
                    logger.warning(f"[pac_upcoming_notifications] Erreur lors du calcul de la différence de jours: {e}")
                    continue
                
                # Inclure les traitements arrivés à terme (en retard) et bientôt à terme (dans les 7 prochains jours)
                if diff_days <= 7:
                    # Déterminer la priorité
                    if diff_days < 0:
                        priority = 'high'  # En retard
                        delai_label = f'En retard de {abs(diff_days)} jour{"s" if abs(diff_days) > 1 else ""}'
                    elif diff_days == 0:
                        priority = 'high'  # Échéance aujourd'hui
                        delai_label = 'Échéance aujourd\'hui'
                    elif diff_days <= 3:
                        priority = 'high'  # Dans les 3 prochains jours
                        delai_label = f'Échéance dans {diff_days} jour{"s" if diff_days > 1 else ""}'
                    else:
                        priority = 'medium'  # Dans 4-7 jours
                        delai_label = f'Échéance dans {diff_days} jours'
                    
                    # Construire le titre
                    pac = traitement.details_pac.pac
                    numero_pac = traitement.details_pac.numero_pac or f'PAC-{pac.uuid}'
                    action_title = traitement.action[:50] if traitement.action else 'Action non spécifiée'
                    if len(traitement.action or '') > 50:
                        action_title += '...'
                    
                    title = f'{numero_pac} - Action : {action_title}'
                    
                    # Construire l'URL d'action
                    action_url = f'/pac/{pac.uuid}'
                    message = f'Délai de réalisation {delai_label}'
                    
                    # Récupérer les informations supplémentaires
                    nature_label = traitement.details_pac.nature.nom if traitement.details_pac.nature else None
                    type_action = traitement.type_action.nom if traitement.type_action else None
                    
                    notifications.append({
                        'id': str(traitement.uuid),
                        'type': 'traitement',
                        'title': title,
                        'numero_pac': numero_pac,
                        'action': (traitement.action or 'Action non spécifiée')[:80],
                        'message': message,
                        'due_date': delai_date.isoformat() if hasattr(delai_date, 'isoformat') else str(delai_date),
                        'priority': priority,
                        'action_url': action_url,
                        'nature_label': nature_label,
                        'type_action': type_action,
                        'delai_label': delai_label,
                        'pac_uuid': str(pac.uuid),
                        'traitement_uuid': str(traitement.uuid),
                        'notification_uuid': None,
                        'read_at': None,
                    })

                    # Enregistrer/mettre à jour la notification côté serveur (table parametre.Notification)
                    try:
                        content_type = ContentType.objects.get_for_model(TraitementPac)
                        notif, created = Notification.objects.get_or_create(
                            user=request.user,
                            content_type=content_type,
                            object_id=traitement.uuid,
                            source_app='pac',
                            notification_type='traitement',
                            defaults={
                                'title': title,
                                'message': message,
                                'action_url': action_url,
                                'priority': priority,
                                'due_date': delai_date,
                            },
                        )
                        if not created:
                            updated_fields = []
                            if notif.title != title:
                                notif.title = title
                                updated_fields.append('title')
                            if notif.message != message:
                                notif.message = message
                                updated_fields.append('message')
                            if notif.action_url != action_url:
                                notif.action_url = action_url
                                updated_fields.append('action_url')
                            if notif.priority != priority:
                                notif.priority = priority
                                updated_fields.append('priority')
                            if notif.due_date != delai_date:
                                notif.due_date = delai_date
                                updated_fields.append('due_date')
                            if updated_fields:
                                notif.save(update_fields=updated_fields + ['updated_at'])
                        notifications[-1]['notification_uuid'] = str(notif.uuid)
                        notifications[-1]['read_at'] = notif.read_at.isoformat() if notif.read_at else None
                    except Exception as notif_err:
                        logger.warning(f"[pac_upcoming_notifications] Notification get_or_create: {notif_err}")
            except Exception as e:
                logger.error(f"[pac_upcoming_notifications] Erreur lors du traitement du traitement {traitement.uuid}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # Trier par priorité (high en premier) puis par date
        notifications.sort(key=lambda x: (
            0 if x['priority'] == 'high' else 1 if x['priority'] == 'medium' else 2,
            x['due_date']
        ))
        
        logger.info(f"[pac_upcoming_notifications] {len(notifications)} notifications trouvées pour l'utilisateur {request.user.username}")
        
        return Response({
            'success': True,
            'notifications': notifications
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des notifications: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'notifications': [],
            'error': 'Erreur lors de la récupération des notifications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATISTIQUES PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_stats(request):
    """Statistiques des PACs de l'utilisateur connecté"""
    try:
        logger.info(f"[pac_stats] Début de la fonction pour l'utilisateur: {request.user.username}")
        scope = request.query_params.get('scope', 'tous')
        
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les PACs, avec filtre processus optionnel (?processus=UUID)
            pacs_base = Pac.objects.all()
            processus_filter = request.query_params.get('processus')
            if processus_filter and str(processus_filter).upper() != 'ALL':
                try:
                    from uuid import UUID
                    UUID(str(processus_filter))
                    pacs_base = pacs_base.filter(processus__uuid=processus_filter)
                except (ValueError, TypeError):
                    pass
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': {
                    'total_pacs': 0, 'pacs_valides': 0, 'pacs_non_valides': 0,
                    'pacs_avec_traitement': 0, 'pacs_sans_traitement': 0,
                    'pacs_avec_suivi': 0, 'pacs_sans_suivi': 0,
                    'total_traitements': 0, 'total_suivis': 0
                },
                'message': 'Aucune donnée de PAC trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Récupérer tous les PACs des processus de l'utilisateur
            pacs_base = Pac.objects.filter(processus__uuid__in=user_processus_uuids)
            # Filtre optionnel sur un seul processus (navigation multi-processus)
            processus_uuid_filter = request.query_params.get('processus_uuid', None)
            if processus_uuid_filter and str(processus_uuid_filter) in [str(u) for u in user_processus_uuids]:
                pacs_base = pacs_base.filter(processus__uuid=processus_uuid_filter)
        logger.info(f"[pac_stats] Queryset créé")
        # ========== FIN FILTRAGE ==========
        
        logger.info(f"[pac_stats] Nombre total de PACs de l'utilisateur: {pacs_base.count()}")

        # Filtrer selon le scope
        if scope == 'dernier':
            # Dernier PAC par processus = celui avec le num_amendement le plus élevé
            from django.db.models import Max
            last_uuids = []
            for proc_uuid in pacs_base.values_list('processus', flat=True).distinct():
                max_num = pacs_base.filter(processus=proc_uuid).aggregate(m=Max('num_amendement'))['m']
                last = pacs_base.filter(processus=proc_uuid, num_amendement=max_num).first()
                if last:
                    last_uuids.append(last.uuid)
            pacs_initiaux_base = pacs_base.filter(uuid__in=last_uuids)
        else:
            # Filtrer les PACs initiaux uniquement (num_amendement == 0)
            pacs_initiaux_base = pacs_base.filter(num_amendement=0)
        logger.info(f"[pac_stats] Nombre de PACs initiaux: {pacs_initiaux_base.count()}")
        
        total_pacs = pacs_initiaux_base.count()
        
        # Compter les PACs initiaux validés
        # Debug: Vérifier tous les PACs initiaux et leur statut de validation
        logger.info(f"[pac_stats] Vérification des PACs initiaux et leur statut de validation:")
        for pac in pacs_initiaux_base:
            # Recharger depuis la DB pour être sûr d'avoir la valeur à jour
            pac.refresh_from_db()
            logger.info(f"[pac_stats] PAC {pac.uuid}: is_validated={pac.is_validated} (type: {type(pac.is_validated).__name__}), validated_at={pac.validated_at}, validated_by={pac.validated_by}")
            
            # Vérifier aussi avec une requête directe
            pac_direct = Pac.objects.get(uuid=pac.uuid)
            logger.info(f"[pac_stats] PAC {pac.uuid} (requête directe): is_validated={pac_direct.is_validated} (type: {type(pac_direct.is_validated).__name__})")
        
        # Utiliser une requête directe sur la base filtrée
        # Un PAC est considéré comme validé si is_validated=True OU si validated_at/validated_by sont remplis
        from django.db.models import Q
        # Utiliser pacs_initiaux_base qui a déjà été filtré correctement (gère le cas super admin)
        pacs_valides_filter1 = pacs_initiaux_base.filter(
            Q(is_validated=True) | Q(validated_at__isnull=False) | Q(validated_by__isnull=False)
        ).count()
        logger.info(f"[pac_stats] Nombre de PACs initiaux validés (via filter avec Q): {pacs_valides_filter1}")
        
        # Essayer avec une requête qui vérifie explicitement que ce n'est pas False
        pacs_valides_filter2 = pacs_initiaux_base.exclude(is_validated=False).count()
        logger.info(f"[pac_stats] Nombre de PACs initiaux validés (via exclude is_validated=False): {pacs_valides_filter2}")
        
        # Compter aussi manuellement pour vérifier (plus fiable)
        # Un PAC est considéré comme validé si is_validated=True OU si validated_at/validated_by sont remplis
        pacs_valides_manual = 0
        for pac in pacs_initiaux_base:
            pac.refresh_from_db()
            # Vérifier explicitement que is_validated est True (booléen Python)
            # OU que validated_at/validated_by sont remplis (cas où is_validated n'a pas été mis à jour)
            is_validated = (
                pac.is_validated is True or 
                pac.is_validated == 1 or 
                (isinstance(pac.is_validated, bool) and pac.is_validated) or
                pac.validated_at is not None or
                pac.validated_by is not None
            )
            if is_validated:
                pacs_valides_manual += 1
                logger.info(f"[pac_stats] PAC {pac.uuid} considéré comme validé: is_validated={pac.is_validated}, validated_at={pac.validated_at}, validated_by={pac.validated_by}")
        logger.info(f"[pac_stats] Nombre de PACs initiaux validés (manuel): {pacs_valides_manual}")
        
        # Utiliser le comptage manuel (plus fiable que la requête filter)
        # Si les deux méthodes donnent des résultats différents, utiliser le manuel
        if pacs_valides_filter1 != pacs_valides_manual or pacs_valides_filter2 != pacs_valides_manual:
            logger.warning(f"[pac_stats] Incohérence détectée! filter1()={pacs_valides_filter1}, filter2()={pacs_valides_filter2}, manuel={pacs_valides_manual}. Utilisation du comptage manuel.")
            pacs_valides = pacs_valides_manual
        else:
            pacs_valides = pacs_valides_filter1
        
        # Récupérer les PACs initiaux avec leurs relations pour les boucles (pour les autres stats)
        pacs = pacs_initiaux_base.select_related(
            'processus', 'cree_par', 'annee'
        ).prefetch_related('details__traitement', 'details__traitement__suivi')
        
        # Compter les PACs avec traitement et suivi
        # Pour "Avec Traitement", compter TOUS les PACs (initiaux ET amendements) qui ont des traitements
        pacs_avec_traitement = 0
        pacs_avec_suivi = 0
        
        # Récupérer TOUS les PACs des processus de l'utilisateur (initiaux ET amendements) pour compter ceux avec traitement
        # Utiliser pacs_base qui a déjà été filtré correctement (gère le cas super admin)
        all_pacs = pacs_base.select_related(
            'processus', 'cree_par', 'annee'
        ).prefetch_related('details__traitement', 'details__traitement__suivi')
        
        logger.info(f"[pac_stats] Nombre total de PACs (initiaux + amendements): {all_pacs.count()}")
        
        # Compter les PACs avec traitement (tous types confondus)
        for pac in all_pacs:
            try:
                has_traitement = False
                has_suivi = False
                
                # Vérifier si le PAC a au moins un détail avec un traitement
                details = pac.details.all()
                for detail in details:
                    try:
                        if hasattr(detail, 'traitement') and detail.traitement:
                            has_traitement = True
                            # Vérifier si le traitement a un suivi
                            if hasattr(detail.traitement, 'suivi') and detail.traitement.suivi:
                                has_suivi = True
                                break
                    except Exception as e:
                        logger.warning(f"[pac_stats] Erreur lors de l'accès au traitement du détail {detail.uuid}: {e}")
                        continue
                
                # Compter une seule fois par PAC
                if has_traitement:
                    pacs_avec_traitement += 1
                    logger.info(f"[pac_stats] PAC {pac.uuid} (num_amendement={pac.num_amendement}) a un traitement")
                if has_suivi:
                    pacs_avec_suivi += 1
            except Exception as e:
                logger.error(f"[pac_stats] Erreur lors du traitement du PAC {pac.uuid}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        logger.info(f"[pac_stats] Nombre de PACs avec traitement (tous types): {pacs_avec_traitement}")
        logger.info(f"[pac_stats] Nombre de PACs avec suivi (tous types): {pacs_avec_suivi}")
        
        # Pour les autres stats, continuer avec les PACs initiaux uniquement
        
        # Analyser TOUS les traitements (pas seulement un par PAC)
        # Pour les traitements bientôt à terme, on continue à filtrer sur les PACs initiaux uniquement
        today = timezone.now().date()
        traitements_arrives_termes = 0
        traitements_bientot_termes = 0
        
        # Récupérer tous les traitements de l'utilisateur avec leurs délais de réalisation
        # Filtrer uniquement les traitements qui ont un details_pac et un pac initial associé
        # Utiliser pacs_initiaux_base pour obtenir les PACs initiaux, puis filtrer les traitements
        pacs_initiaux_uuids = list(pacs_initiaux_base.values_list('uuid', flat=True))
        
        # Si aucun PAC initial, les listes de traitements seront vides
        if not pacs_initiaux_uuids:
            traitements = TraitementPac.objects.none()
        else:
            traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                details_pac__pac__uuid__in=pacs_initiaux_uuids,
                delai_realisation__isnull=False
            ).select_related('details_pac', 'details_pac__pac')
        
        logger.info(f"[pac_stats] Nombre de traitements avec délai trouvés (PACs initiaux uniquement): {traitements.count()}")
        
        for traitement in traitements:
            try:
                # Vérifier que le traitement a bien un details_pac et un pac
                if not traitement.details_pac or not traitement.details_pac.pac:
                    continue
                    
                delai_date = traitement.delai_realisation
                if not delai_date:
                    continue
                
                # DateField retourne un objet date de Python, on peut l'utiliser directement
                # Si par erreur c'est un datetime, convertir en date
                try:
                    from datetime import datetime as dt_class
                    if isinstance(delai_date, dt_class):
                        delai_date = delai_date.date()
                except Exception:
                    # Si la conversion échoue, on continue avec la date telle quelle
                    pass
                
                # Traitement arrivé à terme (la date est passée)
                try:
                    if delai_date < today:
                        traitements_arrives_termes += 1
                        logger.debug(f"[pac_stats] Traitement arrivé à terme: {traitement.uuid}, délai: {delai_date}")
                    # Traitement bientôt à terme (dans les 7 prochains jours)
                    else:
                        diff_days = (delai_date - today).days
                        if 0 <= diff_days <= 7:
                            traitements_bientot_termes += 1
                            logger.debug(f"[pac_stats] Traitement bientôt à terme: {traitement.uuid}, délai: {delai_date}, jours restants: {diff_days}")
                except (TypeError, AttributeError) as e:
                    logger.warning(f"[pac_stats] Erreur lors de la comparaison de dates: {e}, type: {type(delai_date)}")
                    continue
            except Exception as e:
                logger.error(f"[pac_stats] Erreur lors du traitement du traitement {traitement.uuid}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # Compter le total des traitements de l'utilisateur pour les PACs initiaux uniquement
        # Filtrer uniquement les traitements qui ont un details_pac et un pac initial associé
        # Utiliser pacs_initiaux_uuids qui a déjà été créé plus haut
        if not pacs_initiaux_uuids:
            total_traitements = 0
        else:
            total_traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                details_pac__pac__uuid__in=pacs_initiaux_uuids
            ).count()
        
        # Compter le total des suivis de l'utilisateur pour les PACs initiaux uniquement
        # Filtrer uniquement les suivis qui ont un traitement avec details_pac et pac initial associé
        if not pacs_initiaux_uuids:
            total_suivis = 0
        else:
            total_suivis = PacSuivi.objects.filter(
                traitement__isnull=False,
                traitement__details_pac__isnull=False,
                traitement__details_pac__pac__uuid__in=pacs_initiaux_uuids
            ).count()
        
        logger.info(f"[pac_stats] Statistiques calculées: total_pacs={total_pacs}, pacs_valides={pacs_valides}, "
                   f"pacs_avec_traitement={pacs_avec_traitement}, pacs_avec_suivi={pacs_avec_suivi}, "
                   f"total_traitements={total_traitements}, total_suivis={total_suivis}, "
                   f"traitements_arrives_termes={traitements_arrives_termes}, traitements_bientot_termes={traitements_bientot_termes}")
        
        # Statistiques pour les graphiques
        stats = {
            'total_pacs': total_pacs,
            'pacs_valides': pacs_valides,
            'pacs_avec_traitement': pacs_avec_traitement,
            'pacs_avec_suivi': pacs_avec_suivi,
            'total_traitements': total_traitements,
            'total_suivis': total_suivis,
            'traitements_arrives_termes': traitements_arrives_termes,
            'traitements_bientot_termes': traitements_bientot_termes
        }
        
        logger.info(f"[pac_stats] Stats à retourner: {stats}")
        
        return Response({
            'success': True,
            'data': stats
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques PAC: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des statistiques PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_dashboard_stats(request):
    """
    Statistiques agrégées pour le dashboard — 4 requêtes DB au lieu de 51+.
    Remplace les appels séquentiels de dashboardSlice.js (N+1 sur PACs/traitements/suivis).
    """
    try:
        from parametre.models import NotificationSettings
        from datetime import timedelta

        notif_settings = NotificationSettings.get_solo()
        delai_jours = notif_settings.traitement_delai_notice_days
        today = timezone.now().date()
        date_limite = today + timedelta(days=delai_jours)

        # Security by Design : même logique de filtrage que pac_list
        user_processus_uuids = get_user_processus_list(request.user)

        if user_processus_uuids is None:
            pacs_qs = Pac.objects.filter(num_amendement=0)
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': {
                    'pac_count': 0,
                    'traitements_arrives_terme': 0,
                    'traitements_bientot_terme': 0,
                    'suivis_count': 0,
                    'delai_alerte_jours': delai_jours,
                }
            }, status=status.HTTP_200_OK)
        else:
            pacs_qs = Pac.objects.filter(
                processus__uuid__in=user_processus_uuids,
                num_amendement=0
            )

        pacs_uuids = list(pacs_qs.values_list('uuid', flat=True))
        pac_count = len(pacs_uuids)

        if not pacs_uuids:
            return Response({
                'success': True,
                'data': {
                    'pac_count': 0,
                    'traitements_arrives_terme': 0,
                    'traitements_bientot_terme': 0,
                    'suivis_count': 0,
                    'delai_alerte_jours': delai_jours,
                }
            }, status=status.HTTP_200_OK)

        base_filter = {
            'details_pac__isnull': False,
            'details_pac__pac__uuid__in': pacs_uuids,
            'delai_realisation__isnull': False,
        }

        traitements_arrives_terme = TraitementPac.objects.filter(
            **base_filter,
            delai_realisation__lt=today
        ).count()

        traitements_bientot_terme = TraitementPac.objects.filter(
            **base_filter,
            delai_realisation__gte=today,
            delai_realisation__lte=date_limite
        ).count()

        suivis_count = PacSuivi.objects.filter(
            traitement__isnull=False,
            traitement__details_pac__isnull=False,
            traitement__details_pac__pac__uuid__in=pacs_uuids,
        ).count()

        return Response({
            'success': True,
            'data': {
                'pac_count': pac_count,
                'traitements_arrives_terme': traitements_arrives_terme,
                'traitements_bientot_terme': traitements_bientot_terme,
                'suivis_count': suivis_count,
                'delai_alerte_jours': delai_jours,
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"[pac_dashboard_stats] Erreur: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors du calcul des statistiques dashboard'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_pac_previous_year(request):
    """
    Récupérer le dernier PAC (INITIAL, AMENDEMENT_1 ou AMENDEMENT_2) de l'année précédente
    pour un processus donné.

    Query params:
    - annee: UUID de l'année actuelle
    - processus: UUID du processus

    Retourne le dernier type de tableau (ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL)
    """
    try:
        from parametre.models import Annee

        annee_uuid = request.query_params.get('annee')
        processus_uuid = request.query_params.get('processus')

        if not annee_uuid or not processus_uuid:
            return Response({
                'error': 'Les paramètres annee et processus sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer l'année actuelle et calculer l'année précédente
        try:
            annee_actuelle = Annee.objects.get(uuid=annee_uuid)
            annee_precedente_valeur = annee_actuelle.annee - 1
            annee_precedente = Annee.objects.get(annee=annee_precedente_valeur)
        except Annee.DoesNotExist:
            logger.info(f"[get_last_pac_previous_year] Année précédente {annee_precedente_valeur if 'annee_precedente_valeur' in locals() else 'N/A'} non trouvée")
            return Response({
                'message': f'Aucune année {annee_precedente_valeur if "annee_precedente_valeur" in locals() else "précédente"} trouvée dans le système',
                'found': False,
                'data': None
            }, status=status.HTTP_200_OK)

        logger.info(f"[get_last_pac_previous_year] Recherche du dernier PAC pour processus={processus_uuid}, année={annee_precedente.annee}")

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce processus. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Récupérer le PAC avec le num_amendement le plus élevé pour l'année précédente
        pac = Pac.objects.filter(
            annee=annee_precedente,
            processus__uuid=processus_uuid,
        ).select_related('processus', 'annee', 'cree_par', 'validated_by').order_by('-num_amendement').first()

        if pac:
            logger.info(f"[get_last_pac_previous_year] PAC trouvé: {pac.uuid} (num_amendement={pac.num_amendement})")
            serializer = PacSerializer(pac)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun PAC trouvé pour l'année précédente (200 pour que le frontend ne voit pas 404)
        logger.info(f"[get_last_pac_previous_year] Aucun PAC trouvé pour l'année {annee_precedente.annee}")
        return Response({
            'message': f'Aucun Plan d\'Action de Conformité trouvé pour l\'année {annee_precedente.annee}',
            'found': False,
            'data': None
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier PAC de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération du PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
