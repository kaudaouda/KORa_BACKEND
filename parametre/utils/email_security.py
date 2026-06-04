"""
Utilitaires de sécurité pour le système d'email
Security by Design - Chiffrement, validation, sanitization
"""
import re
import html
import hashlib
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class EmailPasswordEncryption:
    """
    Gestion du chiffrement des mots de passe SMTP
    Security by Design : Les mots de passe ne sont JAMAIS stockés en clair
    """
    
    @staticmethod
    def get_encryption_key() -> bytes:
        """
        Récupère la clé de chiffrement depuis les settings
        La clé doit être stockée dans les variables d'environnement
        """
        key = getattr(settings, 'EMAIL_ENCRYPTION_KEY', None)
        if not key:
            # Générer une clé temporaire (À NE PAS FAIRE EN PRODUCTION)
            logger.warning("⚠️ EMAIL_ENCRYPTION_KEY non définie ! Génération d'une clé temporaire.")
            logger.warning("⚠️ Ajoutez EMAIL_ENCRYPTION_KEY dans vos variables d'environnement !")
            key = Fernet.generate_key()
        
        if isinstance(key, str):
            key = key.encode()
        
        return key
    
    @staticmethod
    def encrypt_password(password: str) -> str:
        """
        Chiffre un mot de passe
        
        Args:
            password: Mot de passe en clair
            
        Returns:
            Mot de passe chiffré (string)
        """
        if not password:
            return ''
        
        try:
            fernet = Fernet(EmailPasswordEncryption.get_encryption_key())
            encrypted = fernet.encrypt(password.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("Erreur lors du chiffrement du mot de passe: %s", e)
            raise ValueError("Impossible de chiffrer le mot de passe")
    
    @staticmethod
    def decrypt_password(encrypted_password: str) -> str:
        """
        Déchiffre un mot de passe
        
        Args:
            encrypted_password: Mot de passe chiffré
            
        Returns:
            Mot de passe en clair (string)
        """
        if not encrypted_password:
            return ''
        
        try:
            fernet = Fernet(EmailPasswordEncryption.get_encryption_key())
            decrypted = fernet.decrypt(encrypted_password.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error("Erreur lors du déchiffrement du mot de passe")
            raise ValueError("Impossible de déchiffrer le mot de passe")


class EmailValidator:
    """
    Validation stricte des adresses email
    Security by Design : Validation en profondeur
    """
    
    # Regex stricte pour les emails (RFC 5322 simplifié)
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )
    
    # Domaines suspects pour le spam
    SUSPICIOUS_DOMAINS = [
        'temp-mail.org', 'guerrillamail.com', '10minutemail.com',
        'mailinator.com', 'trashmail.com', 'fakeinbox.com'
    ]
    
    @classmethod
    def is_valid_email(cls, email: str) -> bool:
        """
        Vérifie qu'un email est valide
        
        Args:
            email: Adresse email à valider
            
        Returns:
            True si valide, False sinon
        """
        if not email or not isinstance(email, str):
            return False
        
        email = email.strip().lower()
        
        # Vérifier la longueur
        if len(email) > 254 or len(email) < 3:
            return False
        
        # Vérifier le format avec regex
        if not cls.EMAIL_REGEX.match(email):
            return False
        
        # Vérifier que le domaine n'est pas suspect
        domain = email.split('@')[-1]
        if domain in cls.SUSPICIOUS_DOMAINS:
            logger.warning("Domaine suspect détecté : %s", domain)
            return False
        
        return True
    
    @classmethod
    def sanitize_email_list(cls, emails: list) -> list:
        """
        Filtre et valide une liste d'emails
        
        Args:
            emails: Liste d'emails à valider
            
        Returns:
            Liste d'emails valides uniquement
        """
        valid_emails = []
        for email in emails:
            if cls.is_valid_email(email):
                valid_emails.append(email.strip().lower())
            else:
                logger.warning("Email invalide filtré : %s", email)
        
        return list(set(valid_emails))  # Dédupliquer


class EmailContentSanitizer:
    """
    Sanitization du contenu des emails
    Security by Design : Prévention XSS et injection
    """
    
    # Tags HTML autorisés dans les emails
    ALLOWED_HTML_TAGS = ['p', 'br', 'strong', 'em', 'u', 'a', 'h1', 'h2', 'h3', 'div', 'span']
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Échappe le HTML pour prévenir les injections
        
        Args:
            text: Texte à sanitizer
            
        Returns:
            Texte sécurisé
        """
        if not text:
            return ''
        
        return html.escape(str(text))
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """
        Valide et sécurise une URL
        Security by Design : Validation stricte sans double encodage
        
        Args:
            url: URL à valider
            
        Returns:
            URL sécurisée (non échappée car sera utilisée dans href où Django template gère l'encodage)
        """
        if not url:
            return ''
        
        url = str(url).strip()
        
        # Vérifier que l'URL est sécurisée (protocole autorisé uniquement)
        if not url.startswith(('http://', 'https://', '/')):
            logger.warning("URL suspecte : %s", url)
            return ''
        
        # Ne PAS utiliser html.escape() ici car :
        # 1. L'URL sera utilisée dans un attribut href où Django template gère l'encodage automatiquement
        # 2. html.escape() transformerait & en &amp; ce qui créerait une URL invalide
        # 3. La validation du protocole (http/https) est suffisante pour la sécurité
        
        # Vérifier qu'il n'y a pas de caractères dangereux (javascript:, data:, etc.)
        url_lower = url.lower()
        dangerous_protocols = ['javascript:', 'data:', 'vbscript:', 'file:']
        for protocol in dangerous_protocols:
            if protocol in url_lower:
                logger.warning("URL avec protocole dangereux détecté : %s", url)
                return ''
        
        return url
    
    @staticmethod
    def sanitize_subject(subject: str, max_length: int = 255) -> str:
        """
        Sécurise le sujet d'un email
        
        Args:
            subject: Sujet à sanitizer
            max_length: Longueur maximale
            
        Returns:
            Sujet sécurisé
        """
        if not subject:
            return 'KORA - Notification'
        
        # Supprimer les caractères de contrôle
        sanitized = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', str(subject))
        
        # Limiter la longueur
        sanitized = sanitized[:max_length]
        
        return sanitized.strip()


class EmailRateLimiter:
    """
    Rate limiting pour les envois d'emails
    Security by Design : Prévention du spam et DoS
    """
    
    # Limites par défaut
    MAX_EMAILS_PER_HOUR_USER = 100
    MAX_EMAILS_PER_DAY_GLOBAL = 1000
    MAX_TEST_EMAILS_PER_MINUTE = 1
    
    @classmethod
    def check_user_limit(cls, user_id: int) -> bool:
        """
        Vérifie si l'utilisateur peut envoyer un email
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            True si autorisé, False sinon
        """
        cache_key = f'email_rate_limit_user_{user_id}'
        count = cache.get(cache_key, 0)
        
        if count >= cls.MAX_EMAILS_PER_HOUR_USER:
            logger.warning("Limite d'emails dépassée pour l'utilisateur %s", user_id)
            return False
        
        # Incrémenter le compteur (expire dans 1 heure)
        cache.set(cache_key, count + 1, 3600)
        return True
    
    @classmethod
    def check_global_limit(cls) -> bool:
        """
        Vérifie la limite globale d'emails
        
        Returns:
            True si autorisé, False sinon
        """
        cache_key = 'email_rate_limit_global_day'
        count = cache.get(cache_key, 0)
        
        if count >= cls.MAX_EMAILS_PER_DAY_GLOBAL:
            logger.error("🚨 Limite globale d'emails dépassée !")
            return False
        
        # Incrémenter le compteur (expire dans 24 heures)
        cache.set(cache_key, count + 1, 86400)
        return True
    
    @classmethod
    def check_test_email_limit(cls, user_id: int) -> bool:
        """
        Vérifie la limite pour les emails de test
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            True si autorisé, False sinon
        """
        cache_key = f'email_test_limit_user_{user_id}'
        count = cache.get(cache_key, 0)
        
        if count >= cls.MAX_TEST_EMAILS_PER_MINUTE:
            logger.warning("Limite de tests dépassée pour l'utilisateur %s", user_id)
            return False
        
        # Incrémenter le compteur (expire dans 1 minute)
        cache.set(cache_key, count + 1, 60)
        return True


class SecureEmailLogger:
    """
    Logging sécurisé pour les emails
    Security by Design : Masquage des données sensibles
    """
    
    @staticmethod
    def mask_email(email: str) -> str:
        """
        Masque partiellement un email pour les logs
        
        Args:
            email: Email à masquer
            
        Returns:
            Email masqué (ex: j***@example.com)
        """
        if not email or '@' not in email:
            return '***@***.***'
        
        local, domain = email.split('@')
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def log_email_sent(recipient: str, subject: str, success: bool):
        """
        Log sécurisé d'un envoi d'email
        
        Args:
            recipient: Email du destinataire
            subject: Sujet de l'email
            success: Si l'envoi a réussi
        """
        masked_recipient = SecureEmailLogger.mask_email(recipient)
        status = "✅ Envoyé" if success else "❌ Échec"
        logger.info("%s - Email '%s' -> %s", status, subject, masked_recipient)
    
    @staticmethod
    def log_security_event(event_type: str, details: Dict[str, Any]):
        """
        Log d'un événement de sécurité
        
        Args:
            event_type: Type d'événement
            details: Détails (emails masqués automatiquement)
        """
        # Masquer les emails dans les détails
        safe_details = {}
        for key, value in details.items():
            if 'email' in key.lower() and isinstance(value, str):
                safe_details[key] = SecureEmailLogger.mask_email(value)
            else:
                safe_details[key] = value
        
        logger.warning("Événement sécurité : %s - %s", event_type, safe_details)
