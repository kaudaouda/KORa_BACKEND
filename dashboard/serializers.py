"""
Serializers pour l'application Dashboard
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Objectives, Indicateur, Observation, TableauBord
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
    tableau_bord_uuid = serializers.SerializerMethodField()
    
    class Meta:
        model = Objectives
        fields = [
            'uuid', 'number', 'libelle', 'cree_par', 'createur_nom', 'tableau_bord_uuid',
            'indicateurs_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'number', 'created_at', 'updated_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
    
    def get_indicateurs_count(self, obj):
        """Retourner le nombre d'indicateurs associés"""
        return obj.indicateurs.count()

    def get_tableau_bord_uuid(self, obj):
        return str(obj.tableau_bord.uuid) if obj.tableau_bord else None


class ObjectivesCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'objectifs"""
    tableau_bord = serializers.UUIDField(required=True)
    
    class Meta:
        model = Objectives
        fields = ['libelle', 'tableau_bord']
        extra_kwargs = {
            'number': {'required': False, 'allow_blank': True}
        }
    
    def create(self, validated_data):
        """Créer un objectif avec l'utilisateur connecté"""
        tableau_bord_uuid = validated_data.pop('tableau_bord')
        try:
            tb = TableauBord.objects.get(uuid=tableau_bord_uuid)
            validated_data['tableau_bord'] = tb
        except TableauBord.DoesNotExist:
            raise serializers.ValidationError({'tableau_bord': 'Tableau de bord introuvable'})
        
        validated_data['cree_par'] = self.context['request'].user
        
        # Générer automatiquement le numéro d'objectif si non fourni
        if 'number' not in validated_data or not validated_data['number']:
            # Compter les objectifs existants pour ce tableau
            existing_count = Objectives.objects.filter(tableau_bord=tb).count()
            validated_data['number'] = f"OB{existing_count + 1:02d}"
        
        # Créer l'objectif
        try:
            return super().create(validated_data)
        except Exception as e:
            raise serializers.ValidationError({'general': f'Erreur lors de la création: {str(e)}'})


class ObjectivesUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'objectifs"""
    tableau_bord = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Objectives
        fields = ['libelle', 'tableau_bord']
    
    def update(self, instance, validated_data):
        """Mettre à jour un objectif"""
        tb_uuid = validated_data.pop('tableau_bord', None)
        if tb_uuid is not None:
            try:
                instance.tableau_bord = TableauBord.objects.get(uuid=tb_uuid) if tb_uuid else None
            except TableauBord.DoesNotExist:
                raise serializers.ValidationError({'tableau_bord': 'Tableau de bord introuvable'})
        return super().update(instance, validated_data)


# ==================== TABLEAUX DE BORD ====================

class TableauBordSerializer(serializers.ModelSerializer):
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    type_label = serializers.CharField(source='get_type_display', read_only=True)
    type_tableau_code = serializers.CharField(source='type_tableau.code', read_only=True)
    type_tableau_nom = serializers.CharField(source='type_tableau.nom', read_only=True)
    valide_par_nom = serializers.CharField(source='valide_par.get_full_name', read_only=True)
    has_amendements = serializers.SerializerMethodField()
    
    def get_has_amendements(self, obj):
        """Vérifier si le tableau initial a des amendements"""
        return obj.has_amendements()

    class Meta:
        model = TableauBord
        fields = [
            'uuid', 'annee', 'processus', 'processus_nom',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 
            'type_label', 'initial_ref', 'cree_par', 'created_at', 'updated_at',
            'is_validated', 'date_validation', 'valide_par', 'valide_par_nom', 'has_amendements',
            'raison_amendement'
        ]
        read_only_fields = ['uuid', 'cree_par', 'created_at', 'updated_at', 'date_validation', 'valide_par']
        # Note: initial_ref n'est pas en read_only_fields pour permettre sa définition lors de la création d'amendements

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['cree_par'] = request.user
        
        # Gérer initial_ref si présent dans les données (pour les amendements)
        # initial_ref peut être un UUID (string) ou un objet TableauBord
        # On doit le retirer de validated_data car c'est un ForeignKey vers 'self' et Django peut avoir des problèmes
        initial_ref_uuid = validated_data.pop('initial_ref', None)
        
        # Créer l'instance sans initial_ref
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Création TableauBord - validated_data keys: {list(validated_data.keys())}, initial_ref_uuid: {initial_ref_uuid}")
        
        try:
            instance = super().create(validated_data)
            logger.info(f"Instance TableauBord créée avec succès: {instance.uuid}")
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'instance TableauBord: {str(e)}", exc_info=True)
            raise
        
        # Définir initial_ref après la création si nécessaire
        if initial_ref_uuid:
            # Si c'est un UUID (string), récupérer l'objet
            if isinstance(initial_ref_uuid, str):
                try:
                    initial_ref_obj = TableauBord.objects.get(uuid=initial_ref_uuid)
                    instance.initial_ref = initial_ref_obj
                    instance.save(update_fields=['initial_ref'])
                    logger.info(f"initial_ref défini avec succès: {initial_ref_uuid}")
                except TableauBord.DoesNotExist:
                    logger.warning(f"Tableau initial non trouvé pour initial_ref: {initial_ref_uuid}")
                except Exception as e:
                    logger.error(f"Erreur lors de la définition de initial_ref: {str(e)}", exc_info=True)
            else:
                # Si c'est déjà un objet
                instance.initial_ref = initial_ref_uuid
                instance.save(update_fields=['initial_ref'])
        
        return instance


