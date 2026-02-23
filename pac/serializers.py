"""
Serializers pour l'application PAC
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Pac, TraitementPac, PacSuivi, DetailsPac
from parametre.models import Processus, Preuve, Media
import logging

logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    """Serializer pour les utilisateurs"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'username', 
            'is_active', 'is_staff', 'is_superuser', 'date_joined', 'full_name'
        ]
        read_only_fields = ['id', 'date_joined', 'is_staff', 'is_superuser']
    
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
        if obj.cree_par:
            return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
        return "Utilisateur inconnu"


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
    processus_uuid = serializers.UUIDField(source='processus.uuid', read_only=True)
    annee_valeur = serializers.IntegerField(source='annee.annee', read_only=True, allow_null=True)
    annee_libelle = serializers.CharField(source='annee.libelle', read_only=True, allow_null=True)
    annee_uuid = serializers.UUIDField(source='annee.uuid', read_only=True, allow_null=True)
    type_tableau_code = serializers.CharField(source='type_tableau.code', read_only=True, allow_null=True)
    type_tableau_nom = serializers.CharField(source='type_tableau.nom', read_only=True, allow_null=True)
    type_tableau_uuid = serializers.UUIDField(source='type_tableau.uuid', read_only=True, allow_null=True)
    initial_ref_uuid = serializers.UUIDField(source='initial_ref.uuid', read_only=True, allow_null=True)
    createur_nom = serializers.SerializerMethodField()
    validateur_nom = serializers.SerializerMethodField()
    numero_pac = serializers.SerializerMethodField()

    class Meta:
        model = Pac
        fields = [
            'uuid', 'numero_pac', 'processus', 'processus_nom', 'processus_numero', 'processus_uuid',
            'annee', 'annee_valeur', 'annee_libelle', 'annee_uuid',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 'type_tableau_uuid',
            'initial_ref', 'initial_ref_uuid',
            'is_validated', 'validated_at', 'validated_by', 'validateur_nom',
            'cree_par', 'createur_nom', 'created_at'
        ]
        read_only_fields = ['uuid', 'numero_pac', 'is_validated', 'validated_at', 'validated_by', 'created_at']

    def get_numero_pac(self, obj):
        """Retourner le numéro du premier détail PAC associé, ou None"""
        premier_detail = obj.details.first()
        if premier_detail and premier_detail.numero_pac:
            return premier_detail.numero_pac
        return None

    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        if obj.cree_par:
            return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
        return "Utilisateur inconnu"

    def get_validateur_nom(self, obj):
        """Retourner le nom du validateur"""
        if obj.validated_by:
            return f"{obj.validated_by.first_name} {obj.validated_by.last_name}".strip() or obj.validated_by.username
        return None
    


class PacCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de PACs"""
    
    class Meta:
        model = Pac
        fields = [
            'processus', 'annee', 'type_tableau', 'initial_ref'
        ]
        extra_kwargs = {
            'annee': {'required': False, 'allow_null': True},
            'type_tableau': {'required': False, 'allow_null': True},
            'initial_ref': {'required': False, 'allow_null': True},
        }
    
    def validate(self, data):
        """Valider la cohérence entre type_tableau et initial_ref"""
        type_tableau = data.get('type_tableau')
        initial_ref = data.get('initial_ref')
        
        if type_tableau:
            # Vérifier si c'est un amendement
            if type_tableau.code in ['AMENDEMENT_1', 'AMENDEMENT_2']:
                # Les amendements doivent avoir un initial_ref
                if not initial_ref:
                    raise serializers.ValidationError(
                        f"Un amendement ({type_tableau.code}) doit être lié à un PAC initial. "
                        "Le champ 'initial_ref' est requis."
                    )
                
                # Vérifier que le PAC initial est validé
                if initial_ref and not initial_ref.is_validated:
                    raise serializers.ValidationError(
                        "Le PAC initial doit être validé avant de pouvoir créer un amendement. "
                        "Veuillez d'abord valider tous les détails et traitements du PAC initial."
                    )
            elif type_tableau.code == 'INITIAL':
                # Les PACs INITIAL ne doivent pas avoir d'initial_ref
                if initial_ref:
                    raise serializers.ValidationError(
                        "Un PAC INITIAL ne peut pas avoir de référence initiale (initial_ref)."
                    )
        
        return data
    
    def create(self, validated_data):
        """Créer un PAC avec l'utilisateur connecté"""
        validated_data['cree_par'] = self.context['request'].user
        
        # S'assurer que processus est toujours fourni
        if 'processus' not in validated_data or validated_data['processus'] is None:
            raise serializers.ValidationError("Le champ 'processus' est requis")
        
        return super().create(validated_data)


class PacUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de PACs"""
    
    class Meta:
        model = Pac
        fields = [
            'processus', 'annee', 'type_tableau'
        ]
        extra_kwargs = {
            'annee': {'required': False, 'allow_null': True},
            'type_tableau': {'required': False, 'allow_null': True},
        }
    
    def validate_processus(self, value):
        """Empêcher la modification du processus après création"""
        if self.instance and self.instance.processus != value:
            raise serializers.ValidationError(
                "Le processus ne peut pas être modifié après la création du PAC"
            )
        return value
    
    def update(self, instance, validated_data):
        """Mettre à jour un PAC"""
        # Protection : empêcher la modification si le PAC est validé
        if instance.is_validated:
            raise serializers.ValidationError(
                "Ce PAC est validé. Les champs ne peuvent plus être modifiés."
            )
        
        # Le numéro PAC et le créateur ne peuvent pas être modifiés
        return super().update(instance, validated_data)


class TraitementPacSerializer(serializers.ModelSerializer):
    """Serializer pour les traitements PAC"""
    type_action_nom = serializers.CharField(source='type_action.nom', read_only=True, allow_null=True)
    preuve_description = serializers.CharField(source='preuve.description', read_only=True, allow_null=True)
    preuve_media_url = serializers.SerializerMethodField()
    details_pac_uuid = serializers.UUIDField(source='details_pac.uuid', read_only=True, allow_null=True)
    details_pac_libelle = serializers.CharField(source='details_pac.libelle', read_only=True, allow_null=True)
    pac_numero = serializers.CharField(source='details_pac.numero_pac', read_only=True, allow_null=True)
    pac_uuid = serializers.SerializerMethodField()
    responsable_direction_nom = serializers.CharField(source='responsable_direction.nom', read_only=True, allow_null=True)
    responsable_sous_direction_nom = serializers.CharField(source='responsable_sous_direction.nom', read_only=True, allow_null=True)

    # Exposer aussi les M2M (lecture seule pour compat)
    responsables_directions = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    responsables_sous_directions = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )

    class Meta:
        model = TraitementPac
        fields = [
            'uuid', 'details_pac', 'details_pac_uuid', 'details_pac_libelle',
            'pac_uuid', 'pac_numero', 'action', 'type_action',
            'type_action_nom', 'responsable_direction', 'responsable_direction_nom',
            'responsable_sous_direction', 'responsable_sous_direction_nom',
            'responsables_directions', 'responsables_sous_directions',
            'preuve', 'preuve_description', 'preuve_media_url', 'delai_realisation'
        ]
        read_only_fields = ['uuid']

    def get_pac_uuid(self, obj):
        """Retourner l'UUID du PAC de manière sécurisée"""
        try:
            if obj.details_pac and obj.details_pac.pac:
                return str(obj.details_pac.pac.uuid)
        except Exception:
            pass
        return None

    def get_preuve_media_url(self, obj):
        """Retourner l'URL du premier média de la preuve"""
        try:
            if obj.preuve and obj.preuve.medias.exists():
                # Prendre le premier média
                media = obj.preuve.medias.first()
                if media:
                    if hasattr(media, 'get_url'):
                        return media.get_url()
                    return getattr(media, 'url_fichier', None)
        except Exception as e:
            # En cas d'erreur, retourner None
            print(f"Erreur dans get_preuve_media_url: {e}")
        return None


class TraitementPacCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de traitements PAC"""
    # Définir explicitement details_pac comme PrimaryKeyRelatedField pour accepter l'UUID
    details_pac = serializers.PrimaryKeyRelatedField(
        queryset=DetailsPac.objects.all(),
        required=True
    )
    # Nouveau: accepter des listes d'UUID en entrée pour M2M
    responsables_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    responsables_sous_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    
    class Meta:
        model = TraitementPac
        fields = [
            'details_pac', 'action', 'type_action', 'responsable_direction', 
            'responsable_sous_direction', 'responsables_directions', 'responsables_sous_directions',
            'preuve', 'delai_realisation'
        ]
        extra_kwargs = {
            'type_action': {'required': False, 'allow_null': True},
            'delai_realisation': {'required': False, 'allow_null': True}
        }
    
    def validate_details_pac(self, value):
        """Valider qu'il n'y a pas déjà un traitement pour ce détail (OneToOne)"""
        if value and TraitementPac.objects.filter(details_pac=value).exists():
            raise serializers.ValidationError(
                "Un traitement existe déjà pour ce détail PAC. Un détail ne peut avoir qu'un seul traitement."
            )
        
        # Protection : empêcher la création de traitement si le PAC est validé
        if value and hasattr(value, 'pac') and value.pac.is_validated:
            raise serializers.ValidationError(
                "Ce PAC est validé. Impossible de créer un nouveau traitement."
            )
        
        return value
    
    def validate_delai_realisation(self, value):
        """Valider que le délai de réalisation est >= aujourd'hui et >= période de réalisation du PAC"""
        # Si le champ est null/None, ne pas valider (champ optionnel)
        if value is None:
            return None
            
        from django.utils import timezone
        today = timezone.now().date()
        
        if value < today:
            raise serializers.ValidationError(
                "Le délai de réalisation doit être égal ou supérieur à la date d'aujourd'hui."
            )
        
        # Vérifier si on a accès aux détails PAC pour comparer avec sa période de réalisation
        details_pac = self.initial_data.get('details_pac') if hasattr(self, 'initial_data') else None
        if details_pac:
            try:
                details_pac_obj = DetailsPac.objects.get(uuid=details_pac)
                if details_pac_obj.periode_de_realisation and value < details_pac_obj.periode_de_realisation:
                    raise serializers.ValidationError(
                        f"Le délai de réalisation doit être égal ou supérieur à la période de réalisation du détail PAC ({details_pac_obj.periode_de_realisation.strftime('%d/%m/%Y')})."
                    )
            except DetailsPac.DoesNotExist:
                pass
        
        return value

    def create(self, validated_data):
        # Extraire les listes M2M si présentes
        resp_dirs = self.initial_data.get('responsables_directions', [])
        resp_sous = self.initial_data.get('responsables_sous_directions', [])

        # Retirer des validated_data s'ils y sont (on gère après création)
        validated_data.pop('responsables_directions', None)
        validated_data.pop('responsables_sous_directions', None)

        instance = super().create(validated_data)

        # Synchroniser M2M si fournis
        from parametre.models import Direction, SousDirection
        if isinstance(resp_dirs, list) and len(resp_dirs) > 0:
            instance.responsables_directions.set(
                list(Direction.objects.filter(uuid__in=resp_dirs))
            )
        if isinstance(resp_sous, list) and len(resp_sous) > 0:
            instance.responsables_sous_directions.set(
                list(SousDirection.objects.filter(uuid__in=resp_sous))
            )

        return instance


class TraitementPacUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de traitements PAC"""
    responsables_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    responsables_sous_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    
    class Meta:
        model = TraitementPac
        fields = [
            'action', 'type_action', 'responsable_direction', 
            'responsable_sous_direction', 'responsables_directions', 'responsables_sous_directions',
            'preuve', 'delai_realisation'
        ]
        extra_kwargs = {
            'action': {'required': False},
            'type_action': {'required': False, 'allow_null': True},
            'responsable_direction': {'required': False, 'allow_null': True},
            'responsable_sous_direction': {'required': False, 'allow_null': True},
            'preuve': {'required': False, 'allow_null': True},
            'delai_realisation': {'required': False, 'allow_null': True},
            'responsables_directions': {'required': False},
            'responsables_sous_directions': {'required': False}
        }
    
    def validate_delai_realisation(self, value):
        """Valider que le délai de réalisation est >= aujourd'hui et >= période de réalisation du PAC"""
        # Si le champ est null/None, ne pas valider (champ optionnel)
        if value is None:
            return None
            
        from django.utils import timezone
        today = timezone.now().date()
        
        if value < today:
            raise serializers.ValidationError(
                "Le délai de réalisation doit être égal ou supérieur à la date d'aujourd'hui."
            )
        
        # Pour la mise à jour, on peut accéder aux détails PAC via l'instance
        if hasattr(self, 'instance') and self.instance and self.instance.details_pac:
            details_pac_obj = self.instance.details_pac
            if details_pac_obj.periode_de_realisation and value < details_pac_obj.periode_de_realisation:
                raise serializers.ValidationError(
                    f"Le délai de réalisation doit être égal ou supérieur à la période de réalisation du détail PAC ({details_pac_obj.periode_de_realisation.strftime('%d/%m/%Y')})."
                )
        
        return value

    def update(self, instance, validated_data):
        # Protection : empêcher la modification si le PAC est validé
        if instance.details_pac and instance.details_pac.pac.is_validated:
            raise serializers.ValidationError(
                "Ce PAC est validé. Les champs de traitement ne peuvent plus être modifiés."
            )
        
        resp_dirs = self.initial_data.get('responsables_directions', None)
        resp_sous = self.initial_data.get('responsables_sous_directions', None)

        validated_data.pop('responsables_directions', None)
        validated_data.pop('responsables_sous_directions', None)

        instance = super().update(instance, validated_data)

        from parametre.models import Direction, SousDirection
        if isinstance(resp_dirs, list):
            instance.responsables_directions.set(
                list(Direction.objects.filter(uuid__in=resp_dirs))
            )
        if isinstance(resp_sous, list):
            instance.responsables_sous_directions.set(
                list(SousDirection.objects.filter(uuid__in=resp_sous))
            )

        return instance


