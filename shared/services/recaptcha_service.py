"""
Shim de compatibilité — redirige vers parametre.services.recaptcha_service.
Le service reCAPTCHA est maintenant piloté depuis la DB via l'app parametre.
Les anciens imports (shared.services.recaptcha_service) continuent de fonctionner.
"""
from parametre.services.recaptcha_service import (  # noqa: F401
    RecaptchaService,
    RecaptchaValidationError,
    recaptcha_service,
)
