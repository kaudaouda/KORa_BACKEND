"""
Serializers pour l'application PAC
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Pac, Traitement, Suivi
from parametre.models import Processus


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


class ProcessusSerializer(serializers.ModelSerializer):
    """Serializer pour les processus"""
    createur_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = Processus
        fields = [
            'uuid', 'numero_processus', 'nom', 'description', 
            'cree_par', 'createur_nom', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'numero_processus', 'created_at', 'updated_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username


class ProcessusCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de processus"""
    
    class Meta:
        model = Processus
        fields = ['nom', 'description']
    
    def create(self, validated_data):
        """Créer un processus avec l'utilisateur connecté"""
        validated_data['cree_par'] = self.context['request'].user
        return super().create(validated_data)


class PacSerializer(serializers.ModelSerializer):
    """Serializer pour les PACs"""
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    processus_numero = serializers.CharField(source='processus.numero_processus', read_only=True)
    nature_nom = serializers.CharField(source='nature.nom', read_only=True)
    categorie_nom = serializers.CharField(source='categorie.nom', read_only=True)
    source_nom = serializers.CharField(source='source.nom', read_only=True)
    createur_nom = serializers.SerializerMethodField()
    jours_restants = serializers.SerializerMethodField()
    
    class Meta:
        model = Pac
        fields = [
            'uuid', 'numero_pac', 'processus', 'processus_nom', 'processus_numero',
            'libelle', 'nature', 'nature_nom', 'categorie', 'categorie_nom',
            'source', 'source_nom', 'periode_de_realisation', 'jours_restants',
            'cree_par', 'createur_nom', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
    
    def get_jours_restants(self, obj):
        """Calculer les jours restants"""
        from django.utils import timezone
        delta = obj.periode_de_realisation - timezone.now().date()
        return delta.days if delta.days > 0 else 0


class PacCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de PACs"""
    
    class Meta:
        model = Pac
        fields = [
            'processus', 'libelle', 'nature', 
            'categorie', 'source', 'periode_de_realisation'
        ]
    
    def create(self, validated_data):
        """Créer un PAC avec l'utilisateur connecté et générer le numéro"""
        validated_data['cree_par'] = self.context['request'].user
        
        # Générer le numéro PAC automatiquement
        validated_data['numero_pac'] = self.generate_numero_pac()
        
        return super().create(validated_data)
    
    def generate_numero_pac(self):
        """Générer un numéro PAC unique"""
        from django.db.models import Count
        count = Pac.objects.count()
        numero = f"PAC{count + 1:04d}"
        
        # Vérifier l'unicité
        while Pac.objects.filter(numero_pac=numero).exists():
            count += 1
            numero = f"PAC{count + 1:04d}"
        
        return numero


class PacUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de PACs"""
    
    class Meta:
        model = Pac
        fields = [
            'processus', 'libelle', 'nature', 
            'categorie', 'source', 'periode_de_realisation'
        ]
    
    def update(self, instance, validated_data):
        """Mettre à jour un PAC"""
        # Le numéro PAC et le créateur ne peuvent pas être modifiés
        return super().update(instance, validated_data)


class TraitementSerializer(serializers.ModelSerializer):
    """Serializer pour les traitements"""
    type_action_nom = serializers.CharField(source='type_action.nom', read_only=True)
    preuve_description = serializers.CharField(source='preuve.description', read_only=True)
    pac_numero = serializers.CharField(source='pac.numero_pac', read_only=True)
    pac_uuid = serializers.UUIDField(source='pac.uuid', read_only=True)
    responsable_direction_nom = serializers.CharField(source='responsable_direction.nom', read_only=True)
    responsable_sous_direction_nom = serializers.CharField(source='responsable_sous_direction.nom', read_only=True)
    
    class Meta:
        model = Traitement
        fields = [
            'uuid', 'pac', 'pac_uuid', 'pac_numero', 'action', 'type_action', 
            'type_action_nom', 'responsable_direction', 'responsable_direction_nom',
            'responsable_sous_direction', 'responsable_sous_direction_nom',
            'preuve', 'preuve_description', 'delai_realisation'
        ]
        read_only_fields = ['uuid']


class TraitementCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de traitements"""
    
    class Meta:
        model = Traitement
        fields = [
            'pac', 'action', 'type_action', 'responsable_direction', 
            'responsable_sous_direction', 'preuve', 'delai_realisation'
        ]


class TraitementUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de traitements"""
    
    class Meta:
        model = Traitement
        fields = [
            'action', 'type_action', 'responsable_direction', 
            'responsable_sous_direction', 'preuve', 'delai_realisation'
        ]


class SuiviSerializer(serializers.ModelSerializer):
    """Serializer pour les suivis"""
    etat_nom = serializers.CharField(source='etat_mise_en_oeuvre.nom', read_only=True)
    appreciation_nom = serializers.CharField(source='appreciation.nom', read_only=True)
    traitement_action = serializers.CharField(source='traitement.action', read_only=True)
    createur_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = Suivi
        fields = [
            'uuid', 'traitement', 'traitement_action', 'etat_mise_en_oeuvre', 
            'etat_nom', 'resultat', 'appreciation', 'appreciation_nom',
            'cree_par', 'createur_nom', 'created_at'
        ]
        read_only_fields = ['uuid', 'created_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username


class SuiviCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de suivis"""
    
    class Meta:
        model = Suivi
        fields = [
            'traitement', 'etat_mise_en_oeuvre', 'resultat', 'appreciation'
        ]
    
    def create(self, validated_data):
        """Créer un suivi avec l'utilisateur connecté"""
        validated_data['cree_par'] = self.context['request'].user
        return super().create(validated_data)
