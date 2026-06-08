"""
Service pour l'authentification à deux facteurs par email.
"""
import logging
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

from parametre.models import TwoFactorConfig, EmailOTP
from parametre.utils.email_config import load_email_settings_into_django

logger = logging.getLogger(__name__)

# Durées lisibles pour l'affichage dans l'email
def _lifetime_display(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} seconde{'s' if seconds > 1 else ''}"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} heure{'s' if hours > 1 else ''}"
    days = seconds // 86400
    return f"{days} jour{'s' if days > 1 else ''}"


class TwoFactorService:
    """Gère la génération, l'envoi et la vérification des codes OTP 2FA."""

    @staticmethod
    def is_enabled() -> bool:
        return TwoFactorConfig.get_config().is_enabled

    @staticmethod
    def send_otp(user, ip_address: str) -> EmailOTP:
        """
        Génère un code OTP pour l'utilisateur, l'envoie par email,
        et retourne l'instance EmailOTP créée.
        """
        config = TwoFactorConfig.get_config()
        otp, raw_code = EmailOTP.create_for_user(user, ip_address, config)

        try:
            TwoFactorService._send_otp_email(user, raw_code, ip_address, config)
        except Exception as exc:
            logger.error(
                "Échec envoi OTP à %s : %s",
                user.email,
                exc,
                exc_info=True,
            )
            # On lève pour que la vue retourne une erreur claire
            raise

        logger.info("OTP envoyé à %s (session=%s)", user.email, otp.session_key)
        return otp

    @staticmethod
    def verify_otp(session_key: str, raw_code: str) -> tuple[bool, str, object | None]:
        """
        Vérifie le code OTP pour une session donnée.

        Retourne (success, error_message, user_or_none).
        """
        try:
            otp = EmailOTP.objects.select_related('user').get(session_key=session_key)
        except EmailOTP.DoesNotExist:
            return False, 'Session invalide ou expirée.', None

        if otp.is_used:
            return False, 'Ce code a déjà été utilisé.', None

        if otp.is_expired:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            return False, 'Ce code a expiré. Reconnectez-vous pour en obtenir un nouveau.', None

        config = TwoFactorConfig.get_config()
        if otp.attempts >= config.max_attempts:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            return False, 'Nombre de tentatives dépassé. Reconnectez-vous pour obtenir un nouveau code.', None

        if not otp.check_code(raw_code):
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            remaining = config.max_attempts - otp.attempts
            return False, f'Code incorrect. {remaining} tentative{"s" if remaining > 1 else ""} restante{"s" if remaining > 1 else ""}.', None

        # Code correct → invalider l'OTP
        otp.is_used = True
        otp.save(update_fields=['is_used'])

        logger.info("OTP vérifié avec succès pour %s (session=%s)", otp.user.email, session_key)
        return True, '', otp.user

    @staticmethod
    def _send_otp_email(user, raw_code: str, ip_address: str, config: TwoFactorConfig):
        """Envoie l'email contenant le code OTP."""
        load_email_settings_into_django()

        lifetime_display = _lifetime_display(config.otp_lifetime_seconds)
        timestamp = timezone.localtime(timezone.now()).strftime('%d/%m/%Y à %H:%M')

        context = {
            'user_first_name': user.first_name,
            'user_username': user.username,
            'otp_code': raw_code,
            'lifetime_display': lifetime_display,
            'ip_address': ip_address,
            'timestamp': timestamp,
        }

        subject = 'KORA — Votre code de vérification'
        html_body = render_to_string('emails/two_factor_otp_email.html', context)
        txt_body = render_to_string('emails/two_factor_otp_email.txt', context)

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'KORA <noreply@kora.local>')

        send_mail(
            subject=subject,
            message=txt_body,
            from_email=from_email,
            recipient_list=[user.email],
            html_message=html_body,
            fail_silently=False,
        )
