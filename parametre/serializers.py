from rest_framework import serializers
from .models import (
    Appreciation, Categorie, Direction, SousDirection, ActionType, 
    NotificationSettings, DashboardNotificationSettings, EmailSettings, Nature, Source, Processus, 
    Service, EtatMiseEnOeuvre, Frequence, Versions, Annee, Risque
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
    class Meta:
        model = EmailSettings
        fields = [
            'uuid',
            'email_host',
            'email_port',
            'email_host_user',
            'email_host_password',
            'email_use_tls',
            'email_use_ssl',
            'email_from_name',
            'email_timeout',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
        extra_kwargs = {
            'email_host_password': {'write_only': True}  # Ne pas afficher le mot de passe dans les réponses
        }


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