class PacSuiviSerializer(serializers.ModelSerializer):
    """Serializer pour les suivis PAC"""
    etat_nom = serializers.CharField(source='etat_mise_en_oeuvre.nom', read_only=True)
    appreciation_nom = serializers.CharField(source='appreciation.nom', read_only=True)
    traitement_action = serializers.CharField(source='traitement.action', read_only=True, allow_null=True)
    traitement_uuid = serializers.UUIDField(source='traitement.uuid', read_only=True, allow_null=True)
    statut_nom = serializers.CharField(source='statut.nom', read_only=True, allow_null=True)
    preuve_uuid = serializers.UUIDField(source='preuve.uuid', read_only=True, allow_null=True)
    preuve_description = serializers.CharField(source='preuve.description', read_only=True, allow_null=True)
    preuve_media_url = serializers.SerializerMethodField()
    preuve_media_urls = serializers.SerializerMethodField()
    preuve_medias = serializers.SerializerMethodField()
    createur_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = PacSuivi
        fields = [
            'uuid', 'traitement', 'traitement_uuid', 'traitement_action', 'etat_mise_en_oeuvre',
            'etat_nom', 'resultat', 'appreciation', 'appreciation_nom',
            'preuve', 'preuve_uuid', 'preuve_description', 'preuve_media_url', 'preuve_media_urls', 'preuve_medias',
            'statut', 'statut_nom', 'date_mise_en_oeuvre_effective',
            'date_cloture', 'cree_par', 'createur_nom', 'created_at'
        ]
        read_only_fields = ['uuid', 'created_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        if obj.cree_par:
            return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
        return "Utilisateur inconnu"

    def get_preuve_media_url(self, obj):
        """Retourner l'URL du premier média de la preuve"""
        try:
            if obj.preuve and obj.preuve.medias.exists():
                media = obj.preuve.medias.first()
                if media:
                    if hasattr(media, 'get_url'):
                        url = media.get_url()
                        print(f"Debug SuiviSerializer get_preuve_media_url - URL trouvée via get_url(): {url}")
                        return url
                    url = getattr(media, 'url_fichier', None)
                    print(f"Debug SuiviSerializer get_preuve_media_url - URL trouvée via url_fichier: {url}")
                    return url
                else:
                    print(f"Debug SuiviSerializer get_preuve_media_url - Aucun média trouvé dans preuve.medias")
            else:
                print(f"Debug SuiviSerializer get_preuve_media_url - Pas de preuve ou pas de médias. Preuve: {obj.preuve}, Médias existent: {obj.preuve.medias.exists() if obj.preuve else False}")
        except Exception as e:
            print(f"Debug SuiviSerializer get_preuve_media_url - Erreur: {e}")
        return None

    def get_preuve_media_urls(self, obj):
        """Retourner la liste de toutes les URLs des médias de la preuve"""
        urls = []
        try:
            if obj.preuve:
                for media in obj.preuve.medias.all():
                    url = None
                    if hasattr(media, 'get_url'):
                        url = media.get_url()
                    else:
                        url = getattr(media, 'url_fichier', None)
                    if url:
                        urls.append(url)
        except Exception:
            pass
        return urls

    def get_preuve_medias(self, obj):
        """
        Retourner la liste des médias avec uuid, url et description
        (nécessaire côté frontend pour afficher la description et permettre la suppression d'un média).
        """
        medias = []
        try:
            if obj.preuve:
                for media in obj.preuve.medias.all():
                    url = None
                    if hasattr(media, 'get_url'):
                        url = media.get_url()
                    else:
                        url = getattr(media, 'url_fichier', None)
                    medias.append({
                        'uuid': str(media.uuid),
                        'url': url,
                        'description': getattr(media, 'description', None),
                    })
        except Exception:
            pass
        return medias


class PacSuiviCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de suivis PAC"""
    
    class Meta:
        model = PacSuivi
        fields = [
            'traitement', 'etat_mise_en_oeuvre', 'resultat', 'appreciation',
            'preuve', 'statut', 'date_mise_en_oeuvre_effective', 'date_cloture'
        ]
    
    def validate_traitement(self, value):
        """Valider que le traitement est dans un PAC validé et qu'il n'y a pas déjà un suivi (OneToOne)"""
        if value:
            # Permettre la création lors de la copie d'amendement
            from_amendment_copy = self.context.get('request') and self.context['request'].data.get('from_amendment_copy', False)
            
            # Vérifier que le PAC parent est validé (sauf lors de la copie d'amendement)
            if not value.details_pac.pac.is_validated and not from_amendment_copy:
                raise serializers.ValidationError(
                    "Le PAC doit être validé avant de pouvoir créer un suivi. "
                    "Veuillez d'abord valider tous les détails et traitements du PAC."
                )
            # Vérifier qu'il n'y a pas déjà un suivi (OneToOne)
            if PacSuivi.objects.filter(traitement=value).exists():
                raise serializers.ValidationError(
                    "Un suivi existe déjà pour ce traitement. Un traitement ne peut avoir qu'un seul suivi."
                )
        return value

    def validate_date_mise_en_oeuvre_effective(self, value):
        """Valider que la date de mise en œuvre effective est >= aujourd'hui (sauf copie d'amendement)"""
        if value:
            request = self.context.get('request')
            from_amendment_copy = request and (
                request.data.get('from_amendment_copy', False) or
                request.data.get('from_amendment_copy') == 'true' or
                request.data.get('from_amendment_copy') is True
            )
            if not from_amendment_copy:
                from django.utils import timezone
                today = timezone.now().date()
                if value < today:
                    raise serializers.ValidationError(
                        "La date de mise en œuvre effective doit être égale ou supérieure à la date d'aujourd'hui."
                    )
        return value

    def validate_date_cloture(self, value):
        """Valider que la date de clôture est >= aujourd'hui (sauf copie d'amendement)"""
        if value:
            request = self.context.get('request')
            from_amendment_copy = request and (
                request.data.get('from_amendment_copy', False) or
                request.data.get('from_amendment_copy') == 'true' or
                request.data.get('from_amendment_copy') is True
            )
            if not from_amendment_copy:
                from django.utils import timezone
                today = timezone.now().date()
                if value < today:
                    raise serializers.ValidationError(
                        "La date de clôture doit être égale ou supérieure à la date d'aujourd'hui."
                    )
        return value

    def create(self, validated_data):
        """Créer un suivi avec l'utilisateur connecté"""
        validated_data['cree_par'] = self.context['request'].user
        return super().create(validated_data)


