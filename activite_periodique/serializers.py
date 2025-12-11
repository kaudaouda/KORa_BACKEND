"""
Serializers pour l'application Activité Périodique
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import ActivitePeriodique, DetailsAP, SuivisAP
from parametre.models import Processus, Direction, SousDirection, Service, EtatMiseEnOeuvre, Frequence
import logging

logger = logging.getLogger(__name__)


class ActivitePeriodiqueSerializer(serializers.ModelSerializer):
    """Serializer pour les Activités Périodiques"""
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
    numero_ap = serializers.SerializerMethodField()
    has_amendements = serializers.SerializerMethodField()

    class Meta:
        model = ActivitePeriodique
        fields = [
            'uuid', 'numero_ap', 'processus', 'processus_nom', 'processus_numero', 'processus_uuid',
            'annee', 'annee_valeur', 'annee_libelle', 'annee_uuid',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 'type_tableau_uuid',
            'initial_ref', 'initial_ref_uuid',
            'is_validated', 'validated_at', 'validated_by', 'validateur_nom',
            'cree_par', 'createur_nom', 'has_amendements', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'numero_ap', 'is_validated', 'validated_at', 'validated_by', 'cree_par', 'createur_nom', 'created_at', 'updated_at']

    def get_numero_ap(self, obj):
        """Retourner le numéro du premier détail AP associé, ou None"""
        premier_detail = obj.details.first()
        if premier_detail and premier_detail.numero_ap:
            return premier_detail.numero_ap
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

    def get_has_amendements(self, obj):
        """Vérifier si cet AP a des amendements suivants (doit être verrouillé)"""
        try:
            type_code = obj.type_tableau.code if obj.type_tableau else None
            
            if type_code == 'INITIAL':
                # Pour INITIAL : vérifier s'il y a AMENDEMENT_1 ou AMENDEMENT_2 pour le même processus/année
                return ActivitePeriodique.objects.filter(
                    processus=obj.processus,
                    annee=obj.annee,
                    type_tableau__code__in=['AMENDEMENT_1', 'AMENDEMENT_2'],
                    cree_par=obj.cree_par
                ).exists()
            elif type_code == 'AMENDEMENT_1':
                # Pour AMENDEMENT_1 : vérifier s'il y a AMENDEMENT_2 créé après lui pour le même processus/année
                # On vérifie s'il y a un AMENDEMENT_2 créé pour le même contexte
                return ActivitePeriodique.objects.filter(
                    processus=obj.processus,
                    annee=obj.annee,
                    type_tableau__code='AMENDEMENT_2',
                    cree_par=obj.cree_par,
                    created_at__gt=obj.created_at  # Créé après cet AMENDEMENT_1
                ).exists()
            elif type_code == 'AMENDEMENT_2':
                # AMENDEMENT_2 ne peut pas avoir d'amendements suivants
                return False
            else:
                # Par défaut, vérifier les amendements directs
                return obj.amendements.exists()
        except Exception:
            # En cas d'erreur, retourner False par défaut
            return False

    def create(self, validated_data):
        """Créer une nouvelle Activité Périodique"""
        # Récupérer l'utilisateur depuis le contexte
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['cree_par'] = request.user
        return super().create(validated_data)


class DetailsAPSerializer(serializers.ModelSerializer):
    """Serializer pour les Détails d'Activité Périodique"""
    activite_periodique_uuid = serializers.UUIDField(source='activite_periodique.uuid', read_only=True)
    responsabilite_direction_nom = serializers.CharField(source='responsabilite_direction.nom', read_only=True, allow_null=True)
    responsabilite_sous_direction_nom = serializers.CharField(source='responsabilite_sous_direction.nom', read_only=True, allow_null=True)
    responsabilite_service_nom = serializers.CharField(source='responsabilite_service.nom', read_only=True, allow_null=True)
    frequence_uuid = serializers.UUIDField(source='frequence.uuid', read_only=True, allow_null=True)
    frequence_nom = serializers.CharField(source='frequence.nom', read_only=True, allow_null=True)
    responsables_directions = serializers.PrimaryKeyRelatedField(many=True, queryset=Direction.objects.all(), required=False)
    responsables_sous_directions = serializers.PrimaryKeyRelatedField(many=True, queryset=SousDirection.objects.all(), required=False)
    responsables_services = serializers.PrimaryKeyRelatedField(many=True, queryset=Service.objects.all(), required=False)
    
    # Champs pour renvoyer les responsables avec leurs noms
    responsables_directions_data = serializers.SerializerMethodField()
    responsables_sous_directions_data = serializers.SerializerMethodField()
    responsables_services_data = serializers.SerializerMethodField()

    class Meta:
        model = DetailsAP
        fields = [
            'uuid', 'numero_ap', 'activite_periodique', 'activite_periodique_uuid',
            'activites_periodiques', 'frequence', 'frequence_uuid', 'frequence_nom',
            'responsabilite_direction', 'responsabilite_direction_nom',
            'responsabilite_sous_direction', 'responsabilite_sous_direction_nom',
            'responsabilite_service', 'responsabilite_service_nom',
            'responsables_directions', 'responsables_sous_directions', 'responsables_services',
            'responsables_directions_data', 'responsables_sous_directions_data', 'responsables_services_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at', 'responsables_directions_data', 'responsables_sous_directions_data', 'responsables_services_data']

    def get_responsables_directions_data(self, obj):
        """Retourner les directions responsables avec leurs noms et type"""
        if hasattr(obj, 'responsables_directions'):
            return [
                {
                    'uuid': str(dir.uuid),
                    'nom': dir.nom,
                    'type': 'direction',
                    'nom_complet': dir.nom
                }
                for dir in obj.responsables_directions.all()
            ]
        return []

    def get_responsables_sous_directions_data(self, obj):
        """Retourner les sous-directions responsables avec leurs noms et type"""
        if hasattr(obj, 'responsables_sous_directions'):
            return [
                {
                    'uuid': str(sous_dir.uuid),
                    'nom': sous_dir.nom,
                    'type': 'sousdirection',
                    'nom_complet': f"{sous_dir.direction.nom}/{sous_dir.nom}" if sous_dir.direction else sous_dir.nom
                }
                for sous_dir in obj.responsables_sous_directions.all()
            ]
        return []

    def get_responsables_services_data(self, obj):
        """Retourner les services responsables avec leurs noms et type"""
        if hasattr(obj, 'responsables_services'):
            return [
                {
                    'uuid': str(service.uuid),
                    'nom': service.nom,
                    'type': 'service',
                    'nom_complet': f"{service.sous_direction.direction.nom}/{service.sous_direction.nom}/{service.nom}" if service.sous_direction and service.sous_direction.direction else service.nom
                }
                for service in obj.responsables_services.all()
            ]
        return []


class DetailsAPCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de détails AP avec génération automatique du numéro"""
    numero_ap = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    activite_periodique_uuid = serializers.UUIDField(source='activite_periodique.uuid', read_only=True)
    responsabilite_direction_nom = serializers.CharField(source='responsabilite_direction.nom', read_only=True, allow_null=True)
    responsabilite_sous_direction_nom = serializers.CharField(source='responsabilite_sous_direction.nom', read_only=True, allow_null=True)
    responsabilite_service_nom = serializers.CharField(source='responsabilite_service.nom', read_only=True, allow_null=True)
    frequence_uuid = serializers.UUIDField(source='frequence.uuid', read_only=True, allow_null=True)
    frequence_nom = serializers.CharField(source='frequence.nom', read_only=True, allow_null=True)
    responsables_directions = serializers.PrimaryKeyRelatedField(many=True, queryset=Direction.objects.all(), required=False)
    responsables_sous_directions = serializers.PrimaryKeyRelatedField(many=True, queryset=SousDirection.objects.all(), required=False)
    responsables_services = serializers.PrimaryKeyRelatedField(many=True, queryset=Service.objects.all(), required=False)

    class Meta:
        model = DetailsAP
        fields = [
            'uuid', 'numero_ap', 'activite_periodique', 'activite_periodique_uuid',
            'activites_periodiques', 'frequence', 'frequence_uuid', 'frequence_nom',
            'responsabilite_direction', 'responsabilite_direction_nom',
            'responsabilite_sous_direction', 'responsabilite_sous_direction_nom',
            'responsabilite_service', 'responsabilite_service_nom',
            'responsables_directions', 'responsables_sous_directions', 'responsables_services',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'activites_periodiques': {'required': False, 'allow_null': True, 'allow_blank': True},
            'frequence': {'required': False, 'allow_null': True},
            'responsabilite_direction': {'required': False, 'allow_null': True},
            'responsabilite_sous_direction': {'required': False, 'allow_null': True},
            'responsabilite_service': {'required': False, 'allow_null': True},
        }

    def validate_activite_periodique(self, value):
        """Vérifier que l'AP appartient à l'utilisateur connecté et n'est pas validée"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.cree_par != request.user:
                raise serializers.ValidationError(
                    "Vous n'avez pas les permissions pour ajouter un détail à cette Activité Périodique."
                )

        # Protection : empêcher la création de détail si l'AP est validée
        if value.is_validated:
            raise serializers.ValidationError(
                "Cette Activité Périodique est validée. Impossible de créer un nouveau détail."
            )

        return value

    def create(self, validated_data):
        """Créer un détail AP avec génération automatique du numéro si nécessaire"""
        numero_ap_provided = validated_data.get('numero_ap')
        activite_periodique = validated_data.get('activite_periodique')

        # Génération automatique du numéro si aucun n'est fourni ou si c'est une chaîne vide
        if not numero_ap_provided or (isinstance(numero_ap_provided, str) and numero_ap_provided.strip() == ''):
            # Compter les détails existants pour cette AP
            existing_count = DetailsAP.objects.filter(activite_periodique=activite_periodique).count()
            numero_ap = f"AP-{existing_count + 1}"
            validated_data['numero_ap'] = numero_ap
            logger.info(f"[DetailsAPCreateSerializer] Numéro AP généré automatiquement: {numero_ap}")

        # Extraire les relations many-to-many avant la création
        responsables_directions = validated_data.pop('responsables_directions', [])
        responsables_sous_directions = validated_data.pop('responsables_sous_directions', [])
        responsables_services = validated_data.pop('responsables_services', [])

        # Créer l'instance
        detail = super().create(validated_data)

        # Assigner les relations many-to-many après la création
        if responsables_directions:
            detail.responsables_directions.set(responsables_directions)
            logger.info(f"[DetailsAPCreateSerializer] {len(responsables_directions)} direction(s) assignée(s)")
        
        if responsables_sous_directions:
            detail.responsables_sous_directions.set(responsables_sous_directions)
            logger.info(f"[DetailsAPCreateSerializer] {len(responsables_sous_directions)} sous-direction(s) assignée(s)")
        
        if responsables_services:
            detail.responsables_services.set(responsables_services)
            logger.info(f"[DetailsAPCreateSerializer] {len(responsables_services)} service(s) assigné(s)")

        return detail


