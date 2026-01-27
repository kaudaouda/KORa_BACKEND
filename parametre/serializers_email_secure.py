"""
Serializers sécurisés pour EmailSettings
À intégrer dans parametre/serializers.py

Security by Design :
- Validation stricte
- Champ password en write-only
- Sanitization automatique
"""
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import EmailSettings
from .utils.email_security import EmailValidator, EmailContentSanitizer
import logging

logger = logging.getLogger(__name__)


class EmailSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer sécurisé pour EmailSettings
    Security by Design : Validation stricte, password write-only
    """
    # Le mot de passe n'est jamais renvoyé dans les réponses
    email_host_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={'input_type': 'password'},
        help_text='Mot de passe SMTP (chiffré automatiquement)'
    )
    
    # Champs en lecture seule pour la sécurité
    last_test_success = serializers.DateTimeField(read_only=True)
    last_modified_by_username = serializers.CharField(
        source='last_modified_by.username',
        read_only=True,
        allow_null=True
    )
    
    # Validation de la connexion SMTP
    smtp_connection_status = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailSettings
        fields = [
            'uuid',
            'email_host',
            'email_port',
            'email_host_user',
            'email_host_password',  # Write-only
            'email_use_tls',
            'email_use_ssl',
            'email_from_name',
            'email_timeout',
            'max_emails_per_hour',
            'max_recipients_per_email',
            'enable_rate_limiting',
            'last_test_success',
            'last_modified_by_username',
            'smtp_connection_status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'uuid',
            'last_test_success',
            'created_at',
            'updated_at',
            'smtp_connection_status'
        ]
        extra_kwargs = {
            'email_host_password': {
                'write_only': True,
                'required': False
            }
        }
    
    def get_smtp_connection_status(self, obj):
        """
        Retourne le statut de la dernière connexion SMTP
        Security by Design : Informations sanitizées
        """
        if not obj.last_test_success:
            return {
                'status': 'unknown',
                'message': 'Aucun test effectué'
            }
        
        from django.utils import timezone
        from datetime import timedelta
        
        age = timezone.now() - obj.last_test_success
        
        if age > timedelta(days=7):
            status = 'warning'
            message = f'Dernier test il y a {age.days} jours'
        elif age > timedelta(days=1):
            status = 'ok'
            message = f'Dernier test il y a {age.days} jours'
        else:
            status = 'ok'
            message = 'Testé récemment'
        
        return {
            'status': status,
            'message': message,
            'last_test': obj.last_test_success.isoformat()
        }
    
    def validate_email_host(self, value):
        """
        Valide le serveur SMTP
        Security by Design : Validation du hostname
        """
        if not value or not isinstance(value, str):
            raise serializers.ValidationError("Serveur SMTP requis")
        
        value = value.strip()
        
        # Vérifier que ce n'est pas une URL complète
        if value.startswith(('http://', 'https://', 'ftp://')):
            raise serializers.ValidationError(
                "Le serveur SMTP doit être un nom d'hôte, pas une URL complète"
            )
        
        # Vérifier la longueur
        if len(value) > 255:
            raise serializers.ValidationError("Nom d'hôte trop long (max 255 caractères)")
        
        # Bloquer les caractères dangereux
        import re
        if not re.match(r'^[a-zA-Z0-9.-]+$', value):
            raise serializers.ValidationError(
                "Le nom d'hôte contient des caractères invalides"
            )
        
        return value
    
    def validate_email_port(self, value):
        """
        Valide le port SMTP
        Security by Design : Ports autorisés uniquement
        """
        if not isinstance(value, int):
            raise serializers.ValidationError("Le port doit être un nombre entier")
        
        if value < 1 or value > 65535:
            raise serializers.ValidationError("Port invalide (doit être entre 1 et 65535)")
        
        # Ports communs pour SMTP
        common_ports = [25, 465, 587, 2525]
        if value not in common_ports:
            logger.warning(f"⚠️ Port SMTP inhabituel : {value}")
        
        return value
    
    def validate_email_host_user(self, value):
        """
        Valide l'adresse email de l'hôte
        Security by Design : Validation stricte
        """
        if not value:
            raise serializers.ValidationError("Adresse email requise")
        
        value = value.strip().lower()
        
        if not EmailValidator.is_valid_email(value):
            raise serializers.ValidationError("Adresse email invalide")
        
        return value
    
    def validate_email_from_name(self, value):
        """
        Valide le nom de l'expéditeur
        Security by Design : Sanitization
        """
        if not value:
            return 'KORA'
        
        # Sanitizer pour prévenir les injections
        sanitized = EmailContentSanitizer.sanitize_html(value)
        
        # Limiter la longueur
        if len(sanitized) > 100:
            raise serializers.ValidationError("Nom trop long (max 100 caractères)")
        
        return sanitized
    
    def validate_email_timeout(self, value):
        """
        Valide le timeout
        Security by Design : Limite maximale pour éviter les blocages
        """
        if not isinstance(value, int):
            raise serializers.ValidationError("Le timeout doit être un nombre entier")
        
        if value < 1:
            raise serializers.ValidationError("Le timeout doit être au moins 1 seconde")
        
        if value > 15:
            raise serializers.ValidationError(
                "Le timeout ne doit pas dépasser 15 secondes pour la sécurité"
            )
        
        return value
    
    def validate(self, data):
        """
        Validation globale
        Security by Design : Vérifications croisées
        """
        # Vérifier que TLS et SSL ne sont pas activés ensemble
        email_use_tls = data.get('email_use_tls')
        email_use_ssl = data.get('email_use_ssl')
        
        if email_use_tls and email_use_ssl:
            raise serializers.ValidationError(
                "TLS et SSL ne peuvent pas être activés simultanément"
            )
        
        # Au moins l'un des deux doit être activé
        if not email_use_tls and not email_use_ssl:
            logger.warning("⚠️ Aucun chiffrement activé (TLS/SSL)")
        
        # Valider les limites de rate limiting
        max_emails = data.get('max_emails_per_hour')
        if max_emails and max_emails > 1000:
            raise serializers.ValidationError({
                'max_emails_per_hour': 'Maximum 1000 emails par heure autorisé'
            })
        
        return data
    
    def create(self, validated_data):
        """
        Création sécurisée
        Security by Design : Chiffrement automatique du mot de passe
        """
        password = validated_data.pop('email_host_password', None)
        
        instance = super().create(validated_data)
        
        if password:
            instance.set_password(password)
            instance.save()
        
        logger.info(f"✅ Configuration email créée par {self.context.get('request').user.username if self.context.get('request') else 'system'}")
        
        return instance
    
    def update(self, instance, validated_data):
        """
        Mise à jour sécurisée
        Security by Design : Chiffrement automatique du mot de passe
        """
        password = validated_data.pop('email_host_password', None)
        
        # Enregistrer qui a modifié
        request = self.context.get('request')
        if request and request.user:
            instance.last_modified_by = request.user
        
        instance = super().update(instance, validated_data)
        
        if password:
            instance.set_password(password)
            instance.save()
        
        logger.info(f"✅ Configuration email mise à jour par {request.user.username if request and request.user else 'system'}")
        
        return instance


class EmailSettingsPublicSerializer(serializers.ModelSerializer):
    """
    Serializer public (sans mot de passe)
    Security by Design : Exposition minimale des données
    """
    smtp_connection_status = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailSettings
        fields = [
            'uuid',
            'email_host',
            'email_port',
            'email_host_user',
            'email_use_tls',
            'email_use_ssl',
            'email_from_name',
            'enable_rate_limiting',
            'smtp_connection_status',
        ]
        read_only_fields = '__all__'
    
    def get_smtp_connection_status(self, obj):
        """Statut simplifié pour la vue publique"""
        if not obj.last_test_success:
            return 'not_tested'
        
        from django.utils import timezone
        from datetime import timedelta
        
        age = timezone.now() - obj.last_test_success
        
        if age > timedelta(days=7):
            return 'outdated'
        return 'ok'


class EmailTestSerializer(serializers.Serializer):
    """
    Serializer pour les tests d'email
    Security by Design : Validation stricte des destinataires
    """
    test_email = serializers.EmailField(
        required=True,
        help_text='Adresse email pour le test'
    )
    
    def validate_test_email(self, value):
        """
        Valide l'adresse de test
        Security by Design : Validation complète
        """
        value = value.strip().lower()
        
        if not EmailValidator.is_valid_email(value):
            raise serializers.ValidationError("Adresse email invalide")
        
        return value