# ==================== INDICATEURS ====================

class IndicateurSerializer(serializers.ModelSerializer):
    """Serializer pour les indicateurs"""
    objective_number = serializers.CharField(source='objective_id.number', read_only=True)
    objective_libelle = serializers.CharField(source='objective_id.libelle', read_only=True)
    frequence_nom = serializers.SerializerMethodField()
    allowed_periodes = serializers.SerializerMethodField()
    
    class Meta:
        model = Indicateur
        fields = [
            'uuid', 'libelle', 'objective_id', 'objective_number', 'objective_libelle',
            'frequence_id', 'frequence_nom', 'allowed_periodes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_frequence_nom(self, obj):
        """Retourner le nom de la fréquence si elle existe"""
        return obj.frequence_id.nom if obj.frequence_id else None
    
    def get_allowed_periodes(self, obj):
        """Retourner les périodes autorisées pour la fréquence de cet indicateur"""
        if not obj.frequence_id:
            return []
        from parametre.models import Periodicite
        return [p[0] for p in Periodicite.get_periodes_for_frequence(obj.frequence_id.nom)]


class IndicateurCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'indicateurs"""
    
    class Meta:
        model = Indicateur
        fields = ['libelle', 'objective_id']
    
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
        """Valider que la fréquence existe (optionnel)"""
        from parametre.models import Frequence
        # Si value est vide ou None, c'est OK
        if not value:
            return None
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


# ==================== OBSERVATIONS ====================

class ObservationSerializer(serializers.ModelSerializer):
    """Serializer pour les observations"""
    createur_nom = serializers.SerializerMethodField()
    indicateur_libelle = serializers.SerializerMethodField()
    indicateur_number = serializers.SerializerMethodField()
    indicateur_uuid = serializers.SerializerMethodField()
    
    class Meta:
        model = Observation
        fields = [
            'uuid', 'libelle', 'indicateur_id', 'indicateur_uuid', 'indicateur_libelle', 
            'indicateur_number', 'cree_par', 'createur_nom', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
    
    def get_indicateur_uuid(self, obj):
        """Retourner l'UUID de l'indicateur"""
        return obj.indicateur_id.uuid
    
    def get_indicateur_libelle(self, obj):
        """Retourner le libellé de l'indicateur"""
        return obj.indicateur_id.libelle
    
    def get_indicateur_number(self, obj):
        """Retourner le numéro de l'objectif associé"""
        return obj.indicateur_id.objective_id.number


class ObservationCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'observations"""
    
    class Meta:
        model = Observation
        fields = ['libelle', 'indicateur_id', 'cree_par']
    
    def validate_libelle(self, value):
        """Valider le libellé de l'observation"""
        if not value or not value.strip():
            raise serializers.ValidationError("Le libellé de l'observation ne peut pas être vide")
        return value.strip()
    
    def validate_indicateur_id(self, value):
        """Valider que l'indicateur n'a pas déjà une observation"""
        if Observation.objects.filter(indicateur_id=value).exists():
            raise serializers.ValidationError("Cet indicateur a déjà une observation")
        return value


class ObservationUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'observations"""
    
    class Meta:
        model = Observation
        fields = ['libelle']
    
    def validate_libelle(self, value):
        """Valider le libellé de l'observation"""
        if not value or not value.strip():
            raise serializers.ValidationError("Le libellé de l'observation ne peut pas être vide")
        return value.strip()