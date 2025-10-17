"""
Serializers pour l'application Dashboard
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Objectives, Indicateur
from parametre.models import Cible, Periodicite, Frequence


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
    allowed_periodes = serializers.SerializerMethodField()
    
    class Meta:
        model = Indicateur
        fields = [
            'uuid', 'libelle', 'objective_id', 'objective_number', 'objective_libelle',
            'frequence_id', 'frequence_nom', 'allowed_periodes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_allowed_periodes(self, obj):
        """Retourner les périodes autorisées pour la fréquence de cet indicateur"""
        from parametre.models import Periodicite
        return [p[0] for p in Periodicite.get_periodes_for_frequence(obj.frequence_id.nom)]


class IndicateurCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'indicateurs"""
    
    class Meta:
        model = Indicateur
        fields = ['libelle', 'objective_id', 'frequence_id']
    
    def validate_objective_id(self, value):
        """Valider que l'objectif existe"""
        # Si value est une string UUID, convertir en objet Objectives
        if isinstance(value, str):
            try:
                objective = Objectives.objects.get(uuid=value)
                return objective
            except Objectives.DoesNotExist:
                raise serializers.ValidationError("L'objectif spécifié n'existe pas")
        elif hasattr(value, 'uuid'):
            if not Objectives.objects.filter(uuid=value.uuid).exists():
                raise serializers.ValidationError("L'objectif spécifié n'existe pas")
            return value
        else:
            raise serializers.ValidationError("Format d'objectif invalide")
    
    def validate_frequence_id(self, value):
        """Valider que la fréquence existe"""
        from parametre.models import Frequence
        # Si value est une string UUID, convertir en objet Frequence
        if isinstance(value, str):
            try:
                frequence = Frequence.objects.get(uuid=value)
                return frequence
            except Frequence.DoesNotExist:
                raise serializers.ValidationError("La fréquence spécifiée n'existe pas")
        elif hasattr(value, 'uuid'):
            if not Frequence.objects.filter(uuid=value.uuid).exists():
                raise serializers.ValidationError("La fréquence spécifiée n'existe pas")
            return value
        else:
            raise serializers.ValidationError("Format de fréquence invalide")


class IndicateurUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'indicateurs"""
    
    class Meta:
        model = Indicateur
        fields = ['libelle', 'objective_id', 'frequence_id']
    
    def validate_objective_id(self, value):
        """Valider que l'objectif existe"""
        # Si value est une string UUID, convertir en objet Objectives
        if isinstance(value, str):
            try:
                objective = Objectives.objects.get(uuid=value)
                return objective
            except Objectives.DoesNotExist:
                raise serializers.ValidationError("L'objectif spécifié n'existe pas")
        elif hasattr(value, 'uuid'):
            if not Objectives.objects.filter(uuid=value.uuid).exists():
                raise serializers.ValidationError("L'objectif spécifié n'existe pas")
            return value
        else:
            raise serializers.ValidationError("Format d'objectif invalide")
    
    def validate_frequence_id(self, value):
        """Valider que la fréquence existe"""
        from parametre.models import Frequence
        # Si value est une string UUID, convertir en objet Frequence
        if isinstance(value, str):
            try:
                frequence = Frequence.objects.get(uuid=value)
                return frequence
            except Frequence.DoesNotExist:
                raise serializers.ValidationError("La fréquence spécifiée n'existe pas")
        elif hasattr(value, 'uuid'):
            if not Frequence.objects.filter(uuid=value.uuid).exists():
                raise serializers.ValidationError("La fréquence spécifiée n'existe pas")
            return value
        else:
            raise serializers.ValidationError("Format de fréquence invalide")


# ==================== PERIODICITES ====================

class PeriodiciteSerializer(serializers.ModelSerializer):
    """Serializer pour les périodicités"""
    indicateur_libelle = serializers.CharField(source='indicateur_id.libelle', read_only=True)
    periode_display = serializers.CharField(source='get_periode_display', read_only=True)
    
    class Meta:
        model = Periodicite
        fields = [
            'uuid', 'indicateur_id', 'indicateur_libelle', 'periode', 'periode_display',
            'a_realiser', 'realiser', 'taux', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'taux', 'created_at', 'updated_at']


class PeriodiciteCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de périodicités"""
    
    class Meta:
        model = Periodicite
        fields = ['indicateur_id', 'periode', 'a_realiser', 'realiser']
    
    def validate(self, data):
        """Valider les données"""
        indicateur = data.get('indicateur_id')
        periode = data.get('periode')
        
        # Vérifier que la période est autorisée pour la fréquence de l'indicateur
        if indicateur and periode:
            frequence_nom = indicateur.frequence_id.nom
            if not Periodicite.is_periode_allowed_for_frequence(frequence_nom, periode):
                # Convertir les codes en libellés complets
                periode_labels = {
                    'T1': '1er Trimestre',
                    'T2': '2ème Trimestre', 
                    'T3': '3ème Trimestre',
                    'T4': '4ème Trimestre',
                    'S1': '1er Semestre',
                    'S2': '2ème Semestre',
                    'A1': 'Année'
                }
                
                periode_label = periode_labels.get(periode, periode)
                allowed_periodes_labels = [
                    periode_labels.get(p[0], p[0]) for p in Periodicite.get_periodes_for_frequence(frequence_nom)
                ]
                
                raise serializers.ValidationError(
                    f"La période {periode_label} n'est pas autorisée pour la fréquence \"{frequence_nom}\". "
                    f"Périodes autorisées: {', '.join(allowed_periodes_labels)}"
                )
        
        # Vérifier qu'il n'existe pas déjà une périodicité pour cet indicateur et cette période
        if Periodicite.objects.filter(indicateur_id=indicateur, periode=periode).exists():
            # Convertir le code en libellé complet
            periode_labels = {
                'T1': '1er Trimestre',
                'T2': '2ème Trimestre', 
                'T3': '3ème Trimestre',
                'T4': '4ème Trimestre',
                'S1': '1er Semestre',
                'S2': '2ème Semestre',
                'A1': 'Année'
            }
            periode_label = periode_labels.get(periode, periode)
            raise serializers.ValidationError(
                f"Une périodicité existe déjà pour cet indicateur en {periode_label}"
            )
        
        # Valider que a_realiser est positif
        if data.get('a_realiser', 0) < 0:
            raise serializers.ValidationError("La valeur 'à réaliser' ne peut pas être négative")
        
        # Valider que realiser est positif
        if data.get('realiser', 0) < 0:
            raise serializers.ValidationError("La valeur 'réalisé' ne peut pas être négative")
        
        return data


class PeriodiciteUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de périodicités"""
    
    class Meta:
        model = Periodicite
        fields = ['a_realiser', 'realiser']
    
    def validate_a_realiser(self, value):
        """Valider la valeur à réaliser"""
        if value < 0:
            raise serializers.ValidationError("La valeur 'à réaliser' ne peut pas être négative")
        return value
    
    def validate_realiser(self, value):
        """Valider la valeur réalisée"""
        if value < 0:
            raise serializers.ValidationError("La valeur 'réalisé' ne peut pas être négative")
        return value


# ==================== CIBLES ====================

class CibleSerializer(serializers.ModelSerializer):
    """Serializer pour les cibles"""
    frequence_nom = serializers.CharField(source='indicateur_id.frequence_id.nom', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    indicateur_id = serializers.CharField(source='indicateur_id.uuid', read_only=True)
    
    class Meta:
        model = Cible
        fields = [
            'uuid', 'valeur', 'condition', 'condition_display',
            'indicateur_id', 'frequence_nom',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class CibleCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création/mise à jour de cibles"""
    indicateur_id = serializers.UUIDField(write_only=True, required=True)

    class Meta:
        model = Cible
        fields = ['valeur', 'condition', 'indicateur_id']

    def validate_indicateur_id(self, value):
        """Valider que l'indicateur existe"""
        if value:
            try:
                from .models import Indicateur
                indicateur = Indicateur.objects.get(uuid=value)
                return indicateur
            except Indicateur.DoesNotExist:
                raise serializers.ValidationError("L'indicateur spécifié n'existe pas")
        return None

    def validate_valeur(self, value):
        """Valider la valeur de la cible"""
        if value < 0:
            raise serializers.ValidationError("La valeur de la cible ne peut pas être négative")
        return value

    def create(self, validated_data):
        """Créer ou mettre à jour la cible (une seule par indicateur)"""
        indicateur = validated_data.pop('indicateur_id')
        
        # Vérifier s'il existe déjà une cible pour cet indicateur
        existing_cible = Cible.objects.filter(indicateur_id=indicateur).first()
        
        if existing_cible:
            # Mettre à jour la cible existante
            existing_cible.valeur = validated_data['valeur']
            existing_cible.condition = validated_data['condition']
            existing_cible.save()
            return existing_cible
        else:
            # Créer une nouvelle cible
            validated_data['indicateur_id'] = indicateur
            return super().create(validated_data)


class CibleUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de cibles"""
    
    class Meta:
        model = Cible
        fields = ['valeur', 'condition']
    
    def validate_valeur(self, value):
        """Valider la valeur de la cible"""
        if value < 0:
            raise serializers.ValidationError("La valeur de la cible ne peut pas être négative")
        return value