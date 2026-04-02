from rest_framework import serializers
from django.utils import timezone
from .models import AnalyseTableau, AnalyseLigne, AnalyseAction
from dashboard.models import TableauBord
from parametre.models import Periodicite


class AnalyseActionSerializer(serializers.ModelSerializer):
    """
    Serializer pour une action d'analyse (niveau le plus fin).
    On expose les UUID des responsables, de l'état, de la preuve et de l'appréciation.
    """

    # Pour la lecture, utiliser PrimaryKeyRelatedField avec many=True
    responsables_directions = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    responsables_sous_directions = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    
    # Exposer les noms pour l'affichage
    etat_nom = serializers.CharField(source='etat_mise_en_oeuvre.nom', read_only=True, allow_null=True)
    evaluation_nom = serializers.CharField(source='evaluation.nom', read_only=True, allow_null=True)
    preuve_description = serializers.CharField(source='preuve.description', read_only=True, allow_null=True)
    preuve_medias = serializers.SerializerMethodField()

    class Meta:
        model = AnalyseAction
        fields = [
            'uuid',
            'ligne',
            'action',
            'responsables_directions',
            'responsables_sous_directions',
            'delai_realisation',
            'etat_mise_en_oeuvre',
            'etat_nom',
            'date_realisation',
            'preuve',
            'preuve_description',
            'preuve_medias',
            'evaluation',
            'evaluation_nom',
            'commentaire',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

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


class AnalyseLigneSerializer(serializers.ModelSerializer):
    """
    Serializer pour une ligne d'analyse (objectif non atteint + causes).
    On inclut les actions en lecture.
    """

    actions = AnalyseActionSerializer(many=True, read_only=True)

    class Meta:
        model = AnalyseLigne
        fields = [
            'uuid',
            'analyse_tableau',
            'periode',
            'objectif_non_atteint',
            'cible',
            'resultat',
            'causes',
            'actions',
            'created_at',
            'updated_at',
        ]
        # Ces champs sont calculés côté backend et ne doivent jamais être modifiés
        # directement par le client (Security by Design).
        read_only_fields = [
            'uuid',
            'analyse_tableau',
            'periode',
            'objectif_non_atteint',
            'cible',
            'resultat',
            'created_at',
            'updated_at',
        ]


class AnalyseLigneUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la mise à jour partielle d'une ligne d'analyse.
    Seuls les champs modifiables sont autorisés (causes, actions via actions séparées).
    Security by Design : les champs calculés (objectif, cible, résultat) restent en lecture seule.
    """
    
    class Meta:
        model = AnalyseLigne
        fields = ['causes']
        # Seul le champ 'causes' peut être modifié par le client


class AnalyseTableauSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour l'analyse liée à un tableau de bord.
    - en lecture : renvoie aussi les lignes (et leurs actions).
    - en écriture : on accepte un uuid de tableau de bord.
    """

    lignes = AnalyseLigneSerializer(many=True, read_only=True)
    tableau_bord_uuid = serializers.UUIDField(write_only=True)

    class Meta:
        model = AnalyseTableau
        fields = [
            'uuid',
            'tableau_bord',
            'tableau_bord_uuid',
            'cree_par',
            'lignes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'tableau_bord', 'cree_par', 'created_at', 'updated_at']

    def create(self, validated_data):
        """
        Crée une AnalyseTableau pour un tableau de bord donné.
        On récupère le user depuis le contexte (request.user).
        """
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        tableau_uuid = validated_data.pop('tableau_bord_uuid')
        try:
            tableau = TableauBord.objects.get(uuid=tableau_uuid)
        except TableauBord.DoesNotExist:
            raise serializers.ValidationError({'tableau_bord_uuid': 'Tableau de bord introuvable'})

        if AnalyseTableau.objects.filter(tableau_bord=tableau).exists():
            raise serializers.ValidationError(
                {'tableau_bord_uuid': 'Une analyse existe déjà pour ce tableau de bord.'}
            )

        return AnalyseTableau.objects.create(
            tableau_bord=tableau,
            cree_par=user,
        )


class AnalyseLigneFromTableauCreateSerializer(serializers.Serializer):
    """
    Serializer d'entrée pour créer une ligne d'analyse pré-remplie
    à partir d'un objectif, d'un indicateur et d'un trimestre.
    """
    tableau_bord_uuid = serializers.UUIDField()
    objective_uuid = serializers.UUIDField()
    indicateur_uuid = serializers.UUIDField()
    periode = serializers.ChoiceField(choices=[c[0] for c in Periodicite.PERIODE_CHOICES])


class AnalyseActionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la création d'une action d'analyse.
    """
    # Définir explicitement ligne comme PrimaryKeyRelatedField pour accepter l'UUID
    ligne = serializers.PrimaryKeyRelatedField(
        queryset=AnalyseLigne.objects.all(),
        required=True
    )
    responsables_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    responsables_sous_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )

    class Meta:
        model = AnalyseAction
        fields = [
            'ligne',
            'action',
            'responsables_directions',
            'responsables_sous_directions',
            'delai_realisation',
            'etat_mise_en_oeuvre',
            'date_realisation',
            'preuve',
            'evaluation',
            'commentaire',
        ]

    def validate_delai_realisation(self, value):
        """
        Empêche de définir un délai dans le passé.
        """
        if value is None:
            return value
        today = timezone.localdate()
        if value < today:
            raise serializers.ValidationError("La date de délai ne peut pas être antérieure à la date du jour.")
        return value

    def validate(self, data):
        """
        Validation croisée : la date de réalisation ne peut pas être antérieure au délai.
        """
        delai = data.get('delai_realisation')
        date_realisation = data.get('date_realisation')
        
        if delai and date_realisation and date_realisation < delai:
            raise serializers.ValidationError({
                'date_realisation': 'La date de réalisation ne peut pas être antérieure au délai de réalisation.'
            })
        
        return data

    def create(self, validated_data):
        responsables_directions = validated_data.pop('responsables_directions', [])
        responsables_sous_directions = validated_data.pop('responsables_sous_directions', [])
        
        action = AnalyseAction.objects.create(**validated_data)
        
        if responsables_directions:
            action.responsables_directions.set(responsables_directions)
        if responsables_sous_directions:
            action.responsables_sous_directions.set(responsables_sous_directions)
        
        return action


class AnalyseActionUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la mise à jour d'une action d'analyse.
    """
    responsables_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    responsables_sous_directions = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )

    class Meta:
        model = AnalyseAction
        fields = [
            'action',
            'responsables_directions',
            'responsables_sous_directions',
            'delai_realisation',
            'etat_mise_en_oeuvre',
            'date_realisation',
            'preuve',
            'evaluation',
            'commentaire',
        ]
        read_only_fields = []

    def validate_delai_realisation(self, value):
        """
        Empêche de mettre à jour le délai avec une date dans le passé.
        """
        if value is None:
            return value
        today = timezone.localdate()
        if value < today:
            raise serializers.ValidationError("La date de délai ne peut pas être antérieure à la date du jour.")
        return value

    def validate(self, data):
        """
        Validation croisée : la date de réalisation ne peut pas être antérieure au délai.
        On doit vérifier avec les valeurs existantes de l'instance si elles ne sont pas dans data.
        """
        delai = data.get('delai_realisation')
        date_realisation = data.get('date_realisation')
        
        # Si le délai n'est pas dans data, utiliser celui de l'instance existante
        if delai is None and hasattr(self, 'instance') and self.instance:
            delai = self.instance.delai_realisation
        
        # Si la date de réalisation n'est pas dans data, utiliser celle de l'instance existante
        if date_realisation is None and hasattr(self, 'instance') and self.instance:
            date_realisation = self.instance.date_realisation
        
        if delai and date_realisation and date_realisation < delai:
            raise serializers.ValidationError({
                'date_realisation': 'La date de réalisation ne peut pas être antérieure au délai de réalisation.'
            })
        
        return data

    def update(self, instance, validated_data):
        responsables_directions = validated_data.pop('responsables_directions', None)
        responsables_sous_directions = validated_data.pop('responsables_sous_directions', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if responsables_directions is not None:
            instance.responsables_directions.set(responsables_directions)
        if responsables_sous_directions is not None:
            instance.responsables_sous_directions.set(responsables_sous_directions)
        
        return instance

