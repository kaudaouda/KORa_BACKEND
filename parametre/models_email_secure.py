"""
Modèle EmailSettings sécurisé avec chiffrement
À intégrer dans parametre/models.py

Security by Design :
- Chiffrement du mot de passe SMTP
- Validation stricte
- Audit trail
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from .utils.email_security import EmailPasswordEncryption, EmailValidator
import logging

logger = logging.getLogger(__name__)


class EmailSettings(models.Model):
    """
    Paramètres de configuration email sécurisés
    Security by Design : Mot de passe chiffré, validation stricte
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Paramètres SMTP
    email_host = models.CharField(
        max_length=255, 
        default='smtp.gmail.com',
        help_text='Serveur SMTP (ex: smtp.gmail.com)'
    )
    email_port = models.PositiveIntegerField(
        default=587,
        help_text='Port SMTP (587 pour TLS, 465 pour SSL)'
    )
    email_host_user = models.EmailField(
        help_text='Adresse email pour l\'authentification SMTP'
    )
    
    # ⚠️ IMPORTANT : Le mot de passe est maintenant chiffré !
    email_host_password_encrypted = models.TextField(
        help_text='Mot de passe chiffré pour l\'authentification SMTP',
        blank=True
    )
    
    email_use_tls = models.BooleanField(
        default=True,
        help_text='Utiliser TLS (recommandé)'
    )
    email_use_ssl = models.BooleanField(
        default=False,
        help_text='Utiliser SSL'
    )
    
    # Paramètres d'envoi
    email_from_name = models.CharField(
        max_length=100,
        default='KORA',
        help_text='Nom affiché dans l\'expéditeur'
    )
    email_timeout = models.PositiveIntegerField(
        default=10,  # Réduit de 30 à 10 pour la sécurité
        help_text='Timeout en secondes pour l\'envoi (max 10 secondes recommandé)'
    )
    
    # Paramètres de sécurité
    max_emails_per_hour = models.PositiveIntegerField(
        default=100,
        help_text='Nombre maximum d\'emails par heure'
    )
    max_recipients_per_email = models.PositiveIntegerField(
        default=50,
        help_text='Nombre maximum de destinataires par email'
    )
    enable_rate_limiting = models.BooleanField(
        default=True,
        help_text='Activer la limitation du taux d\'envoi'
    )
    
    # Audit trail
    last_test_success = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date du dernier test réussi'
    )
    last_modified_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='email_settings_modifications'
    )
    
    # Enforce singleton
    singleton_enforcer = models.BooleanField(default=True, unique=True, editable=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_settings'
        verbose_name = 'Paramètre email'
        verbose_name_plural = 'Paramètres email'
        permissions = [
            ("can_test_email_config", "Peut tester la configuration email"),
            ("can_view_email_logs", "Peut voir les logs d'emails"),
        ]

    def __str__(self):
        return f'Configuration email - {self.email_host_user}'

    def clean(self):
        """
        Validation du modèle
        Security by Design : Validation stricte
        """
        super().clean()
        
        # Valider l'email
        if self.email_host_user and not EmailValidator.is_valid_email(self.email_host_user):
            raise ValidationError({
                'email_host_user': 'Adresse email invalide'
            })
        
        # Valider le port
        if self.email_port < 1 or self.email_port > 65535:
            raise ValidationError({
                'email_port': 'Port doit être entre 1 et 65535'
            })
        
        # Valider que TLS et SSL ne sont pas activés en même temps
        if self.email_use_tls and self.email_use_ssl:
            raise ValidationError(
                'TLS et SSL ne peuvent pas être activés simultanément'
            )
        
        # Valider le timeout
        if self.email_timeout > 15:
            raise ValidationError({
                'email_timeout': 'Timeout maximum de 15 secondes pour la sécurité'
            })

    @classmethod
    def get_solo(cls):
        """Retourne l'unique instance des paramètres email (créée si absente)."""
        instance, created = cls.objects.get_or_create(
            singleton_enforcer=True,
            defaults={
                'email_host': 'smtp.gmail.com',
                'email_port': 587,
                'email_host_user': '',
                'email_host_password_encrypted': '',
                'email_use_tls': True,
                'email_use_ssl': False,
                'email_from_name': 'KORA',
                'email_timeout': 10,
                'max_emails_per_hour': 100,
                'max_recipients_per_email': 50,
                'enable_rate_limiting': True
            }
        )
        
        if created:
            logger.info("✅ Configuration email initialisée avec les valeurs par défaut")
        
        return instance

    def set_password(self, password: str):
        """
        Définit le mot de passe SMTP (chiffré)
        Security by Design : Chiffrement automatique
        
        Args:
            password: Mot de passe en clair
        """
        if not password:
            self.email_host_password_encrypted = ''
            return
        
        try:
            self.email_host_password_encrypted = EmailPasswordEncryption.encrypt_password(password)
            logger.info("✅ Mot de passe SMTP chiffré avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors du chiffrement du mot de passe : {str(e)}")
            raise ValidationError("Impossible de chiffrer le mot de passe")

    def get_password(self) -> str:
        """
        Récupère le mot de passe SMTP déchiffré
        Security by Design : Déchiffrement sécurisé
        
        Returns:
            Mot de passe en clair
        """
        if not self.email_host_password_encrypted:
            return ''
        
        try:
            return EmailPasswordEncryption.decrypt_password(self.email_host_password_encrypted)
        except Exception as e:
            logger.error("❌ Erreur lors du déchiffrement du mot de passe")
            raise ValidationError("Impossible de déchiffrer le mot de passe")

    def get_email_config(self) -> dict:
        """
        Retourne la configuration email au format Django
        Security by Design : Mot de passe déchiffré seulement pour l'envoi
        
        Returns:
            Configuration Django
        """
        return {
            'EMAIL_HOST': self.email_host,
            'EMAIL_PORT': self.email_port,
            'EMAIL_HOST_USER': self.email_host_user,
            'EMAIL_HOST_PASSWORD': self.get_password(),  # Déchiffré
            'EMAIL_USE_TLS': self.email_use_tls,
            'EMAIL_USE_SSL': self.email_use_ssl,
            'EMAIL_TIMEOUT': self.email_timeout,
            'DEFAULT_FROM_EMAIL': f'{self.email_from_name} <{self.email_host_user}>',
        }

    def test_smtp_connection(self) -> tuple[bool, str]:
        """
        Test la connexion SMTP
        Security by Design : Validation de la configuration
        
        Returns:
            (succès, message)
        """
        try:
            from django.core.mail import get_connection
            
            config = self.get_email_config()
            connection = get_connection(
                host=config['EMAIL_HOST'],
                port=config['EMAIL_PORT'],
                username=config['EMAIL_HOST_USER'],
                password=config['EMAIL_HOST_PASSWORD'],
                use_tls=config['EMAIL_USE_TLS'],
                use_ssl=config['EMAIL_USE_SSL'],
                timeout=config['EMAIL_TIMEOUT']
            )
            
            connection.open()
            connection.close()
            
            # Enregistrer le succès
            self.last_test_success = timezone.now()
            self.save(update_fields=['last_test_success'])
            
            logger.info("✅ Test de connexion SMTP réussi")
            return True, "Connexion SMTP établie avec succès"
            
        except Exception as e:
            logger.error(f"❌ Test de connexion SMTP échoué : {str(e)}")
            return False, f"Échec de la connexion : {str(e)}"

    def mark_test_success(self):
        """Marque le dernier test comme réussi"""
        self.last_test_success = timezone.now()
        self.save(update_fields=['last_test_success'])


class ReminderEmailLog(models.Model):
    """
    Log des emails de relance
    Security by Design : Audit trail complet
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    context_hash = models.CharField(max_length=64)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # Champs de sécurité ajoutés
    success = models.BooleanField(default=True, help_text='Si l\'envoi a réussi')
    error_message = models.TextField(blank=True, help_text='Message d\'erreur si échec')
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text='IP de l\'émetteur')
    user = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Utilisateur qui a déclenché l\'envoi'
    )

    class Meta:
        db_table = 'reminder_email_log'
        indexes = [
            models.Index(fields=['recipient', 'context_hash', 'sent_at']),
            models.Index(fields=['success', 'sent_at']),
            models.Index(fields=['user', 'sent_at']),
        ]
        verbose_name = 'Log email de relance'
        verbose_name_plural = 'Logs emails de relance'

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.subject} -> {self.recipient} ({self.sent_at:%Y-%m-%d %H:%M})"


# ==================== INSTRUCTIONS DE MIGRATION ====================
"""
Pour migrer vers ce modèle sécurisé :

1. Créer une migration pour ajouter les nouveaux champs :
   python manage.py makemigrations parametre --name add_email_security_fields

2. Créer une migration de données pour chiffrer les mots de passe existants :
   python manage.py makemigrations parametre --name encrypt_existing_passwords --empty

3. Exécuter les migrations :
   python manage.py migrate parametre

4. Ajouter EMAIL_ENCRYPTION_KEY dans .env :
   EMAIL_ENCRYPTION_KEY=your-generated-key-here

5. Générer une clé de chiffrement :
   from cryptography.fernet import Fernet
   print(Fernet.generate_key().decode())
"""
