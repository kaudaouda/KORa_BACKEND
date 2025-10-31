"""
Serializers pour l'application PAC
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Pac, Traitement, Suivi
from parametre.models import Processus, Preuve, Media


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
    processus_uuid = serializers.UUIDField(source='processus.uuid', read_only=True)
    nature_nom = serializers.CharField(source='nature.nom', read_only=True, allow_null=True)
    nature_uuid = serializers.UUIDField(source='nature.uuid', read_only=True, allow_null=True)
    categorie_nom = serializers.CharField(source='categorie.nom', read_only=True, allow_null=True)
    categorie_uuid = serializers.UUIDField(source='categorie.uuid', read_only=True, allow_null=True)
    source_nom = serializers.CharField(source='source.nom', read_only=True, allow_null=True)
    source_uuid = serializers.UUIDField(source='source.uuid', read_only=True, allow_null=True)
    dysfonctionnement_recommandation_nom = serializers.CharField(source='dysfonctionnement_recommandation.nom', read_only=True, allow_null=True)
    dysfonctionnement_recommandation_uuid = serializers.UUIDField(source='dysfonctionnement_recommandation.uuid', read_only=True, allow_null=True)
    annee_valeur = serializers.IntegerField(source='annee.annee', read_only=True, allow_null=True)
    annee_libelle = serializers.CharField(source='annee.libelle', read_only=True, allow_null=True)
    annee_uuid = serializers.UUIDField(source='annee.uuid', read_only=True, allow_null=True)
    type_tableau_code = serializers.CharField(source='type_tableau.code', read_only=True, allow_null=True)
    type_tableau_nom = serializers.CharField(source='type_tableau.nom', read_only=True, allow_null=True)
    type_tableau_uuid = serializers.UUIDField(source='type_tableau.uuid', read_only=True, allow_null=True)
    createur_nom = serializers.SerializerMethodField()
    validateur_nom = serializers.SerializerMethodField()
    jours_restants = serializers.SerializerMethodField()
    
    class Meta:
        model = Pac
        fields = [
            'uuid', 'numero_pac', 'processus', 'processus_nom', 'processus_numero', 'processus_uuid',
            'libelle', 'nature', 'nature_nom', 'nature_uuid', 'categorie', 'categorie_nom', 'categorie_uuid',
            'source', 'source_nom', 'source_uuid', 'dysfonctionnement_recommandation', 
            'dysfonctionnement_recommandation_nom', 'dysfonctionnement_recommandation_uuid',
            'annee', 'annee_valeur', 'annee_libelle', 'annee_uuid',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 'type_tableau_uuid',
            'periode_de_realisation', 'jours_restants',
            'is_validated', 'date_validation', 'validated_by', 'validateur_nom',
            'cree_par', 'createur_nom', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'is_validated', 'date_validation', 'validated_by', 'created_at', 'updated_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
    
    def get_validateur_nom(self, obj):
        """Retourner le nom du validateur"""
        if obj.validated_by:
            return f"{obj.validated_by.first_name} {obj.validated_by.last_name}".strip() or obj.validated_by.username
        return None
    
    def get_jours_restants(self, obj):
        """Calculer les jours restants"""
        if not obj.periode_de_realisation:
            return None
        from django.utils import timezone
        delta = obj.periode_de_realisation - timezone.now().date()
        return delta.days if delta.days > 0 else 0


class PacCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de PACs"""
    
    class Meta:
        model = Pac
        fields = [
            'processus', 'libelle', 'nature', 
            'categorie', 'source', 'dysfonctionnement_recommandation', 
            'annee', 'type_tableau', 'periode_de_realisation'
        ]
        extra_kwargs = {
            'libelle': {'required': False, 'allow_null': True, 'allow_blank': True},
            'nature': {'required': False, 'allow_null': True},
            'categorie': {'required': False, 'allow_null': True},
            'source': {'required': False, 'allow_null': True},
            'dysfonctionnement_recommandation': {'required': False, 'allow_null': True},
            'annee': {'required': False, 'allow_null': True},
            'type_tableau': {'required': False, 'allow_null': True},
            'periode_de_realisation': {'required': False, 'allow_null': True},
        }
    
    def validate_periode_de_realisation(self, value):
        """Valider que la période de réalisation est >= aujourd'hui"""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Si la valeur est None, on ne valide pas
        if value is None:
            return value
        
        if value < today:
            raise serializers.ValidationError(
                "La période de réalisation doit être égale ou supérieure à la date d'aujourd'hui."
            )
        
        return value
    
    def create(self, validated_data):
        """Créer un PAC avec l'utilisateur connecté et générer le numéro"""
        validated_data['cree_par'] = self.context['request'].user
        
        # Générer le numéro PAC automatiquement
        validated_data['numero_pac'] = self.generate_numero_pac()
        
        # S'assurer que processus est toujours fourni
        if 'processus' not in validated_data or validated_data['processus'] is None:
            raise serializers.ValidationError("Le champ 'processus' est requis")
        
        return super().create(validated_data)
    
    def generate_numero_pac(self):
        """Générer un numéro PAC unique"""
        from django.db.models import Count
        count = Pac.objects.count()
        numero = f"PAC{count + 1:02d}"
        
        # Vérifier l'unicité
        while Pac.objects.filter(numero_pac=numero).exists():
            count += 1
            numero = f"PAC{count + 1:02d}"
        
        return numero


class PacUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de PACs"""
    
    class Meta:
        model = Pac
        fields = [
            'processus', 'libelle', 'nature', 
            'categorie', 'source', 'dysfonctionnement_recommandation', 
            'annee', 'type_tableau', 'periode_de_realisation'
        ]
        extra_kwargs = {
            'libelle': {'required': False, 'allow_null': True, 'allow_blank': True},
            'nature': {'required': False, 'allow_null': True},
            'categorie': {'required': False, 'allow_null': True},
            'source': {'required': False, 'allow_null': True},
            'dysfonctionnement_recommandation': {'required': False, 'allow_null': True},
            'annee': {'required': False, 'allow_null': True},
            'type_tableau': {'required': False, 'allow_null': True},
            'periode_de_realisation': {'required': False, 'allow_null': True},
        }
    
    def validate_periode_de_realisation(self, value):
        """Valider que la période de réalisation est >= aujourd'hui"""
        if value is None:
            return value
        
        from django.utils import timezone
        today = timezone.now().date()
        
        if value < today:
            raise serializers.ValidationError(
                "La période de réalisation doit être égale ou supérieure à la date d'aujourd'hui."
            )
        
        return value
    
    def update(self, instance, validated_data):
        """Mettre à jour un PAC"""
        # Le numéro PAC et le créateur ne peuvent pas être modifiés
        return super().update(instance, validated_data)


class TraitementSerializer(serializers.ModelSerializer):
    """Serializer pour les traitements"""
    type_action_nom = serializers.CharField(source='type_action.nom', read_only=True, allow_null=True)
    preuve_description = serializers.CharField(source='preuve.description', read_only=True, allow_null=True)
    preuve_media_url = serializers.SerializerMethodField()
    pac_numero = serializers.CharField(source='pac.numero_pac', read_only=True)
    pac_uuid = serializers.UUIDField(source='pac.uuid', read_only=True)
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
        model = Traitement
        fields = [
            'uuid', 'pac', 'pac_uuid', 'pac_numero', 'action', 'type_action', 
            'type_action_nom', 'responsable_direction', 'responsable_direction_nom',
            'responsable_sous_direction', 'responsable_sous_direction_nom',
            'responsables_directions', 'responsables_sous_directions',
            'preuve', 'preuve_description', 'preuve_media_url', 'delai_realisation'
        ]
        read_only_fields = ['uuid']

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


class TraitementCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de traitements"""
    # Nouveau: accepter des listes d'UUID en entrée pour M2M
    responsables_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    responsables_sous_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    
    class Meta:
        model = Traitement
        fields = [
            'pac', 'action', 'type_action', 'responsable_direction', 
            'responsable_sous_direction', 'responsables_directions', 'responsables_sous_directions',
            'preuve', 'delai_realisation'
        ]
        extra_kwargs = {
            'type_action': {'required': False, 'allow_null': True},
            'delai_realisation': {'required': False, 'allow_null': True}
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
        
        # Vérifier si on a accès au PAC pour comparer avec sa période de réalisation
        pac = self.initial_data.get('pac') if hasattr(self, 'initial_data') else None
        if pac:
            try:
                pac_obj = Pac.objects.get(uuid=pac)
                if pac_obj.periode_de_realisation and value < pac_obj.periode_de_realisation:
                    raise serializers.ValidationError(
                        f"Le délai de réalisation doit être égal ou supérieur à la période de réalisation du PAC ({pac_obj.periode_de_realisation.strftime('%d/%m/%Y')})."
                    )
            except Pac.DoesNotExist:
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


class TraitementUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de traitements"""
    responsables_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    responsables_sous_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    
    class Meta:
        model = Traitement
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
        
        # Pour la mise à jour, on peut accéder au PAC via l'instance
        if hasattr(self, 'instance') and self.instance and self.instance.pac:
            pac_obj = self.instance.pac
            if pac_obj.periode_de_realisation and value < pac_obj.periode_de_realisation:
                raise serializers.ValidationError(
                    f"Le délai de réalisation doit être égal ou supérieur à la période de réalisation du PAC ({pac_obj.periode_de_realisation.strftime('%d/%m/%Y')})."
                )
        
        return value

    def update(self, instance, validated_data):
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