class PacCompletSerializer(serializers.ModelSerializer):
    """Serializer complet pour un PAC avec tous ses traitements et suivis"""
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    processus_numero = serializers.CharField(source='processus.numero_processus', read_only=True)
    processus_uuid = serializers.UUIDField(source='processus.uuid', read_only=True)
    annee_valeur = serializers.IntegerField(source='annee.annee', read_only=True, allow_null=True)
    annee_libelle = serializers.CharField(source='annee.libelle', read_only=True, allow_null=True)
    annee_uuid = serializers.UUIDField(source='annee.uuid', read_only=True, allow_null=True)
    type_tableau_code = serializers.CharField(source='type_tableau.code', read_only=True, allow_null=True)
    type_tableau_nom = serializers.CharField(source='type_tableau.nom', read_only=True, allow_null=True)
    type_tableau_uuid = serializers.UUIDField(source='type_tableau.uuid', read_only=True, allow_null=True)
    initial_ref_uuid = serializers.UUIDField(source='initial_ref.uuid', read_only=True, allow_null=True)
    createur_nom = serializers.SerializerMethodField()
    numero_pac = serializers.SerializerMethodField()

    # Inclure tous les détails avec leurs traitements et suivis
    details = serializers.SerializerMethodField()

    class Meta:
        model = Pac
        fields = [
            'uuid', 'numero_pac', 'processus', 'processus_nom', 'processus_numero', 'processus_uuid',
            'annee', 'annee_valeur', 'annee_libelle', 'annee_uuid',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 'type_tableau_uuid',
            'initial_ref', 'initial_ref_uuid',
            'cree_par', 'createur_nom', 'is_validated', 'validated_at', 'validated_by',
            'created_at', 'details'
        ]
        read_only_fields = ['uuid', 'numero_pac', 'is_validated', 'validated_at', 'validated_by', 'created_at']

    def get_numero_pac(self, obj):
        """Retourner le numéro du premier détail PAC associé, ou None"""
        premier_detail = obj.details.first()
        if premier_detail and premier_detail.numero_pac:
            return premier_detail.numero_pac
        return None

    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        if obj.cree_par:
            return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
        return "Utilisateur inconnu"
    
    def get_details(self, obj):
        """Récupérer tous les détails avec leurs traitements et suivis"""
        # Forcer le rafraîchissement depuis la base de données (éviter le cache)
        # Trier par numero_pac pour préserver l'ordre (si les numéros sont séquentiels)
        # Sinon, utiliser created_at comme fallback pour préserver l'ordre de création
        details = DetailsPac.objects.filter(pac=obj).select_related(
            'dysfonctionnement_recommandation',
            'nature',
            'categorie',
            'source',
            'traitement__suivi__etat_mise_en_oeuvre',
            'traitement__suivi__appreciation',
            'traitement__suivi__statut',
            'traitement__suivi__cree_par',
            'traitement__suivi__preuve'
        ).order_by('numero_pac')
        
        # Log pour diagnostiquer
        details_count = details.count()
        logger.info(f"[PacCompletSerializer] PAC {obj.uuid} - Nombre de détails trouvés dans la DB: {details_count}")
        if details_count > 0:
            logger.info(f"[PacCompletSerializer] UUIDs des détails: {[str(d.uuid) for d in details]}")
        details_data = []
        
        for detail in details:
            detail_data = {
                'uuid': str(detail.uuid),
                'numero_pac': detail.numero_pac,
                'libelle': detail.libelle,
                'dysfonctionnement_recommandation': detail.dysfonctionnement_recommandation.uuid if detail.dysfonctionnement_recommandation else None,
                'dysfonctionnement_recommandation_nom': detail.dysfonctionnement_recommandation.nom if detail.dysfonctionnement_recommandation else None,
                'nature': detail.nature.uuid if detail.nature else None,
                'nature_nom': detail.nature.nom if detail.nature else None,
                'categorie': detail.categorie.uuid if detail.categorie else None,
                'categorie_nom': detail.categorie.nom if detail.categorie else None,
                'source': detail.source.uuid if detail.source else None,
                'source_nom': detail.source.nom if detail.source else None,
                'periode_de_realisation': detail.periode_de_realisation,
                'traitement': None
            }
            
            # Récupérer le traitement pour ce détail (OneToOne)
            if hasattr(detail, 'traitement') and detail.traitement:
                traitement = detail.traitement
                # Récupérer les responsables M2M
                responsables_directions = [
                    {
                        'uuid': str(dir.uuid),
                        'nom': dir.nom
                    }
                    for dir in traitement.responsables_directions.all()
                ] if hasattr(traitement, 'responsables_directions') else []
                
                responsables_sous_directions = [
                    {
                        'uuid': str(sous_dir.uuid),
                        'nom': sous_dir.nom
                    }
                    for sous_dir in traitement.responsables_sous_directions.all()
                ] if hasattr(traitement, 'responsables_sous_directions') else []
                
                traitement_data = {
                    'uuid': str(traitement.uuid),
                    'action': traitement.action,
                    'type_action': traitement.type_action.uuid if traitement.type_action else None,
                    'type_action_nom': traitement.type_action.nom if traitement.type_action else None,
                    'responsable_direction': traitement.responsable_direction.uuid if traitement.responsable_direction else None,
                    'responsable_direction_nom': traitement.responsable_direction.nom if traitement.responsable_direction else None,
                    'responsable_sous_direction': traitement.responsable_sous_direction.uuid if traitement.responsable_sous_direction else None,
                    'responsable_sous_direction_nom': traitement.responsable_sous_direction.nom if traitement.responsable_sous_direction else None,
                    'responsables_directions': responsables_directions,
                    'responsables_sous_directions': responsables_sous_directions,
                    'delai_realisation': traitement.delai_realisation,
                    'preuve': traitement.preuve.uuid if traitement.preuve else None,
                    'preuve_uuid': str(traitement.preuve.uuid) if traitement.preuve else None,
                    'preuve_description': traitement.preuve.description if traitement.preuve else None,
                    'preuve_media_url': self.get_preuve_media_url(traitement),
                    'preuve_medias': self.get_preuve_medias(traitement),
                    'suivi': None
                }
                
                # Récupérer le suivi pour ce traitement (OneToOne - relation inverse)
                # Vérifier si le suivi existe en utilisant la relation inverse
                try:
                    suivi = traitement.suivi
                    if suivi:
                        suivi_data = {
                            'uuid': str(suivi.uuid),
                            'etat_mise_en_oeuvre': suivi.etat_mise_en_oeuvre.uuid if suivi.etat_mise_en_oeuvre else None,
                            'etat_nom': suivi.etat_mise_en_oeuvre.nom if suivi.etat_mise_en_oeuvre else None,
                            'resultat': suivi.resultat,
                            'appreciation': suivi.appreciation.uuid if suivi.appreciation else None,
                            'appreciation_nom': suivi.appreciation.nom if suivi.appreciation else None,
                            'statut': suivi.statut.uuid if suivi.statut else None,
                            'statut_nom': suivi.statut.nom if suivi.statut else None,
                            'date_mise_en_oeuvre_effective': suivi.date_mise_en_oeuvre_effective,
                            'date_cloture': suivi.date_cloture,
                            'createur_nom': f"{suivi.cree_par.first_name} {suivi.cree_par.last_name}".strip() or suivi.cree_par.username,
                            'created_at': suivi.created_at,
                            'preuve': suivi.preuve.uuid if suivi.preuve else None,
                            'preuve_uuid': str(suivi.preuve.uuid) if suivi.preuve else None,
                            'preuve_description': suivi.preuve.description if suivi.preuve else None,
                            'preuve_media_url': self.get_preuve_media_url_suivi(suivi),
                            'preuve_media_urls': self.get_preuve_media_urls_suivi(suivi),
                            'preuve_medias': self.get_preuve_medias_suivi(suivi)
                        }
                        traitement_data['suivi'] = suivi_data
                except (AttributeError, PacSuivi.DoesNotExist):
                    # Pas de suivi pour ce traitement
                    pass
                
                detail_data['traitement'] = traitement_data
            
            details_data.append(detail_data)
        
        return details_data
    
    def get_preuve_media_url(self, traitement):
        """Retourner l'URL du premier média de la preuve du traitement"""
        try:
            if traitement.preuve and traitement.preuve.medias.exists():
                media = traitement.preuve.medias.first()
                if media:
                    if hasattr(media, 'get_url'):
                        return media.get_url()
                    return getattr(media, 'url_fichier', None)
        except Exception:
            pass
        return None
    
    def get_preuve_media_url_suivi(self, suivi):
        """Retourner l'URL du premier média de la preuve du suivi"""
        try:
            if suivi.preuve and suivi.preuve.medias.exists():
                media = suivi.preuve.medias.first()
                if media:
                    if hasattr(media, 'get_url'):
                        return media.get_url()
                    return getattr(media, 'url_fichier', None)
        except Exception:
            pass
        return None
    
    def get_preuve_media_urls_suivi(self, suivi):
        """Retourner la liste de toutes les URLs des médias de la preuve du suivi"""
        urls = []
        try:
            if suivi.preuve:
                for media in suivi.preuve.medias.all():
                    url = None
                    if hasattr(media, 'get_url'):
                        url = media.get_url()
                    else:
                        url = getattr(media, 'url_fichier', None)
                    if url:
                        urls.append(url)
        except Exception:
            pass
        return urls
    
    def get_preuve_medias(self, traitement):
        """Retourner la liste des médias avec uuid, url et description pour le traitement"""
        medias = []
        try:
            if traitement.preuve:
                for media in traitement.preuve.medias.all():
                    url = None
                    if hasattr(media, 'get_url'):
                        url = media.get_url()
                    else:
                        url = getattr(media, 'url_fichier', None)
                    medias.append({
                        'uuid': str(media.uuid),
                        'url': url,
                        'description': getattr(media, 'description', None),
                    })
        except Exception:
            pass
        return medias
    
    def get_preuve_medias_suivi(self, suivi):
        """Retourner la liste des médias avec uuid, url et description pour le suivi"""
        medias = []
        try:
            if suivi.preuve:
                for media in suivi.preuve.medias.all():
                    url = None
                    if hasattr(media, 'get_url'):
                        url = media.get_url()
                    else:
                        url = getattr(media, 'url_fichier', None)
                    medias.append({
                        'uuid': str(media.uuid),
                        'url': url,
                        'description': getattr(media, 'description', None),
                    })
        except Exception:
            pass
        return medias


class PacSuiviUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour des suivis PAC"""

    class Meta:
        model = PacSuivi
        fields = [
            'traitement', 'etat_mise_en_oeuvre', 'resultat', 'appreciation',
            'preuve', 'statut', 'date_mise_en_oeuvre_effective', 'date_cloture'
        ]
    
    def update(self, instance, validated_data):
        """Mettre à jour un suivi PAC"""
        # Protection : empêcher la modification si le PAC n'est pas validé
        if instance.traitement and instance.traitement.details_pac and not instance.traitement.details_pac.pac.is_validated:
            raise serializers.ValidationError(
                "Le PAC doit être validé avant de pouvoir modifier un suivi."
            )
        
        return super().update(instance, validated_data)
    
    def validate_date_mise_en_oeuvre_effective(self, value):
        """Valider que la date de mise en œuvre effective est >= aujourd'hui"""
        if value:
            from django.utils import timezone
            today = timezone.now().date()
            
            if value < today:
                raise serializers.ValidationError(
                    "La date de mise en œuvre effective doit être égale ou supérieure à la date d'aujourd'hui."
                )
        
        return value
    
    def validate_date_cloture(self, value):
        """Valider que la date de clôture est >= aujourd'hui"""
        if value:
            from django.utils import timezone
            today = timezone.now().date()
            
            if value < today:
                raise serializers.ValidationError(
                    "La date de clôture doit être égale ou supérieure à la date d'aujourd'hui."
                )
        
        return value


# ==================== SERIALIZERS DETAILS PAC ====================