class SuivisAPSerializer(serializers.ModelSerializer):
    """Serializer pour les Suivis d'Activité Périodique"""
    details_ap_uuid = serializers.UUIDField(source='details_ap.uuid', read_only=True)
    details_ap_numero = serializers.CharField(source='details_ap.numero_ap', read_only=True, allow_null=True)
    mois_uuid = serializers.UUIDField(source='mois.uuid', read_only=True)
    mois_numero = serializers.IntegerField(source='mois.numero', read_only=True)
    mois_nom = serializers.CharField(source='mois.nom', read_only=True)
    mois_abreviation = serializers.CharField(source='mois.abreviation', read_only=True)
    etat_mise_en_oeuvre_nom = serializers.CharField(source='etat_mise_en_oeuvre.nom', read_only=True, allow_null=True)
    etat_mise_en_oeuvre_uuid = serializers.UUIDField(source='etat_mise_en_oeuvre.uuid', read_only=True, allow_null=True)

    class Meta:
        model = SuivisAP
        fields = [
            'uuid', 'details_ap', 'details_ap_uuid', 'details_ap_numero',
            'mois', 'mois_uuid', 'mois_numero', 'mois_nom', 'mois_abreviation',
            'etat_mise_en_oeuvre', 'etat_mise_en_oeuvre_nom', 'etat_mise_en_oeuvre_uuid',
            'livrable', 'date_realisation',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def validate_mois(self, value):
        """Valider que le mois est autorisé selon la fréquence et les mois déjà renseignés"""
        # Récupérer l'instance depuis l'objet si c'est une mise à jour
        if self.instance:
            detail_ap = self.instance.details_ap
        else:
            # Pour la création, récupérer depuis initial_data
            details_ap_uuid = self.initial_data.get('details_ap')
            if not details_ap_uuid:
                return value
            try:
                detail_ap = DetailsAP.objects.select_related('frequence').get(uuid=details_ap_uuid)
            except DetailsAP.DoesNotExist:
                return value

        # Si pas de fréquence définie, autoriser tous les mois
        if not detail_ap.frequence:
            return value

        frequence_nom = detail_ap.frequence.nom.lower()
        mois_numero = value.numero

        # Récupérer les suivis existants pour ce détail AP (excluant l'instance actuelle si mise à jour)
        suivis_existants = detail_ap.suivis.all()
        if self.instance:
            suivis_existants = suivis_existants.exclude(uuid=self.instance.uuid)

        # Extraire les numéros de mois déjà renseignés
        mois_renseignes = list(suivis_existants.values_list('mois__numero', flat=True))

        # Définir les mois autorisés selon la fréquence et les mois déjà renseignés
        mois_autorises = []
        if frequence_nom == 'trimestrielle':
            # Trimestrielle : déterminer le trimestre en fonction du premier mois renseigné
            # T1: 1,2,3 / T2: 4,5,6 / T3: 7,8,9 / T4: 10,11,12
            if mois_renseignes:
                # Déterminer le trimestre déjà commencé
                premier_mois = min(mois_renseignes)
                if premier_mois in [1, 2, 3]:
                    mois_autorises = [1, 2, 3]
                elif premier_mois in [4, 5, 6]:
                    mois_autorises = [4, 5, 6]
                elif premier_mois in [7, 8, 9]:
                    mois_autorises = [7, 8, 9]
                elif premier_mois in [10, 11, 12]:
                    mois_autorises = [10, 11, 12]
            else:
                # Aucun mois renseigné, tous les trimestres sont possibles
                mois_autorises = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

        elif frequence_nom == 'semestrielle':
            # Semestrielle : déterminer le semestre en fonction du premier mois renseigné
            # S1: 1,2,3,4,5,6 / S2: 7,8,9,10,11,12
            if mois_renseignes:
                # Déterminer le semestre déjà commencé
                premier_mois = min(mois_renseignes)
                if premier_mois in [1, 2, 3, 4, 5, 6]:
                    mois_autorises = [1, 2, 3, 4, 5, 6]
                elif premier_mois in [7, 8, 9, 10, 11, 12]:
                    mois_autorises = [7, 8, 9, 10, 11, 12]
            else:
                # Aucun mois renseigné, tous les semestres sont possibles
                mois_autorises = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

        elif frequence_nom == 'annuelle':
            # Annuelle : tous les mois de l'année sont toujours autorisés
            mois_autorises = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        else:
            # Pour les autres fréquences (mensuelle, etc.), autoriser tous les mois
            return value

        if mois_numero not in mois_autorises:
            mois_nom = value.nom
            if frequence_nom == 'trimestrielle' and mois_renseignes:
                trimestre_actuel = (min(mois_renseignes) - 1) // 3 + 1
                raise serializers.ValidationError(
                    f"Pour la fréquence trimestrielle, vous avez déjà commencé à renseigner le trimestre {trimestre_actuel}. "
                    f"Vous ne pouvez renseigner que les mois de ce trimestre."
                )
            elif frequence_nom == 'semestrielle' and mois_renseignes:
                semestre_actuel = (min(mois_renseignes) - 1) // 6 + 1
                raise serializers.ValidationError(
                    f"Pour la fréquence semestrielle, vous avez déjà commencé à renseigner le semestre {semestre_actuel}. "
                    f"Vous ne pouvez renseigner que les mois de ce semestre."
                )
            else:
                raise serializers.ValidationError(
                    f"Le mois '{mois_nom}' n'est pas autorisé pour la fréquence '{detail_ap.frequence.nom}'."
                )

        return value


class SuivisAPCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de Suivis AP"""
    details_ap_uuid = serializers.UUIDField(source='details_ap.uuid', read_only=True)
    details_ap_numero = serializers.CharField(source='details_ap.numero_ap', read_only=True, allow_null=True)
    mois_uuid = serializers.UUIDField(source='mois.uuid', read_only=True)
    mois_numero = serializers.IntegerField(source='mois.numero', read_only=True)
    mois_nom = serializers.CharField(source='mois.nom', read_only=True)
    mois_abreviation = serializers.CharField(source='mois.abreviation', read_only=True)
    etat_mise_en_oeuvre_nom = serializers.CharField(source='etat_mise_en_oeuvre.nom', read_only=True, allow_null=True)
    etat_mise_en_oeuvre_uuid = serializers.UUIDField(source='etat_mise_en_oeuvre.uuid', read_only=True, allow_null=True)

    class Meta:
        model = SuivisAP
        fields = [
            'uuid', 'details_ap', 'details_ap_uuid', 'details_ap_numero',
            'mois', 'mois_uuid', 'mois_numero', 'mois_nom', 'mois_abreviation',
            'etat_mise_en_oeuvre', 'etat_mise_en_oeuvre_nom', 'etat_mise_en_oeuvre_uuid',
            'livrable', 'date_realisation',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'etat_mise_en_oeuvre': {'required': False, 'allow_null': True},
            'livrable': {'required': False, 'allow_null': True, 'allow_blank': True},
            'date_realisation': {'required': False, 'allow_null': True},
        }

    def validate_details_ap(self, value):
        """Vérifier que le détail AP appartient à l'utilisateur connecté et que l'AP est validée"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.activite_periodique.cree_par != request.user:
                raise serializers.ValidationError(
                    "Vous n'avez pas les permissions pour ajouter un suivi à ce détail AP."
                )

        # Protection : empêcher la création de suivi si l'AP n'est pas validée
        # Exception : permettre la création lors de la copie d'amendement
        from_amendment_copy = self.initial_data.get('from_amendment_copy', False)
        if not value.activite_periodique.is_validated and not from_amendment_copy:
            raise serializers.ValidationError(
                "Cette Activité Périodique n'est pas validée. Veuillez remplir tous les champs requis des détails et valider le tableau avant de pouvoir renseigner les suivis."
            )

        return value

    def validate_mois(self, value):
        """Valider que le mois est autorisé selon la fréquence et les mois déjà renseignés"""
        details_ap = self.initial_data.get('details_ap')
        if not details_ap:
            return value

        try:
            detail_ap = DetailsAP.objects.select_related('activite_periodique', 'frequence').get(uuid=details_ap)
        except DetailsAP.DoesNotExist:
            return value

        # Vérifier que l'AP est validée (les suivis ne peuvent être créés que si l'AP est validée)
        # Exception : permettre la création lors de la copie d'amendement
        from_amendment_copy = self.initial_data.get('from_amendment_copy', False)
        if not detail_ap.activite_periodique.is_validated and not from_amendment_copy:
            raise serializers.ValidationError(
                "L'Activité Périodique doit être validée avant de pouvoir renseigner les suivis. Veuillez remplir tous les champs requis des détails et valider le tableau."
            )

        # Si pas de fréquence définie, autoriser tous les mois
        if not detail_ap.frequence:
            return value

        frequence_nom = detail_ap.frequence.nom.lower()
        mois_numero = value.numero

        # Récupérer les suivis existants pour ce détail AP
        suivis_existants = detail_ap.suivis.all()

        # Extraire les numéros de mois déjà renseignés
        mois_renseignes = list(suivis_existants.values_list('mois__numero', flat=True))

        # Définir les mois autorisés selon la fréquence et les mois déjà renseignés
        mois_autorises = []
        if frequence_nom == 'trimestrielle':
            # Trimestrielle : déterminer le trimestre en fonction du premier mois renseigné
            # T1: 1,2,3 / T2: 4,5,6 / T3: 7,8,9 / T4: 10,11,12
            if mois_renseignes:
                # Déterminer le trimestre déjà commencé
                premier_mois = min(mois_renseignes)
                if premier_mois in [1, 2, 3]:
                    mois_autorises = [1, 2, 3]
                elif premier_mois in [4, 5, 6]:
                    mois_autorises = [4, 5, 6]
                elif premier_mois in [7, 8, 9]:
                    mois_autorises = [7, 8, 9]
                elif premier_mois in [10, 11, 12]:
                    mois_autorises = [10, 11, 12]
            else:
                # Aucun mois renseigné, tous les trimestres sont possibles
                mois_autorises = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

        elif frequence_nom == 'semestrielle':
            # Semestrielle : déterminer le semestre en fonction du premier mois renseigné
            # S1: 1,2,3,4,5,6 / S2: 7,8,9,10,11,12
            if mois_renseignes:
                # Déterminer le semestre déjà commencé
                premier_mois = min(mois_renseignes)
                if premier_mois in [1, 2, 3, 4, 5, 6]:
                    mois_autorises = [1, 2, 3, 4, 5, 6]
                elif premier_mois in [7, 8, 9, 10, 11, 12]:
                    mois_autorises = [7, 8, 9, 10, 11, 12]
            else:
                # Aucun mois renseigné, tous les semestres sont possibles
                mois_autorises = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

        elif frequence_nom == 'annuelle':
            # Annuelle : tous les mois de l'année sont toujours autorisés
            mois_autorises = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        else:
            # Pour les autres fréquences (mensuelle, etc.), autoriser tous les mois
            return value

        if mois_numero not in mois_autorises:
            mois_nom = value.nom
            if frequence_nom == 'trimestrielle' and mois_renseignes:
                trimestre_actuel = (min(mois_renseignes) - 1) // 3 + 1
                raise serializers.ValidationError(
                    f"Pour la fréquence trimestrielle, vous avez déjà commencé à renseigner le trimestre {trimestre_actuel}. "
                    f"Vous ne pouvez renseigner que les mois de ce trimestre."
                )
            elif frequence_nom == 'semestrielle' and mois_renseignes:
                semestre_actuel = (min(mois_renseignes) - 1) // 6 + 1
                raise serializers.ValidationError(
                    f"Pour la fréquence semestrielle, vous avez déjà commencé à renseigner le semestre {semestre_actuel}. "
                    f"Vous ne pouvez renseigner que les mois de ce semestre."
                )
            else:
                raise serializers.ValidationError(
                    f"Le mois '{mois_nom}' n'est pas autorisé pour la fréquence '{detail_ap.frequence.nom}'."
                )

        return value


class ActivitePeriodiqueCompletSerializer(serializers.ModelSerializer):
    """Serializer complet pour une Activité Périodique avec tous ses détails et périodicités"""
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
    numero_ap = serializers.SerializerMethodField()
    has_amendements = serializers.SerializerMethodField()
    
    # Inclure tous les détails avec leurs périodicités et mois
    details = serializers.SerializerMethodField()

    class Meta:
        model = ActivitePeriodique
        fields = [
            'uuid', 'numero_ap', 'processus', 'processus_nom', 'processus_numero', 'processus_uuid',
            'annee', 'annee_valeur', 'annee_libelle', 'annee_uuid',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 'type_tableau_uuid',
            'initial_ref', 'initial_ref_uuid',
            'cree_par', 'createur_nom', 'is_validated', 'validated_at', 'validated_by', 'has_amendements', 'details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'numero_ap', 'is_validated', 'validated_at', 'validated_by', 'cree_par', 'createur_nom', 'details', 'created_at', 'updated_at']

    def get_numero_ap(self, obj):
        """Retourner le numéro du premier détail AP associé, ou None"""
        premier_detail = obj.details.first()
        if premier_detail and premier_detail.numero_ap:
            return premier_detail.numero_ap
        return None

    def get_createur_nom(self, obj):
        """Retourner le nom du créateur"""
        if obj.cree_par:
            return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
        return "Utilisateur inconnu"

    def get_has_amendements(self, obj):
        """Vérifier si cet AP a des amendements suivants (doit être verrouillé)"""
        try:
            type_code = obj.type_tableau.code if obj.type_tableau else None
            
            if type_code == 'INITIAL':
                # Pour INITIAL : vérifier s'il y a AMENDEMENT_1 ou AMENDEMENT_2 pour le même processus/année
                return ActivitePeriodique.objects.filter(
                    processus=obj.processus,
                    annee=obj.annee,
                    type_tableau__code__in=['AMENDEMENT_1', 'AMENDEMENT_2'],
                    cree_par=obj.cree_par
                ).exists()
            elif type_code == 'AMENDEMENT_1':
                # Pour AMENDEMENT_1 : vérifier s'il y a AMENDEMENT_2 créé après lui pour le même processus/année
                # On vérifie s'il y a un AMENDEMENT_2 créé pour le même contexte
                return ActivitePeriodique.objects.filter(
                    processus=obj.processus,
                    annee=obj.annee,
                    type_tableau__code='AMENDEMENT_2',
                    cree_par=obj.cree_par,
                    created_at__gt=obj.created_at  # Créé après cet AMENDEMENT_1
                ).exists()
            elif type_code == 'AMENDEMENT_2':
                # AMENDEMENT_2 ne peut pas avoir d'amendements suivants
                return False
            else:
                # Par défaut, vérifier les amendements directs
                return obj.amendements.exists()
        except Exception:
            # En cas d'erreur, retourner False par défaut
            return False

    def get_details(self, obj):
        """Retourner tous les détails avec leurs suivis"""
        details = obj.details.all()
        result = []
        for detail in details:
            detail_data = DetailsAPSerializer(detail).data
            suivis = detail.suivis.all()
            detail_data['suivis'] = [SuivisAPSerializer(s).data for s in suivis]
            result.append(detail_data)
        return result

