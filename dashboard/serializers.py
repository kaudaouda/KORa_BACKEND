"""
Serializers pour l'application Dashboard
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Objectives, Indicateur


class UserSerializer(serializers.ModelSerializer):
    """Serializer pour les utilisateurs"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'username', 
            'is_active', 'date_joined', 'full_name'
        ]
        read_only_fields = ['id', 'date_joined']
    
    def get_full_name(self, obj):
        """Retourner le nom complet"""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


# ==================== OBJECTIFS ====================

class ObjectivesSerializer(serializers.ModelSerializer):
    """Serializer pour les objectifs"""
    createur_nom = serializers.SerializerMethodField()
    indicateurs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Objectives
        fields = [
            'uuid', 'number', 'libelle', 'cree_par', 'createur_nom',
            'indicateurs_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'number', 'created_at', 'updated_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
    
    def get_indicateurs_count(self, obj):
        """Retourner le nombre d'indicateurs associés"""
        return obj.indicateurs.count()


class ObjectivesCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'objectifs"""
    
    class Meta:
        model = Objectives
        fields = ['libelle']
    
    def create(self, validated_data):
        """Créer un objectif avec l'utilisateur connecté"""
        validated_data['cree_par'] = self.context['request'].user
        return super().create(validated_data)


class ObjectivesUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'objectifs"""
    
    class Meta:
        model = Objectives
        fields = ['libelle']
    
    def update(self, instance, validated_data):
        """Mettre à jour un objectif"""
        # Le numéro et le créateur ne peuvent pas être modifiés
        return super().update(instance, validated_data)


# ==================== INDICATEURS ====================

class IndicateurSerializer(serializers.ModelSerializer):
    """Serializer pour les indicateurs"""
    objective_number = serializers.CharField(source='objective_id.number', read_only=True)
    objective_libelle = serializers.CharField(source='objective_id.libelle', read_only=True)
    frequence_nom = serializers.CharField(source='frequence_id.nom', read_only=True)
    
    class Meta:
        model = Indicateur
        fields = [
            'uuid', 'libelle', 'objective_id', 'objective_number', 'objective_libelle',
            'frequence_id', 'frequence_nom', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class IndicateurCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'indicateurs"""
    
    class Meta:
        model = Indicateur
        fields = ['libelle', 'objective_id', 'frequence_id']
    
    def validate_objective_id(self, value):
        """Valider que l'objectif existe"""
        if not Objectives.objects.filter(uuid=value.uuid).exists():
            raise serializers.ValidationError("L'objectif spécifié n'existe pas")
        return value
    
    def validate_frequence_id(self, value):
        """Valider que la fréquence existe"""
        from parametre.models import Frequence
        if not Frequence.objects.filter(uuid=value.uuid).exists():
            raise serializers.ValidationError("La fréquence spécifiée n'existe pas")
        return value


class IndicateurUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'indicateurs"""
    
    class Meta:
        model = Indicateur
        fields = ['libelle', 'objective_id', 'frequence_id']
    
    def validate_objective_id(self, value):
        """Valider que l'objectif existe"""
        if not Objectives.objects.filter(uuid=value.uuid).exists():
            raise serializers.ValidationError("L'objectif spécifié n'existe pas")
        return value
    
    def validate_frequence_id(self, value):
        """Valider que la fréquence existe"""
        from parametre.models import Frequence
        if not Frequence.objects.filter(uuid=value.uuid).exists():
            raise serializers.ValidationError("La fréquence spécifiée n'existe pas")
        return value
