"""
Service de notifications Cartographie des Risques (CDR) — logique métier pure, sans couche HTTP.

Peut être appelé depuis :
  - un management command / scheduler  (send_cdr_reminders)
  - des tests unitaires sans request factory

Chaîne de données :
  CDR (is_validated, processus)
    └── DetailsCDR (numero_cdr)
        └── PlanAction (delai_realisation)
            └── PlanActionResponsable [0..N] (Direction / SousDirection / Service)

Utilisateurs notifiés : tous ceux qui ont un rôle actif sur le processus du CDR.
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from cartographie_risque.models import PlanAction
from parametre.models import Notification, NotificationPolicy, UserProcessusRole
from parametre.permissions import get_user_processus_list, is_super_admin
from parametre.utils.notification_policy import should_notify_pac as should_notify  # même logique deadline

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Requêtes
# ─────────────────────────────────────────────

def _get_plans_for_user(user):
    """
    Retourne le queryset PlanAction filtré selon les droits de l'utilisateur.
    - Super admin : tous les plans des CDR validés
    - Autres : plans des CDR validés sur leurs processus uniquement
    """
    user_processus_uuids = get_user_processus_list(user)

    base_qs = PlanAction.objects.filter(
        delai_realisation__isnull=False,
        details_cdr__cdr__is_validated=True,
    ).select_related(
        'details_cdr',
        'details_cdr__cdr',
        'details_cdr__cdr__processus',
    ).prefetch_related(
        'responsables',
    ).order_by('delai_realisation')

    if user_processus_uuids is None:
        # Super admin : tous les plans
        return base_qs
    if not user_processus_uuids:
        return PlanAction.objects.none()

    return base_qs.filter(
        details_cdr__cdr__processus__uuid__in=user_processus_uuids
    )


def _get_responsable_names(plan):
    """
    Retourne la liste des noms des responsables d'un plan d'action.
    Gère les trois types : Direction, SousDirection, Service.
    """
    names = []
    for par in plan.responsables.all():
        try:
            obj = par.responsable
            if obj and hasattr(obj, 'nom'):
                names.append(obj.nom)
        except Exception:
            pass
    return names


# ─────────────────────────────────────────────
# Construction du payload
# ─────────────────────────────────────────────

def _build_notification_payload(plan, today):
    """Construit le dict de notification pour un plan d'action donné."""
    days_until_due = (plan.delai_realisation - today).days
    priority = 'high' if days_until_due <= 2 else 'medium' if days_until_due <= 5 else 'low'

    numero_cdr = 'N/A'
    try:
        numero_cdr = plan.details_cdr.numero_cdr or 'N/A'
    except Exception:
        pass

    processus_nom = 'N/A'
    try:
        processus_nom = plan.details_cdr.cdr.processus.nom
    except Exception:
        pass

    action_resume = plan.actions_mesures[:50] + ('...' if len(plan.actions_mesures) > 50 else '')
    delai_label = (
        f"{plan.delai_realisation.strftime('%d/%m/%Y')} "
        f"({days_until_due} jour{'s' if days_until_due > 1 else ''})"
    )
    title = f"{numero_cdr} - Action : {action_resume}"
    message = f"Delai de realisation dans {days_until_due} jour{'s' if days_until_due > 1 else ''}"
    action_url = f'/cartographie-risque/plan-action/{plan.uuid}/show'

    return {
        'id': f'plan_action_{plan.uuid}',
        'type': 'plan_action',
        'title': title,
        'message': message,
        'due_date': plan.delai_realisation.isoformat(),
        'priority': priority,
        'action_url': action_url,
        'entity_id': str(plan.uuid),
        'notification_uuid': None,
        'read_at': None,
        'numero_cdr': numero_cdr,
        'processus': processus_nom,
        'responsables': _get_responsable_names(plan),
        'days_remaining': days_until_due,
        'delai_label': delai_label,
        # Champs internes pour _sync_notifications
        '_plan_uuid': plan.uuid,
        '_title': title,
        '_message': message,
        '_action_url': action_url,
        '_priority': priority,
        '_due_date': plan.delai_realisation,
    }


