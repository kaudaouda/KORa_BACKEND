from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import (
    Appreciation, Categorie, Direction, SousDirection, ActionType,
    NotificationSettings, DashboardNotificationSettings, EmailSettings, Nature, Source, Processus,
    Service, EtatMiseEnOeuvre, Frequence, Versions, Annee, Risque, StatutActionCDR,
    Role, UserProcessus, UserProcessusRole
)


class AppreciationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appreciation
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class DirectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class SousDirectionSerializer(serializers.ModelSerializer):
    direction_nom = serializers.CharField(source='direction.nom', read_only=True)
    
    class Meta:
        model = SousDirection
        fields = ['uuid', 'nom', 'description', 'direction', 'direction_nom', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class ActionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionType
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class NatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nature
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class ProcessusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Processus
        fields = ['uuid', 'numero_processus', 'nom', 'description', 'cree_par', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'numero_processus', 'created_at', 'updated_at']


class ServiceSerializer(serializers.ModelSerializer):
    sous_direction_nom = serializers.CharField(source='sous_direction.nom', read_only=True)
    direction_nom = serializers.CharField(source='sous_direction.direction.nom', read_only=True)
    
    class Meta:
        model = Service
        fields = ['uuid', 'nom', 'description', 'sous_direction', 'sous_direction_nom', 'direction_nom', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class EtatMiseEnOeuvreSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtatMiseEnOeuvre
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class StatutActionCDRSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatutActionCDR
        fields = ['uuid', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = [
            'uuid',
            'traitement_delai_notice_days',
            'traitement_reminder_frequency_days',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class DashboardNotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardNotificationSettings
        fields = [
            'uuid',
            'days_before_period_end',
            'days_after_period_end',
            'reminder_frequency_days',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class EmailSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer sécurisé pour EmailSettings
    Security by Design : Validation stricte, password write-only, chiffrement automatique
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
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'uuid',
            'last_test_success',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'email_host_password': {
                'write_only': True,
                'required': False
            }
        }
    
    def validate_email_timeout(self, value):
        """
        Valide le timeout
        Security by Design : Limite maximale pour éviter les blocages
        """
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
        email_use_tls = data.get('email_use_tls', getattr(self.instance, 'email_use_tls', False))
        email_use_ssl = data.get('email_use_ssl', getattr(self.instance, 'email_use_ssl', False))
        
        if email_use_tls and email_use_ssl:
            raise serializers.ValidationError(
                "TLS et SSL ne peuvent pas être activés simultanément"
            )
        
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
        
        return instance


class FrequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Frequence
        fields = ['uuid', 'nom', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class VersionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Versions
        fields = ['uuid', 'code', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class AnneeSerializer(serializers.ModelSerializer):
    pacs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Annee
        fields = ['uuid', 'annee', 'libelle', 'description', 'is_active', 'pacs_count', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_pacs_count(self, obj):
        """Retourner le nombre de PACs associés à cette année"""
        return obj.pacs.count()


class RisqueSerializer(serializers.ModelSerializer):
    niveaux_risque = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = Risque
        fields = ['uuid', 'libelle', 'description', 'niveaux_risque', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def validate_niveaux_risque(self, value):
        """Convertir une chaîne séparée par des virgules en liste, ou accepter une liste JSON"""
        if not value:
            return []
        
        # Si c'est déjà une liste (depuis JSON), la retourner telle quelle
        if isinstance(value, list):
            # Nettoyer et valider chaque élément
            return [str(item).strip().upper() for item in value if str(item).strip()]
        
        # Si c'est une chaîne, la convertir en liste
        if isinstance(value, str):
            # Essayer d'abord de parser comme JSON
            try:
                import json
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item).strip().upper() for item in parsed if str(item).strip()]
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Sinon, traiter comme une chaîne séparée par des virgules
            niveaux = [n.strip().upper() for n in value.split(',') if n.strip()]
            return niveaux
        
        return []
    
    def to_representation(self, instance):
        """Convertir la liste en chaîne pour l'affichage dans l'admin si nécessaire"""
        representation = super().to_representation(instance)
        # Garder la liste pour l'API, mais on peut aussi la convertir en chaîne si besoin
        return representation
    
    def create(self, validated_data):
        """Créer un risque avec les niveaux de risque convertis"""
        niveaux_risque = validated_data.pop('niveaux_risque', [])
        risque = Risque.objects.create(**validated_data)
        risque.niveaux_risque = niveaux_risque
        risque.save()
        return risque
    
    def update(self, instance, validated_data):
        """Mettre à jour un risque avec les niveaux de risque convertis"""
        niveaux_risque = validated_data.pop('niveaux_risque', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if niveaux_risque is not None:
            instance.niveaux_risque = niveaux_risque
        
        instance.save()
        return instance


# ==================== SERIALIZERS POUR LE SYSTÈME DE RÔLES ====================

class RoleSerializer(serializers.ModelSerializer):
    """Serializer pour les rôles"""
    
    class Meta:
        model = Role
        fields = ['uuid', 'code', 'nom', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class UserProcessusSerializer(serializers.ModelSerializer):
    """Serializer pour les attributions processus-utilisateur"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    processus_numero = serializers.CharField(source='processus.numero_processus', read_only=True)
    attribue_par_username = serializers.CharField(source='attribue_par.username', read_only=True, allow_null=True)
    
    class Meta:
        model = UserProcessus
        fields = [
            'uuid', 'user', 'user_username', 'user_email',
            'processus', 'processus_nom', 'processus_numero',
            'attribue_par', 'attribue_par_username',
            'date_attribution', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'date_attribution', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    """Serializer pour les utilisateurs"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'last_login', 'full_name'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_full_name(self, obj):
        """Retourner le nom complet"""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un utilisateur (super admin uniquement)"""
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'is_active'
        ]
    
    def validate_email(self, value):
        """Valider l'unicité de l'email"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value
    
    def validate_username(self, value):
        """Valider l'unicité du username"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà utilisé.")
        return value
    
    def validate(self, data):
        """Valider que les mots de passe correspondent"""
        if data.get('password') != data.get('password_confirm'):
            raise serializers.ValidationError({
                'password_confirm': 'Les mots de passe ne correspondent pas.'
            })
        
        # Valider la force du mot de passe
        password = data.get('password')
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise serializers.ValidationError({
                    'password': list(e.messages)
                })
        
        return data
    
    def create(self, validated_data):
        """Créer l'utilisateur avec le mot de passe hashé"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UserInviteSerializer(serializers.ModelSerializer):
    """
    Serializer pour inviter un utilisateur sans définir de mot de passe.
    Security by Design :
    - Le mot de passe n'est jamais manipulé côté admin
    - L'utilisateur définira lui-même son mot de passe via un lien sécurisé
    - Le username est optionnel et généré automatiquement depuis l'email si non fourni
    """
    username = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=False)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 'is_active'
        ]
        extra_kwargs = {
            'username': {'required': False, 'allow_blank': True, 'allow_null': True},
            'email': {'required': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
        }

    def validate_email(self, value):
        """Valider l'unicité et la validité de l'email"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[UserInviteSerializer] validate_email appelé avec value: {value}")
        logger.info(f"[UserInviteSerializer] Type de value: {type(value)}")
        
        from .utils.email_security import EmailValidator

        if not EmailValidator.is_valid_email(value):
            logger.error(f"[UserInviteSerializer] Email invalide: {value}")
            raise serializers.ValidationError("Adresse email invalide.")

        email_exists = User.objects.filter(email=value).exists()
        logger.info(f"[UserInviteSerializer] Email existe dans DB: {email_exists}")
        
        if email_exists:
            existing_user = User.objects.filter(email=value).first()
            logger.warning(f"[UserInviteSerializer] Email déjà utilisé par: username={existing_user.username}, id={existing_user.id}, is_active={existing_user.is_active}")
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        
        logger.info(f"[UserInviteSerializer] Email validé avec succès: {value}")
        return value

    def validate_username(self, value):
        """Valider l'unicité du username si fourni"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[UserInviteSerializer] validate_username appelé avec value: {value}")
        logger.info(f"[UserInviteSerializer] Type de value: {type(value)}")
        
        # Si username est None, vide ou seulement des espaces, retourner None (sera généré automatiquement)
        if not value or not value.strip():
            logger.info(f"[UserInviteSerializer] Username vide ou None, sera généré automatiquement")
            return None
        
        username_clean = value.strip()
        logger.info(f"[UserInviteSerializer] Username fourni: {username_clean}")
        
        # Valider l'unicité si un username est fourni
        username_exists = User.objects.filter(username=username_clean).exists()
        logger.info(f"[UserInviteSerializer] Username existe dans DB: {username_exists}")
        
        if username_exists:
            logger.warning(f"[UserInviteSerializer] Username déjà utilisé: {username_clean}")
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà utilisé.")
        
        logger.info(f"[UserInviteSerializer] Username validé avec succès: {username_clean}")
        return username_clean

    def create(self, validated_data):
        """
        Créer l'utilisateur avec un mot de passe inutilisable.
        L'activation finale et la définition du mot de passe se feront via le lien d'invitation.
        Si username n'est pas fourni, il sera généré automatiquement depuis l'email.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[UserInviteSerializer] create appelé avec validated_data: {validated_data}")
        
        email = validated_data['email']
        logger.info(f"[UserInviteSerializer] Email à utiliser: {email}")
        
        # Récupérer le username s'il est fourni, sinon None
        username = validated_data.pop('username', None)
        logger.info(f"[UserInviteSerializer] Username initial (depuis validated_data): {username}")
        
        if username:
            username = username.strip()
            logger.info(f"[UserInviteSerializer] Username après strip: {username}")
        
        # Générer automatiquement le username depuis l'email si non fourni ou vide
        if not username:
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            logger.info(f"[UserInviteSerializer] Génération automatique du username depuis email, base: {base_username}")
            
            # S'assurer que le nom d'utilisateur est unique
            while User.objects.filter(username=username).exists():
                logger.info(f"[UserInviteSerializer] Username {username} existe déjà, tentative suivante...")
                username = f"{base_username}{counter}"
                counter += 1
            
            logger.info(f"[UserInviteSerializer] Username final généré: {username}")
        
        # Par défaut, ne pas activer le compte tant que le mot de passe n'est pas défini
        is_active = validated_data.get('is_active', False)
        logger.info(f"[UserInviteSerializer] is_active: {is_active}")
        logger.info(f"[UserInviteSerializer] first_name: {validated_data.get('first_name', '')}")
        logger.info(f"[UserInviteSerializer] last_name: {validated_data.get('last_name', '')}")
        
        # Créer l'utilisateur avec le username généré ou fourni
        logger.info(f"[UserInviteSerializer] Création de l'utilisateur avec username={username}, email={email}")
        user = User(
            username=username,
            email=email,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_active=is_active,
        )
        # Mot de passe inutilisable tant que l'utilisateur n'a pas finalisé l'invitation
        user.set_unusable_password()
        user.save()
        logger.info(f"[UserInviteSerializer] Utilisateur créé avec succès: id={user.id}, username={user.username}, email={user.email}")
        return user


class UserProcessusRoleSerializer(serializers.ModelSerializer):
    """Serializer pour les rôles utilisateur-processus"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    processus_numero = serializers.CharField(source='processus.numero_processus', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    role_nom = serializers.CharField(source='role.nom', read_only=True)
    attribue_par_username = serializers.CharField(source='attribue_par.username', read_only=True, allow_null=True)
    
    class Meta:
        model = UserProcessusRole
        fields = [
            'uuid', 'user', 'user_username', 'user_email',
            'processus', 'processus_nom', 'processus_numero',
            'role', 'role_code', 'role_nom',
            'attribue_par', 'attribue_par_username',
            'date_attribution', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'date_attribution', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Valider que l'utilisateur est bien attribué au processus"""
        user = data.get('user')
        processus = data.get('processus')
        
        if user and processus:
            # Vérifier que l'utilisateur est bien attribué au processus
            user_processus_exists = UserProcessus.objects.filter(
                user=user,
                processus=processus,
                is_active=True
            ).exists()
            
            if not user_processus_exists:
                raise serializers.ValidationError(
                    f"L'utilisateur {user.username} doit d'abord être attribué au processus {processus.nom} "
                    "avant de pouvoir avoir des rôles."
                )
        
        return data


