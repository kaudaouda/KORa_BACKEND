"""
Service reCAPTCHA v3 — configuration pilotée depuis la base de données.
La configuration est lue à chaque appel (pas au démarrage), ce qui permet
d'activer/désactiver le service sans redémarrer Django.
"""
import hashlib
import logging
import requests
from django.conf import settings as django_settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'

ENDPOINT_FIELD = {
    'login': 'apply_to_login',
    'register': 'apply_to_register',
    'invitation': 'apply_to_invitation',
    'password_reset': 'apply_to_password_reset',
}


class RecaptchaValidationError(Exception):
    """Erreur de communication avec l'API Google reCAPTCHA."""
    pass


class RecaptchaService:
    """
    Service reCAPTCHA v3 piloté par RecaptchaConfig (DB).
    Fallback automatique sur les variables d'environnement si la DB est
    inaccessible ou si les champs sont vides.
    """

    def _get_config(self):
        """Charge la config depuis la DB. Retourne None si la DB est indisponible."""
        try:
            from parametre.models import RecaptchaConfig
            return RecaptchaConfig.get_config()
        except Exception as exc:
            logger.warning("RecaptchaConfig DB indisponible, fallback settings: %s", exc)
            return None

    def _effective_secret_key(self, config):
        if config:
            key = config.get_effective_secret_key()
            if key:
                return key
        return getattr(django_settings, 'RECAPTCHA_SECRET_KEY', None)

    def _effective_site_key(self, config):
        if config:
            key = config.get_effective_site_key()
            if key:
                return key
        return getattr(django_settings, 'RECAPTCHA_SITE_KEY', None)

    # ── API publique ────────────────────────────────────────────────────────

    def is_enabled(self):
        """True si le service est actif ET que les deux clés sont disponibles."""
        config = self._get_config()
        if config and not config.is_enabled:
            return False
        return bool(
            self._effective_secret_key(config) and self._effective_site_key(config)
        )

    def is_enabled_for(self, endpoint: str) -> bool:
        """
        True si reCAPTCHA est actif ET activé pour l'endpoint donné.
        endpoint: 'login' | 'register' | 'invitation' | 'password_reset'
        """
        if not self.is_enabled():
            return False
        config = self._get_config()
        if config is None:
            return True
        field = ENDPOINT_FIELD.get(endpoint)
        if field is None:
            return True
        return getattr(config, field, True)

    def get_min_score(self):
        config = self._get_config()
        if config:
            return config.min_score
        return float(getattr(django_settings, 'RECAPTCHA_MIN_SCORE', 0.5))

    def get_public_config(self):
        """Retourne le dict exposé au frontend (jamais la secret_key)."""
        config = self._get_config()
        return {
            'enabled': self.is_enabled(),
            'site_key': self._effective_site_key(config),
            'min_score': self.get_min_score(),
            'apply_to_login': getattr(config, 'apply_to_login', True) if config else True,
            'apply_to_register': getattr(config, 'apply_to_register', True) if config else True,
            'apply_to_invitation': getattr(config, 'apply_to_invitation', True) if config else True,
            'apply_to_password_reset': getattr(config, 'apply_to_password_reset', True) if config else True,
        }

    def verify_token(self, token: str, remote_ip: str = None, expected_action: str = None):
        """
        Vérifie un token reCAPTCHA v3 auprès de Google.

        Args:
            token:           Token généré par le frontend.
            remote_ip:       IP du client (transmise à Google pour scoring).
            expected_action: Nom d'action attendu (ex: 'login', 'register').
                             Si fourni, le service rejette les tokens générés
                             pour une autre action — empêche le replay cross-action.

        Returns:
            (True, data_dict)   si le token est valide, l'action correspond
                                et le score est suffisant.
            (False, error_dict) sinon.
        Raises:
            RecaptchaValidationError si la communication avec Google échoue.
        """
        config = self._get_config()
        secret_key = self._effective_secret_key(config)
        min_score = self.get_min_score()

        if not secret_key:
            logger.warning("reCAPTCHA désactivé — secret_key manquante, validation ignorée.")
            return True, {'score': 1.0, 'action': expected_action or 'verify', 'success': True}

        payload = {'secret': secret_key, 'response': token}
        if remote_ip:
            payload['remoteip'] = remote_ip

        try:
            resp = requests.post(VERIFY_URL, data=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
        except requests.RequestException as exc:
            logger.error("Erreur réseau reCAPTCHA: %s", exc)
            raise RecaptchaValidationError(f"Erreur de communication avec reCAPTCHA : {exc}")

        # 1 — Vérification du succès Google
        if not result.get('success', False):
            codes = result.get('error-codes', [])
            logger.warning("reCAPTCHA échoué: %s", codes)
            return False, {'error': 'Validation reCAPTCHA échouée', 'error_codes': codes}

        # 2 — Vérification de l'action (Security by Design)
        # Un token généré pour 'register' ne peut pas être utilisé sur 'login'.
        actual_action = result.get('action', '')
        if expected_action and actual_action != expected_action:
            logger.warning(
                "reCAPTCHA action mismatch: expected=%r actual=%r — token rejeté",
                expected_action, actual_action,
            )
            return False, {
                'error': 'Action reCAPTCHA invalide',
                'expected_action': expected_action,
                'actual_action': actual_action,
            }

        # 3 — Vérification du score
        score = result.get('score', 0.0)
        if score < min_score:
            logger.warning(
                "Score reCAPTCHA insuffisant: %.2f < %.2f (action=%s)",
                score, min_score, actual_action,
            )
            return False, {
                'error': 'Score de sécurité insuffisant',
                'score': score,
                'min_score': min_score,
            }

        # 4 — Anti-replay : un token Google v3 est valide 120 s.
        # On stocke son empreinte SHA-256 en cache dès qu'il est accepté.
        # Tout token déjà vu dans cette fenêtre est rejeté.
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        cache_key = f'recaptcha:replay:{token_hash}'
        if cache.get(cache_key):
            logger.warning(
                "reCAPTCHA replay détecté (action=%s score=%.2f) — token rejeté",
                actual_action, score,
            )
            return False, {'error': 'Token reCAPTCHA déjà utilisé', 'replay': True}

        cache.set(cache_key, True, timeout=120)

        logger.info(
            "reCAPTCHA validé: score=%.2f action=%s",
            score, actual_action,
        )
        return True, {'score': score, 'action': actual_action, 'success': True}


recaptcha_service = RecaptchaService()
