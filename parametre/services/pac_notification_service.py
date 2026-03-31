"""
Service de notifications PAC — logique métier pure, sans couche HTTP.

Peut être appelé depuis :
  - une view DRF  (parametre/views.py)
  - un management command / scheduler  (send_reminders_secure)
  - des tests unitaires sans request factory
"""
import logging
from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from pac.models import TraitementPac
from parametre.models import Notification, NotificationPolicy
from parametre.permissions import get_user_processus_list
from parametre.utils.notification_policy import should_notify_pac

logger = logging.getLogger(__name__)


def _get_traitements_for_user(user):
    """Retourne le queryset TraitementPac filtré selon les droits de l'utilisateur."""
    user_processus_uuids = get_user_processus_list(user)

    base_qs = TraitementPac.objects.filter(
        details_pac__isnull=False,
        delai_realisation__isnull=False,
    ).select_related(
        'details_pac',
        'details_pac__pac',
        'details_pac__pac__processus',
        'details_pac__nature',
        'type_action',
    ).order_by('delai_realisation')

    if user_processus_uuids is None:
        # Super admin : tous les traitements
        return base_qs
    if not user_processus_uuids:
        return TraitementPac.objects.none()

    return base_qs.filter(
        details_pac__pac__processus__uuid__in=user_processus_uuids
    )


def _build_notification_payload(traitement, today):
    """Construit le dict de notification pour un traitement donné."""
    days_until_due = (traitement.delai_realisation - today).days
    priority = 'high' if days_until_due <= 2 else 'medium' if days_until_due <= 5 else 'low'

    # Nature label
    nature_label = None
    try:
        nature = getattr(traitement.details_pac, 'nature', None)
        if nature:
            name = (nature.nom or '').strip().lower()
            if 'recommand' in name:
                nature_label = 'Recommandation'
            elif 'non' in name or 'dysfonction' in name:
                nature_label = 'Dysfonctionnement'
            else:
                nature_label = nature.nom
    except Exception:
        pass

    # Type d'action
    type_action = None
    try:
        if getattr(traitement, 'type_action', None):
            type_action = traitement.type_action.nom
    except Exception:
        pass

    numero_pac = (traitement.details_pac.numero_pac or 'N/A') if traitement.details_pac else 'N/A'
    delai_label = (
        f"{traitement.delai_realisation.strftime('%d/%m/%Y')} "
        f"({days_until_due} jour{'s' if days_until_due > 1 else ''})"
    )
    title = (
        f"{numero_pac} - Action : "
        f"{traitement.action[:50]}{'...' if len(traitement.action) > 50 else ''}"
    )
    message = f"Délai de réalisation dans {days_until_due} jour{'s' if days_until_due > 1 else ''}"
    action_url = f'/pac/traitement/{traitement.uuid}/show'

    return {
        'id': f'traitement_{traitement.uuid}',
        'type': 'traitement',
        'title': title,
        'message': message,
        'due_date': traitement.delai_realisation.isoformat(),
        'priority': priority,
        'action_url': action_url,
        'entity_id': str(traitement.uuid),
        'notification_uuid': None,
        'read_at': None,
        'nature_label': nature_label,
        'type_action': type_action,
        'days_remaining': days_until_due,
        'delai_label': delai_label,
        # Champs internes utilisés par _sync_notifications
        '_title': title,
        '_message': message,
        '_action_url': action_url,
        '_priority': priority,
        '_due_date': traitement.delai_realisation,
        '_traitement_uuid': traitement.uuid,
    }


def _sync_notifications(user, payloads):
    """
    Crée ou met à jour les objets Notification en base pour l'utilisateur,
    en utilisant bulk_create / bulk_update pour éviter le N+1.

    Enrichit chaque payload avec 'notification_uuid' et 'read_at'.
    """
    if not payloads:
        return

    content_type = ContentType.objects.get_for_model(TraitementPac)
    traitement_uuids = [p['_traitement_uuid'] for p in payloads]

    # 1 seule requête pour charger les notifications existantes
    existing = {
        n.object_id: n
        for n in Notification.objects.filter(
            user=user,
            content_type=content_type,
            object_id__in=traitement_uuids,
            source_app='pac',
            notification_type='traitement',
        )
    }

    to_create = []
    to_update = []
    updated_fields_set = {'title', 'message', 'action_url', 'priority', 'due_date', 'updated_at'}

    for payload in payloads:
        uuid = payload['_traitement_uuid']
        title = payload['_title']
        message = payload['_message']
        action_url = payload['_action_url']
        priority = payload['_priority']
        due_date = payload['_due_date']

        if uuid in existing:
            notif = existing[uuid]
            changed = False
            if notif.title != title:
                notif.title = title
                changed = True
            if notif.message != message:
                notif.message = message
                changed = True
            if notif.action_url != action_url:
                notif.action_url = action_url
                changed = True
            if notif.priority != priority:
                notif.priority = priority
                changed = True
            if notif.due_date != due_date:
                notif.due_date = due_date
                changed = True
            if changed:
                to_update.append(notif)
            payload['notification_uuid'] = str(notif.uuid)
            payload['read_at'] = notif.read_at.isoformat() if notif.read_at else None
        else:
            notif = Notification(
                user=user,
                content_type=content_type,
                object_id=uuid,
                source_app='pac',
                notification_type='traitement',
                title=title,
                message=message,
                action_url=action_url,
                priority=priority,
                due_date=due_date,
            )
            to_create.append((payload, notif))

    # Bulk create
    if to_create:
        new_notifs = Notification.objects.bulk_create([n for _, n in to_create])
        for (payload, _), new_notif in zip(to_create, new_notifs):
            payload['notification_uuid'] = str(new_notif.uuid)
            payload['read_at'] = None

    # Bulk update
    if to_update:
        Notification.objects.bulk_update(to_update, fields=list(updated_fields_set))


def get_pac_notifications(user):
    """
    Point d'entrée principal du service.

    Retourne un dict compatible avec la réponse de l'ancienne view :
      {
        'notifications': [...],
        'total': int,
        'settings': {...},
      }

    Peut être appelé directement sans requête HTTP.
    """
    today = timezone.now().date()
    policy = NotificationPolicy.get_for_scope(NotificationPolicy.SCOPE_PAC)

    traitements = _get_traitements_for_user(user)
    payloads = []

    for traitement in traitements:
        if not traitement.details_pac or not traitement.details_pac.pac:
            continue
        if not should_notify_pac(traitement, today, policy):
            continue
        payloads.append(_build_notification_payload(traitement, today))

    try:
        _sync_notifications(user, payloads)
    except Exception:
        logger.exception("Erreur lors de la synchronisation des notifications PAC pour %s", user)

    # Nettoyer les champs internes avant de retourner
    notifications = []
    for p in payloads:
        clean = {k: v for k, v in p.items() if not k.startswith('_')}
        notifications.append(clean)

    # Trier par priorité puis date
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    notifications.sort(key=lambda x: (priority_order.get(x['priority'], 3), x['due_date']))

    return {
        'notifications': notifications,
        'total': len(notifications),
        'settings': {
            'traitement_delai_notice_days': policy.days_before,
            'traitement_reminder_frequency_days': policy.reminder_frequency_days,
            'traitement_days_after_deadline': policy.days_after,
        },
    }
