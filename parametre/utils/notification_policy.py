from datetime import date


def _normalize_date(d):
  """
  Convertit un datetime en date si nécessaire, laisse les dates inchangées.
  Retourne None si la valeur est invalide.
  """
  if d is None:
    return None
  if hasattr(d, "date") and not isinstance(d, date):
    try:
      return d.date()
    except Exception:
      return None
  return d


def should_notify_pac(traitement, today, policy):
  """
  Détermine si un traitement PAC doit être notifié (email / UI) à la date `today`
  en fonction de la politique fournie.

  Règle métier :
  - Avant échéance : on notifie si 0 <= diff_days <= days_before
  - Après échéance : on notifie si:
      days_since_deadline >= days_after
      ET (days_since_deadline - days_after) % reminder_frequency_days == 0
  """
  delai = _normalize_date(getattr(traitement, "delai_realisation", None))
  if delai is None or today is None:
    return False

  # S'assurer que today est une date
  today = _normalize_date(today)
  if today is None:
    return False

  # Différence en jours (positive = encore à venir, négative = en retard)
  try:
    diff_days = (delai - today).days
  except Exception:
    return False

  days_before = max(0, getattr(policy, "days_before", 0))
  days_after = max(0, getattr(policy, "days_after", 0))
  reminder_frequency = max(1, getattr(policy, "reminder_frequency_days", 1))

  # Avant échéance : fenêtre [0 ; days_before]
  if diff_days >= 0:
    return diff_days <= days_before

  # Après échéance
  days_since_deadline = -diff_days  # today - delai
  if days_since_deadline < days_after:
    return False

  # Première relance dès que days_since_deadline >= days_after,
  # puis toutes les `reminder_frequency` jours
  return (days_since_deadline - days_after) % reminder_frequency == 0


def should_notify_dashboard(periode_end_date, today, policy):
  """
  Détermine si un indicateur de tableau de bord doit être notifié à la date `today`
  en fonction de la politique fournie.

  Retourne:
    - ('before', message) si on est dans la fenêtre avant fin de période
    - ('after', message) si on est en phase de relance après fin de période
    - (None, None) sinon
  """
  end_date = _normalize_date(periode_end_date)
  if end_date is None or today is None:
    return (None, None)

  today = _normalize_date(today)
  if today is None:
    return (None, None)

  days_before = max(0, getattr(policy, "days_before", 0))
  days_after = max(0, getattr(policy, "days_after", 0))
  reminder_frequency = max(1, getattr(policy, "reminder_frequency_days", 1))

  # Fenêtre d'alerte avant la fin de période
  from datetime import timedelta

  alert_start = end_date - timedelta(days=days_before)

  if alert_start <= today <= end_date:
    days_until_end = (end_date - today).days
    return (
      "before",
      f"La période se termine dans {days_until_end} jour(s)",
    )

  # Relances après la fin de période
  if today > end_date:
    days_since_end = (today - end_date).days
    if days_since_end >= days_after:
      # Première relance à days_after, puis toutes les reminder_frequency_days
      if (days_since_end - days_after) % reminder_frequency == 0:
        return (
          "after",
          f"La période est terminée depuis {days_since_end} jour(s)",
        )

  return (None, None)

