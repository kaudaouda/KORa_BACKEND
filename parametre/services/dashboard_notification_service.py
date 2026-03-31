"""
Service de notifications Dashboard — logique métier pure, sans couche HTTP.

Peut être appelé depuis :
  - un management command / scheduler  (send_dashboard_reminders)
  - des tests unitaires sans request factory
"""
import hashlib
import logging
from datetime import date, timedelta

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from dashboard.models import Indicateur
from parametre.models import ReminderEmailLog, NotificationPolicy
from parametre.utils.notification_policy import should_notify_dashboard

logger = logging.getLogger(__name__)


def get_periods_to_check(frequence_nom):
    """Retourne les dates de fin de période à vérifier selon la fréquence."""
    today = timezone.now().date()

    if frequence_nom == 'Trimestrielle':
        return [
            (date(today.year, 3, 31),  '1er Trimestre'),
            (date(today.year, 6, 30),  '2ème Trimestre'),
            (date(today.year, 9, 30),  '3ème Trimestre'),
            (date(today.year, 12, 31), '4ème Trimestre'),
        ]
    if frequence_nom == 'Semestrielle':
        return [
            (date(today.year, 6, 30),  '1er Semestre'),
            (date(today.year, 12, 31), '2ème Semestre'),
        ]
    if frequence_nom == 'Annuelle':
        return [
            (date(today.year, 12, 31), 'Année'),
        ]
    return []


def get_users_to_notify(indicateur):
    """Retourne la liste des utilisateurs à notifier pour un indicateur."""
    try:
        tableau_bord = indicateur.objective_id.tableau_bord
        if tableau_bord and tableau_bord.cree_par:
            return [tableau_bord.cree_par]
    except Exception:
        pass
    return []


def build_email_context(user, indicateur, periode_name, periode_end_date, message):
    """Construit le contexte pour les templates email dashboard."""
    objective = indicateur.objective_id
    frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')
    return {
        'user_name': user.first_name or user.username,
        'objective_number': objective.number,
        'objective_libelle': objective.libelle,
        'indicateur_libelle': indicateur.libelle,
        'frequence': indicateur.frequence_id.nom,
        'periode_name': periode_name,
        'periode_end_date': periode_end_date.strftime('%d/%m/%Y'),
        'message': message,
        'dashboard_url': f"{frontend_base}/dashboard",
    }


def get_dashboard_notifications():
    """
    Point d'entrée principal du service.

    Retourne un générateur de tuples (user, indicateur, periode_name,
    periode_end_date, notification_type, message, context_hash) pour chaque
    notification à envoyer.

    Appelable directement sans requête HTTP.
    """
    policy = NotificationPolicy.get_for_scope(NotificationPolicy.SCOPE_DASHBOARD)
    today = timezone.now().date()

    indicateurs = Indicateur.objects.select_related(
        'frequence_id',
        'objective_id',
        'objective_id__tableau_bord',
        'objective_id__tableau_bord__cree_par',
    ).all()

    for indicateur in indicateurs:
        if not indicateur.frequence_id:
            continue

        for periode_date, periode_name in get_periods_to_check(indicateur.frequence_id.nom):
            notification_type, message = should_notify_dashboard(periode_date, today, policy)
            if not notification_type:
                continue

            for user in get_users_to_notify(indicateur):
                context_key = (
                    f"{user.email}:{indicateur.uuid}:{periode_name}"
                    f":{periode_date}:{notification_type}"
                )
                context_hash = hashlib.sha256(context_key.encode('utf-8')).hexdigest()

                yield user, indicateur, periode_name, periode_date, notification_type, message, context_hash


def is_already_sent_today(context_hash):
    """Vérifie si cette notification a déjà été envoyée aujourd'hui."""
    return ReminderEmailLog.objects.filter(
        context_hash=context_hash,
        sent_at__date=timezone.now().date(),
        success=True,
    ).exists()


def build_subject(notification_type, indicateur):
    """Construit le sujet email sans emoji (compatible tous encodages)."""
    prefix = "RAPPEL" if notification_type == 'before' else "RELANCE"
    return f"KORA - {prefix} Indicateur {indicateur.objective_id.number}"


def render_email_bodies(user, indicateur, periode_name, periode_end_date, message):
    """Rend les templates HTML et texte."""
    context = build_email_context(user, indicateur, periode_name, periode_end_date, message)
    html_body = render_to_string('emails/dashboard_reminder_email.html', context)
    text_body = render_to_string('emails/dashboard_reminder_email.txt', context)
    return html_body, text_body