# ─────────────────────────────────────────────
# Synchronisation Notification en base (bulk)
# ─────────────────────────────────────────────

def _sync_notifications(user, payloads):
    """
    Crée ou met à jour les objets Notification en base pour l'utilisateur
    via bulk_create / bulk_update (pas de N+1).
    Enrichit chaque payload avec 'notification_uuid' et 'read_at'.
    """
    if not payloads:
        return

    content_type = ContentType.objects.get_for_model(PlanAction)
    plan_uuids = [p['_plan_uuid'] for p in payloads]

    existing = {
        n.object_id: n
        for n in Notification.objects.filter(
            user=user,
            content_type=content_type,
            object_id__in=plan_uuids,
            source_app='cartographie_risque',
            notification_type='plan_action',
        )
    }

    to_create = []
    to_update = []
    update_fields = {'title', 'message', 'action_url', 'priority', 'due_date', 'updated_at'}

    for payload in payloads:
        uuid = payload['_plan_uuid']
        title    = payload['_title']
        message  = payload['_message']
        action_url = payload['_action_url']
        priority = payload['_priority']
        due_date = payload['_due_date']

        if uuid in existing:
            notif = existing[uuid]
            changed = False
            if notif.title != title:       notif.title = title;             changed = True
            if notif.message != message:   notif.message = message;         changed = True
            if notif.action_url != action_url: notif.action_url = action_url; changed = True
            if notif.priority != priority: notif.priority = priority;       changed = True
            if notif.due_date != due_date: notif.due_date = due_date;       changed = True
            if changed:
                to_update.append(notif)
            payload['notification_uuid'] = str(notif.uuid)
            payload['read_at'] = notif.read_at.isoformat() if notif.read_at else None
        else:
            notif = Notification(
                user=user,
                content_type=content_type,
                object_id=uuid,
                source_app='cartographie_risque',
                notification_type='plan_action',
                title=title,
                message=message,
                action_url=action_url,
                priority=priority,
                due_date=due_date,
            )
            to_create.append((payload, notif))

    if to_create:
        new_notifs = Notification.objects.bulk_create([n for _, n in to_create])
        for (payload, _), new_notif in zip(to_create, new_notifs):
            payload['notification_uuid'] = str(new_notif.uuid)
            payload['read_at'] = None

    if to_update:
        Notification.objects.bulk_update(to_update, fields=list(update_fields))


# ─────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────

def get_cdr_notifications(user):
    """
    Retourne les notifications CDR pour un utilisateur donné.

    Structure retournée (compatible avec le pattern PAC/Dashboard) :
    {
        'notifications': [...],
        'total': int,
        'settings': {
            'days_before': int,
            'days_after': int,
            'reminder_frequency_days': int,
        }
    }

    Appelable directement sans requête HTTP.
    """
    today = timezone.now().date()
    policy = NotificationPolicy.get_for_scope(NotificationPolicy.SCOPE_CDR)

    plans = _get_plans_for_user(user)
    payloads = []

    for plan in plans:
        if not should_notify(plan, today, policy):
            continue
        payloads.append(_build_notification_payload(plan, today))

    try:
        _sync_notifications(user, payloads)
    except Exception:
        logger.exception(
            "Erreur lors de la synchronisation des notifications CDR pour %s", user
        )

    notifications = []
    for p in payloads:
        clean = {k: v for k, v in p.items() if not k.startswith('_')}
        notifications.append(clean)

    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    notifications.sort(key=lambda x: (priority_order.get(x['priority'], 3), x['due_date']))

    return {
        'notifications': notifications,
        'total': len(notifications),
        'settings': {
            'days_before': policy.days_before,
            'days_after': policy.days_after,
            'reminder_frequency_days': policy.reminder_frequency_days,
        },
    }
