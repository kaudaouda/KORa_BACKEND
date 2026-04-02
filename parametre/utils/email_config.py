import logging
from django.conf import settings

from parametre.models import EmailSettings
from .email_security import SecureEmailLogger

logger = logging.getLogger(__name__)


def load_email_settings_into_django() -> bool:
    """
    Charge la configuration email depuis EmailSettings dans les settings Django.

    Retourne True si la configuration est complète et appliquée, False sinon.
    """
    try:
        email_settings = EmailSettings.get_solo()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de EmailSettings: {e}")
        return False

    config = email_settings.get_email_config()

    # Vérifier que la configuration est complète (host user + mot de passe)
    if not config.get("EMAIL_HOST_USER") or not config.get("EMAIL_HOST_PASSWORD"):
        logger.warning("Configuration email incomplète dans EmailSettings (EMAIL_HOST_USER ou mot de passe manquant).")
        SecureEmailLogger.log_security_event(
            "email_settings_incomplete",
            {"reason": "missing_user_or_password"}
        )
        return False

    # Appliquer la configuration au runtime Django
    for key, value in config.items():
        setattr(settings, key, value)

    logger.info(
        f"Configuration email chargée depuis EmailSettings pour l'utilisateur SMTP "
        f"{SecureEmailLogger.mask_email(config.get('EMAIL_HOST_USER', ''))}"
    )
    return True

