"""
Service reCAPTCHA partagé
"""
import os
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class RecaptchaValidationError(Exception):
    """Exception levée lors d'une erreur de validation reCAPTCHA"""
    pass


class RecaptchaService:
    """Service pour la validation reCAPTCHA"""
    
    def __init__(self):
        self.secret_key = getattr(settings, 'RECAPTCHA_SECRET_KEY', None)
        self.site_key = getattr(settings, 'RECAPTCHA_SITE_KEY', None)
        self.min_score = getattr(settings, 'RECAPTCHA_MIN_SCORE', 0.5)
        self.verify_url = 'https://www.google.com/recaptcha/api/siteverify'
    
    def is_enabled(self):
        """Vérifier si reCAPTCHA est activé"""
        return self.secret_key is not None and self.site_key is not None
    
    def get_min_score(self):
        """Obtenir le score minimum requis"""
        return self.min_score
    
    def verify_token(self, token, remote_ip=None):
        """
        Vérifier un token reCAPTCHA
        
        Args:
            token: Token reCAPTCHA à vérifier
            remote_ip: Adresse IP du client (optionnel)
            
        Returns:
            tuple: (is_valid, data)
        """
        if not self.is_enabled():
            logger.warning("reCAPTCHA désactivé - validation ignorée")
            return True, {'score': 1.0, 'action': 'verify', 'success': True}
        
        try:
            data = {
                'secret': self.secret_key,
                'response': token,
            }
            
            if remote_ip:
                data['remoteip'] = remote_ip
            
            response = requests.post(self.verify_url, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get('success', False):
                error_codes = result.get('error-codes', [])
                logger.warning(f"reCAPTCHA validation échouée: {error_codes}")
                return False, {
                    'error': 'Validation reCAPTCHA échouée',
                    'error_codes': error_codes
                }
            
            score = result.get('score', 0.0)
            action = result.get('action', 'verify')
            
            if score < self.min_score:
                logger.warning(f"Score reCAPTCHA trop faible: {score} < {self.min_score}")
                return False, {
                    'error': f'Score trop faible: {score}',
                    'score': score,
                    'min_score': self.min_score
                }
            
            logger.info(f"reCAPTCHA validé avec succès: score={score}, action={action}")
            return True, {
                'score': score,
                'action': action,
                'success': True
            }
            
        except requests.RequestException as e:
            logger.error(f"Erreur lors de la vérification reCAPTCHA: {str(e)}")
            raise RecaptchaValidationError(f"Erreur de communication avec reCAPTCHA: {str(e)}")
        
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la validation reCAPTCHA: {str(e)}")
            raise RecaptchaValidationError(f"Erreur de validation: {str(e)}")


# Instance globale du service
recaptcha_service = RecaptchaService()