class SuiviSerializer(serializers.ModelSerializer):
    """Serializer pour les suivis"""
    etat_nom = serializers.CharField(source='etat_mise_en_oeuvre.nom', read_only=True)
    appreciation_nom = serializers.CharField(source='appreciation.nom', read_only=True)
    traitement_action = serializers.CharField(source='traitement.action', read_only=True)
    statut_nom = serializers.CharField(source='statut.nom', read_only=True)
    preuve_description = serializers.CharField(source='preuve.description', read_only=True)
    preuve_media_url = serializers.SerializerMethodField()
    preuve_media_urls = serializers.SerializerMethodField()
    createur_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = Suivi
        fields = [
            'uuid', 'traitement', 'traitement_action', 'etat_mise_en_oeuvre',
            'etat_nom', 'resultat', 'appreciation', 'appreciation_nom',
            'preuve', 'preuve_description', 'preuve_media_url', 'preuve_media_urls',
            'statut', 'statut_nom', 'date_mise_en_oeuvre_effective',
            'date_cloture', 'cree_par', 'createur_nom', 'created_at'
        ]
        read_only_fields = ['uuid', 'created_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username

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


class SuiviCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de suivis"""
    
    class Meta:
        model = Suivi
        fields = [
            'traitement', 'etat_mise_en_oeuvre', 'resultat', 'appreciation',
            'preuve', 'statut', 'date_mise_en_oeuvre_effective', 'date_cloture'
        ]
    
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
    
    def create(self, validated_data):
        """Créer un suivi avec l'utilisateur connecté"""
        validated_data['cree_par'] = self.context['request'].user
        return super().create(validated_data)


class PacCompletSerializer(serializers.ModelSerializer):
    """Serializer complet pour un PAC avec tous ses traitements et suivis"""
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    processus_numero = serializers.CharField(source='processus.numero_processus', read_only=True)
    processus_uuid = serializers.UUIDField(source='processus.uuid', read_only=True)
    nature_nom = serializers.CharField(source='nature.nom', read_only=True, allow_null=True)
    nature_uuid = serializers.UUIDField(source='nature.uuid', read_only=True, allow_null=True)
    categorie_nom = serializers.CharField(source='categorie.nom', read_only=True, allow_null=True)
    categorie_uuid = serializers.UUIDField(source='categorie.uuid', read_only=True, allow_null=True)
    source_nom = serializers.CharField(source='source.nom', read_only=True, allow_null=True)
    source_uuid = serializers.UUIDField(source='source.uuid', read_only=True, allow_null=True)
    dysfonctionnement_recommandation_nom = serializers.CharField(source='dysfonctionnement_recommandation.nom', read_only=True, allow_null=True)
    dysfonctionnement_recommandation_uuid = serializers.UUIDField(source='dysfonctionnement_recommandation.uuid', read_only=True, allow_null=True)
    annee_valeur = serializers.IntegerField(source='annee.annee', read_only=True, allow_null=True)
    annee_libelle = serializers.CharField(source='annee.libelle', read_only=True, allow_null=True)
    annee_uuid = serializers.UUIDField(source='annee.uuid', read_only=True, allow_null=True)
    type_tableau_code = serializers.CharField(source='type_tableau.code', read_only=True, allow_null=True)
    type_tableau_nom = serializers.CharField(source='type_tableau.nom', read_only=True, allow_null=True)
    type_tableau_uuid = serializers.UUIDField(source='type_tableau.uuid', read_only=True, allow_null=True)
    createur_nom = serializers.SerializerMethodField()
    jours_restants = serializers.SerializerMethodField()
    
    # Inclure tous les traitements avec leurs suivis
    traitements = serializers.SerializerMethodField()
    
    class Meta:
        model = Pac
        fields = [
            'uuid', 'numero_pac', 'processus', 'processus_nom', 'processus_numero', 'processus_uuid',
            'libelle', 'nature', 'nature_nom', 'nature_uuid', 'categorie', 'categorie_nom', 'categorie_uuid',
            'source', 'source_nom', 'source_uuid', 'dysfonctionnement_recommandation',
            'dysfonctionnement_recommandation_nom', 'dysfonctionnement_recommandation_uuid',
            'annee', 'annee_valeur', 'annee_libelle', 'annee_uuid',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 'type_tableau_uuid',
            'periode_de_realisation', 'jours_restants',
            'cree_par', 'createur_nom', 'created_at', 'updated_at', 'traitements'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
    
    def get_jours_restants(self, obj):
        """Calculer les jours restants"""
        if not obj.periode_de_realisation:
            return None
        from django.utils import timezone
        delta = obj.periode_de_realisation - timezone.now().date()
        return delta.days if delta.days > 0 else 0
    
    def get_traitements(self, obj):
        """Récupérer tous les traitements avec leurs suivis"""
        traitements = obj.traitements.all().order_by('delai_realisation')
        traitements_data = []
        
        for traitement in traitements:
            traitement_data = {
                'uuid': str(traitement.uuid),
                'action': traitement.action,
                'type_action': traitement.type_action.uuid if traitement.type_action else None,
                'type_action_nom': traitement.type_action.nom if traitement.type_action else None,
                'responsable_direction': traitement.responsable_direction.uuid if traitement.responsable_direction else None,
                'responsable_direction_nom': traitement.responsable_direction.nom if traitement.responsable_direction else None,
                'responsable_sous_direction': traitement.responsable_sous_direction.uuid if traitement.responsable_sous_direction else None,
                'responsable_sous_direction_nom': traitement.responsable_sous_direction.nom if traitement.responsable_sous_direction else None,
                'delai_realisation': traitement.delai_realisation,
                'preuve': traitement.preuve.uuid if traitement.preuve else None,
                'preuve_description': traitement.preuve.description if traitement.preuve else None,
                'preuve_media_url': self.get_preuve_media_url(traitement),
                'suivis': []
            }
            
            # Récupérer tous les suivis pour ce traitement
            suivis = traitement.suivis.all().order_by('created_at')
            for suivi in suivis:
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
                    'preuve_description': suivi.preuve.description if suivi.preuve else None,
                    'preuve_media_url': self.get_preuve_media_url_suivi(suivi),
                    'preuve_media_urls': self.get_preuve_media_urls_suivi(suivi)
                }
                traitement_data['suivis'].append(suivi_data)
            
            traitements_data.append(traitement_data)
        
        return traitements_data
    
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


class SuiviUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour des suivis"""

    class Meta:
        model = Suivi
        fields = [
            'etat_mise_en_oeuvre', 'resultat', 'appreciation',
            'preuve', 'statut', 'date_mise_en_oeuvre_effective', 'date_cloture'
        ]
    
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