class DetailsPacSerializer(serializers.ModelSerializer):
    """Serializer pour les détails de PAC"""
    pac_uuid = serializers.UUIDField(source='pac.uuid', read_only=True)
    dysfonctionnement_recommandation_nom = serializers.CharField(
        source='dysfonctionnement_recommandation.nom', 
        read_only=True, 
        allow_null=True
    )
    dysfonctionnement_recommandation_uuid = serializers.UUIDField(
        source='dysfonctionnement_recommandation.uuid', 
        read_only=True, 
        allow_null=True
    )
    nature_nom = serializers.CharField(
        source='nature.nom', 
        read_only=True, 
        allow_null=True
    )
    nature_uuid = serializers.UUIDField(
        source='nature.uuid', 
        read_only=True, 
        allow_null=True
    )
    categorie_nom = serializers.CharField(
        source='categorie.nom', 
        read_only=True, 
        allow_null=True
    )
    categorie_uuid = serializers.UUIDField(
        source='categorie.uuid', 
        read_only=True, 
        allow_null=True
    )
    source_nom = serializers.CharField(
        source='source.nom', 
        read_only=True, 
        allow_null=True
    )
    source_uuid = serializers.UUIDField(
        source='source.uuid', 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = DetailsPac
        fields = [
            'uuid', 'numero_pac', 'pac', 'pac_uuid',
            'dysfonctionnement_recommandation', 'dysfonctionnement_recommandation_nom', 
            'dysfonctionnement_recommandation_uuid',
            'libelle',
            'nature', 'nature_nom', 'nature_uuid',
            'categorie', 'categorie_nom', 'categorie_uuid',
            'source', 'source_nom', 'source_uuid',
            'periode_de_realisation'
        ]
        read_only_fields = ['uuid', 'numero_pac']
    
    def validate_periode_de_realisation(self, value):
        """Valider que la période de réalisation est >= aujourd'hui"""
        if value:
            from django.utils import timezone
            today = timezone.now().date()
            
            if value < today:
                raise serializers.ValidationError(
                    "La période de réalisation doit être égale ou supérieure à la date d'aujourd'hui."
                )
        
        return value


class DetailsPacCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de détails de PAC"""
    # Permettre de spécifier le numero_pac lors de la copie d'amendement
    numero_pac = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = DetailsPac
        fields = [
            'pac', 'numero_pac', 'dysfonctionnement_recommandation', 'libelle',
            'nature', 'categorie', 'source', 'periode_de_realisation'
        ]
        extra_kwargs = {
            'dysfonctionnement_recommandation': {'required': False, 'allow_null': True},
            'libelle': {'required': False, 'allow_null': True, 'allow_blank': True},
            'nature': {'required': False, 'allow_null': True},
            'categorie': {'required': False, 'allow_null': True},
            'source': {'required': False, 'allow_null': True},
            'periode_de_realisation': {'required': False, 'allow_null': True},
        }
    
    def validate_pac(self, value):
        """Vérifier que l'utilisateur a accès au processus du PAC (comme dashboard, unicité globale)"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            from parametre.permissions import user_has_access_to_processus
            if not user_has_access_to_processus(request.user, value.processus.uuid):
                raise serializers.ValidationError(
                    "Vous n'avez pas les permissions pour ajouter un détail à ce PAC."
                )
        
        # Protection : empêcher la création de détail si le PAC est validé
        if value.is_validated:
            raise serializers.ValidationError(
                "Ce PAC est validé. Impossible de créer un nouveau détail."
            )
        
        return value
    
    def validate_periode_de_realisation(self, value):
        """Valider que la période de réalisation est >= aujourd'hui (sauf copie d'amendement)"""
        if value:
            from django.utils import timezone
            request = self.context.get('request')
            from_amendment_copy = request and (
                request.data.get('from_amendment_copy', False) or
                request.data.get('from_amendment_copy') == 'true' or
                request.data.get('from_amendment_copy') is True
            )
            if not from_amendment_copy:
                today = timezone.now().date()
                if value < today:
                    raise serializers.ValidationError(
                        "La période de réalisation doit être égale ou supérieure à la date d'aujourd'hui."
                    )
        return value

    def create(self, validated_data):
        """Créer un détail PAC avec génération automatique du numéro"""
        # Vérifier si c'est une copie d'amendement (flag from_amendment_copy)
        request = self.context.get('request')
        from_amendment_copy = request and (
            request.data.get('from_amendment_copy', False) or 
            request.data.get('from_amendment_copy') == 'true' or
            request.data.get('from_amendment_copy') == True
        )
        numero_pac_provided = validated_data.get('numero_pac')
        pac = validated_data.get('pac')
        
        # Vérifier si le PAC est un amendement
        is_amendment = False
        if pac and pac.type_tableau:
            type_code = pac.type_tableau.code
            is_amendment = type_code in ['AMENDEMENT_1', 'AMENDEMENT_2']
        
        logger.info(f"[DetailsPacCreateSerializer] Création détail - from_amendment_copy: {from_amendment_copy}, is_amendment: {is_amendment}, numero_pac_provided: {numero_pac_provided}, pac_type: {pac.type_tableau.code if pac and pac.type_tableau else None}")
        
        # CAS 1: Copie d'amendement avec numéro fourni - TOUJOURS utiliser le numéro fourni
        # Pour les amendements, on peut toujours réutiliser le même numéro que l'initial
        if is_amendment and numero_pac_provided and str(numero_pac_provided).strip():
            original_numero = str(numero_pac_provided).strip()
            logger.info(f"[DetailsPacCreateSerializer] Amendement - Conservation du numéro depuis l'initial: {original_numero}")
            validated_data['numero_pac'] = original_numero
            detail = super().create(validated_data)
            logger.info(f"[DetailsPacCreateSerializer] ✅ Détail créé avec UUID: {detail.uuid}, Numéro: {detail.numero_pac}")
            return detail
        
        # CAS 1b: Copie d'amendement (flag explicite) avec numéro fourni
        if from_amendment_copy and numero_pac_provided and str(numero_pac_provided).strip():
            original_numero = str(numero_pac_provided).strip()
            logger.info(f"[DetailsPacCreateSerializer] Copie d'amendement (flag) - Conservation du numéro: {original_numero}")
            validated_data['numero_pac'] = original_numero
            detail = super().create(validated_data)
            logger.info(f"[DetailsPacCreateSerializer] ✅ Détail créé avec UUID: {detail.uuid}, Numéro: {detail.numero_pac}")
            return detail
        
        # CAS 2: Amendement sans numéro fourni
        # Si c'est une copie d'amendement (flag explicite), chercher le numéro depuis l'initial
        # Sinon (amendement vide avec ajout manuel), générer un nouveau numéro qui s'incrémente
        if is_amendment and not numero_pac_provided:
            if from_amendment_copy:
                # CAS 2a: Copie d'amendement - Trouver le numéro correspondant depuis l'initial
                if pac and pac.initial_ref:
                    initial_pac = pac.initial_ref
                    # Compter combien de détails existent déjà dans cet amendement
                    existing_details_count = DetailsPac.objects.filter(pac=pac).count()
                    # Récupérer les détails de l'initial triés par numero_pac
                    initial_details = DetailsPac.objects.filter(pac=initial_pac).exclude(
                        numero_pac__isnull=True
                    ).exclude(
                        numero_pac__exact=''
                    ).order_by('numero_pac')
                    
                    if initial_details.exists():
                        # Utiliser le numéro correspondant au nombre de détails existants
                        if existing_details_count < initial_details.count():
                            corresponding_detail = initial_details[existing_details_count]
                            numero_pac_provided = corresponding_detail.numero_pac
                            logger.info(f"[DetailsPacCreateSerializer] Amendement (copie) - Utilisation du numéro correspondant depuis l'initial: {numero_pac_provided}")
                        else:
                            # Si on a plus de détails que l'initial, générer un nouveau numéro
                            validated_data['numero_pac'] = self.generate_numero_pac()
                            logger.info(f"[DetailsPacCreateSerializer] Amendement (copie) - Plus de détails que l'initial, génération nouveau numéro")
                            return super().create(validated_data)
                    else:
                        # Pas de détails dans l'initial, générer un nouveau numéro
                        validated_data['numero_pac'] = self.generate_numero_pac()
                        logger.info(f"[DetailsPacCreateSerializer] Amendement (copie) - Aucun détail dans l'initial, génération nouveau numéro")
                        return super().create(validated_data)
                else:
                    # Pas d'initial_ref, générer un nouveau numéro
                    validated_data['numero_pac'] = self.generate_numero_pac()
                    logger.info(f"[DetailsPacCreateSerializer] Amendement (copie) sans initial_ref, génération nouveau numéro")
                    return super().create(validated_data)
            else:
                # CAS 2b: Amendement vide avec ajout manuel - Générer un nouveau numéro qui s'incrémente
                validated_data['numero_pac'] = self.generate_numero_pac()
                logger.info(f"[DetailsPacCreateSerializer] Amendement (vide) - Génération nouveau numéro qui s'incrémente")
                return super().create(validated_data)
        
        # CAS 3: PAC initial ou cas normal - Générer le numéro si non fourni
        if not numero_pac_provided:
            validated_data['numero_pac'] = self.generate_numero_pac()
        elif not is_amendment:
            # Si un numéro est fourni mais ce n'est pas un amendement, vérifier l'unicité
            if DetailsPac.objects.filter(numero_pac=numero_pac_provided).exists():
                # Générer un nouveau numéro si le numéro existe déjà
                validated_data['numero_pac'] = self.generate_numero_pac()
        
        return super().create(validated_data)
    
    def generate_numero_pac(self):
        """Générer un numéro PAC unique en trouvant le maximum existant"""
        import re
        
        # Récupérer tous les numéros de PAC existants
        existing_numbers = DetailsPac.objects.exclude(
            numero_pac__isnull=True
        ).exclude(
            numero_pac__exact=''
        ).values_list('numero_pac', flat=True)
        
        max_num = 0
        for num_str in existing_numbers:
            if num_str:
                # Extraire le numéro (ex: "PAC01" -> 1, "PAC5" -> 5, "PAC02" -> 2)
                match = re.search(r'(\d+)', str(num_str))
                if match:
                    try:
                        num = int(match.group(1))
                        max_num = max(max_num, num)
                    except ValueError:
                        continue
        
        # Générer le prochain numéro (max_num + 1)
        next_num = max_num + 1
        numero = f"PAC{next_num:02d}"
        
        # Vérifier l'unicité (au cas où il y aurait un conflit)
        while DetailsPac.objects.filter(numero_pac=numero).exists():
            next_num += 1
            numero = f"PAC{next_num:02d}"
        
        logger.info(f"[DetailsPacCreateSerializer] Génération nouveau numéro: {numero} (max trouvé: {max_num})")
        return numero


class DetailsPacUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de détails de PAC"""
    
    class Meta:
        model = DetailsPac
        fields = [
            'dysfonctionnement_recommandation', 'libelle',
            'nature', 'categorie', 'source', 'periode_de_realisation'
        ]
        extra_kwargs = {
            'dysfonctionnement_recommandation': {'required': False, 'allow_null': True},
            'libelle': {'required': False, 'allow_null': True, 'allow_blank': True},
            'nature': {'required': False, 'allow_null': True},
            'categorie': {'required': False, 'allow_null': True},
            'source': {'required': False, 'allow_null': True},
            'periode_de_realisation': {'required': False, 'allow_null': True},
        }
    
    def validate_periode_de_realisation(self, value):
        """Valider que la période de réalisation est >= aujourd'hui"""
        if value:
            from django.utils import timezone
            today = timezone.now().date()
            
            if value < today:
                raise serializers.ValidationError(
                    "La période de réalisation doit être égale ou supérieure à la date d'aujourd'hui."
                )
        
        return value
    
    def update(self, instance, validated_data):
        """Mettre à jour un détail PAC"""
        # Protection : empêcher la modification si le PAC est validé
        if instance.pac.is_validated:
            raise serializers.ValidationError(
                "Ce PAC est validé. Les champs de détail ne peuvent plus être modifiés."
            )
        
        return super().update(instance, validated_data)
