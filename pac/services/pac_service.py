"""
Services métier PAC — logique pure, sans couche HTTP.

Peut être appelé depuis :
  - une view DRF
  - un management command / scheduler
  - des tests unitaires sans request factory
"""
import logging
import traceback
from datetime import datetime as dt_class

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from pac.models import TraitementPac
from parametre.models import Notification
from parametre.permissions import get_user_processus_list

logger = logging.getLogger(__name__)


def check_pac_completude(pac):
    """
    Vérifie que tous les champs obligatoires du PAC, de ses détails et de leurs
    traitements sont renseignés avant validation.

    Returns:
        None si tout est OK, sinon un message d'erreur (str).
    """
    details = pac.details.select_related(
        'dysfonctionnement_recommandation', 'nature', 'categorie', 'source',
        'traitement', 'traitement__type_action', 'traitement__responsable_direction',
    ).prefetch_related('traitement__responsables_directions').all()

    if not details.exists():
        return "Le tableau doit avoir au moins une ligne avant d'être validé."

    for detail in details:
        if not detail.libelle or not detail.libelle.strip():
            return "Le champ « Libellé » est obligatoire pour toutes les lignes."
        if not detail.dysfonctionnement_recommandation_id:
            return "Le champ « Dysfonctionnement / Recommandation » est obligatoire pour toutes les lignes."
        if not detail.nature_id:
            return "Le champ « Nature » est obligatoire pour toutes les lignes."
        if not detail.categorie_id:
            return "Le champ « Catégorie » est obligatoire pour toutes les lignes."
        if not detail.source_id:
            return "Le champ « Source » est obligatoire pour toutes les lignes."
        if not detail.periode_de_realisation:
            return "Le champ « Période de réalisation » est obligatoire pour toutes les lignes."

        if not hasattr(detail, 'traitement') or not detail.traitement:
            return "Toutes les lignes doivent avoir un traitement (Actions) avant validation."

        t = detail.traitement
        if not t.action or not t.action.strip():
            return "Le champ « Actions » est obligatoire pour tous les traitements."
        if not t.type_action_id:
            return "Le champ « Type d'action » est obligatoire pour tous les traitements."

        has_responsable = (
            t.responsable_direction_id
            or t.responsable_sous_direction_id
            or t.responsables_directions.exists()
            or t.responsables_sous_directions.exists()
        )
        if not has_responsable:
            return "Au moins un « Responsable » est obligatoire pour tous les traitements."

        if not t.delai_realisation:
            return "Le champ « Délai de réalisation » est obligatoire pour tous les traitements."

    return None


def get_upcoming_notifications_data(user):
    """
    Retourne les traitements PAC bientôt à terme pour l'utilisateur.
    Crée/met à jour les enregistrements Notification en base comme effet de bord.

    Returns:
        dict avec les clés 'success', 'notifications' (list triée par priorité/date),
        et optionnellement 'message'/'count'/'data' pour le cas liste vide.
    """
    today = timezone.now().date()

    user_processus_uuids = get_user_processus_list(user)

    if user_processus_uuids is None:
        # Super admin : toutes les notifications sans filtre de processus
        traitements = TraitementPac.objects.filter(
            details_pac__isnull=False,
            delai_realisation__isnull=False,
        ).select_related(
            'details_pac',
            'details_pac__pac',
            'details_pac__pac__processus',
            'details_pac__nature',
            'type_action',
        ).prefetch_related(
            'responsables_directions',
            'responsables_sous_directions',
        )
    elif not user_processus_uuids:
        return {
            'success': True,
            'data': [],
            'count': 0,
            'notifications': [],
            'message': 'Aucune notification trouvée pour vos processus attribués.',
        }
    else:
        traitements = TraitementPac.objects.filter(
            details_pac__isnull=False,
            details_pac__pac__processus__uuid__in=user_processus_uuids,
            delai_realisation__isnull=False,
        ).select_related(
            'details_pac',
            'details_pac__pac',
            'details_pac__pac__processus',
            'details_pac__nature',
            'type_action',
        ).prefetch_related(
            'responsables_directions',
            'responsables_sous_directions',
        )

    notifications = []
    content_type = ContentType.objects.get_for_model(TraitementPac)

    for traitement in traitements:
        try:
            if not traitement.details_pac or not traitement.details_pac.pac:
                continue

            delai_date = traitement.delai_realisation
            if not delai_date:
                continue

            if isinstance(delai_date, dt_class):
                delai_date = delai_date.date()

            try:
                diff_days = (delai_date - today).days
            except (TypeError, AttributeError) as e:
                logger.warning("[get_upcoming_notifications_data] Calcul diff jours: %s", e)
                continue

            if diff_days > 7:
                continue

            if diff_days < 0:
                priority = 'high'
                delai_label = f'En retard de {abs(diff_days)} jour{"s" if abs(diff_days) > 1 else ""}'
            elif diff_days == 0:
                priority = 'high'
                delai_label = "Échéance aujourd'hui"
            elif diff_days <= 3:
                priority = 'high'
                delai_label = f'Échéance dans {diff_days} jour{"s" if diff_days > 1 else ""}'
            else:
                priority = 'medium'
                delai_label = f'Échéance dans {diff_days} jours'

            pac = traitement.details_pac.pac
            numero_pac = traitement.details_pac.numero_pac or f'PAC-{pac.uuid}'
            raw_action = traitement.action or ''
            action_title = raw_action[:50] + ('...' if len(raw_action) > 50 else '')
            if not action_title:
                action_title = 'Action non spécifiée'

            title = f'{numero_pac} - Action : {action_title}'
            action_url = f'/pac/{pac.uuid}'
            message = f'Délai de réalisation {delai_label}'
            nature_label = traitement.details_pac.nature.nom if traitement.details_pac.nature else None
            type_action = traitement.type_action.nom if traitement.type_action else None

            entry = {
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
            }
            notifications.append(entry)

            # Upsert en table Notification
            try:
                notif, created = Notification.objects.get_or_create(
                    user=user,
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
                    for field, value in [
                        ('title', title),
                        ('message', message),
                        ('action_url', action_url),
                        ('priority', priority),
                        ('due_date', delai_date),
                    ]:
                        if getattr(notif, field) != value:
                            setattr(notif, field, value)
                            updated_fields.append(field)
                    if updated_fields:
                        notif.save(update_fields=updated_fields + ['updated_at'])
                entry['notification_uuid'] = str(notif.uuid)
                entry['read_at'] = notif.read_at.isoformat() if notif.read_at else None
            except Exception as notif_err:
                logger.warning("[get_upcoming_notifications_data] Notification upsert: %s", notif_err)

        except Exception as e:
            logger.error(
                "[get_upcoming_notifications_data] Erreur traitement %s: %s",
                traitement.uuid, e,
            )
            logger.error(traceback.format_exc())
            continue

    notifications.sort(key=lambda x: (
        0 if x['priority'] == 'high' else 1 if x['priority'] == 'medium' else 2,
        x['due_date'],
    ))

    logger.info(
        "[get_upcoming_notifications_data] %d notifications pour %s",
        len(notifications), user.username,
    )
    return {'success': True, 'notifications': notifications}
