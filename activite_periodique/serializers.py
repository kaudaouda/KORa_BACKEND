"""
Serializers pour l'application Activité Périodique
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import ActivitePeriodique, DetailsAP, SuivisAP
from parametre.models import Processus, Direction, SousDirection, Service, EtatMiseEnOeuvre, Frequence, Media
try:
    from parametre.models import MediaLivrable
except ImportError:
    MediaLivrable = None
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
        """Vérifier que l'utilisateur a la permission de créer un détail et que l'AP n'est pas validée"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            # Super admin : permettre la création même si ce n'est pas le créateur
            from parametre.permissions import can_manage_users, is_super_admin
            is_super = can_manage_users(request.user) or is_super_admin(request.user)
            
            # Si ce n'est pas un super admin, vérifier la permission create_detail_activite_periodique
            if not is_super:
                # Vérifier si l'utilisateur a la permission create_detail_activite_periodique pour ce processus
                from permissions.services.permission_service import PermissionService
                processus_uuid = str(value.processus.uuid) if value.processus else None
                if processus_uuid:
                    has_permission = PermissionService.can_perform_action(
                        user=request.user,
                        app_name='activite_periodique',
                        action='create_detail_activite_periodique',
                        processus_uuid=processus_uuid
                    )
                    if not has_permission:
                        raise serializers.ValidationError(
                            "Vous n'avez pas les permissions pour ajouter un détail à cette Activité Périodique."
                        )
                else:
                    # Si pas de processus UUID, vérifier si c'est le créateur (fallback)
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

    media_livrables = serializers.SerializerMethodField()
    media_livrables_count = serializers.SerializerMethodField()

    class Meta:
        model = SuivisAP
        fields = [
            'uuid', 'details_ap', 'details_ap_uuid', 'details_ap_numero',
            'mois', 'mois_uuid', 'mois_numero', 'mois_nom', 'mois_abreviation',
            'etat_mise_en_oeuvre', 'etat_mise_en_oeuvre_nom', 'etat_mise_en_oeuvre_uuid',
            'livrable', 'date_realisation', 'media_livrables', 'media_livrables_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_media_livrables(self, obj):
        """Retourner les MediaLivrable associés"""
        try:
            # Vérifier si MediaLivrable est disponible et si la relation existe
            if MediaLivrable is None:
                return []
            if not hasattr(obj, 'media_livrables'):
                return []
            # Vérifier si la table existe en essayant d'accéder à la relation
            try:
                media_livrables = obj.media_livrables.all().prefetch_related('medias')
                return MediaLivrableSerializer(media_livrables, many=True).data
            except Exception:
                # La table n'existe probablement pas encore (migration non appliquée)
                return []
        except Exception as e:
            logger.warning(f'Erreur lors de la récupération des MediaLivrable pour suivi {obj.uuid}: {str(e)}')
            return []
    
    def get_media_livrables_count(self, obj):
        """Retourner le nombre de MediaLivrable"""
        try:
            # Vérifier si MediaLivrable est disponible et si la relation existe
            if MediaLivrable is None:
                return 0
            if not hasattr(obj, 'media_livrables'):
                return 0
            return obj.media_livrables.count()
        except Exception as e:
            logger.warning(f'Erreur lors du comptage des MediaLivrable pour suivi {obj.uuid}: {str(e)}')
            return 0

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

        # Définir les mois autorisés selon la fréquence (logique fixe comme dans le tableau de bord)
        # Utilise la même logique que Periodicite.get_periodes_for_frequence
        from parametre.models import Periodicite
        
        # Mapping des trimestres aux mois
        trimestres_mois = {
            'T1': [1, 2, 3],      # 1er Trimestre
            'T2': [4, 5, 6],      # 2ème Trimestre
            'T3': [7, 8, 9],      # 3ème Trimestre
            'T4': [10, 11, 12]    # 4ème Trimestre
        }

        # Récupérer les périodes autorisées pour cette fréquence (même logique que le tableau de bord)
        periodes_autorisees = Periodicite.get_periodes_for_frequence(detail_ap.frequence.nom)
        periodes_codes = [p[0] for p in periodes_autorisees]  # Extraire les codes (T1, T2, etc.)

        # Convertir les périodes en mois autorisés
        mois_autorises = []
        for periode_code in periodes_codes:
            if periode_code in trimestres_mois:
                mois_autorises.extend(trimestres_mois[periode_code])

        if mois_numero not in mois_autorises:
            mois_nom = value.nom
            periode_labels = {
                'T1': '1er Trimestre',
                'T2': '2ème Trimestre',
                'T3': '3ème Trimestre',
                'T4': '4ème Trimestre'
            }
            allowed_periodes_labels = [
                periode_labels.get(p[0], p[1]) for p in periodes_autorisees
            ]
            raise serializers.ValidationError(
                f"Le mois '{mois_nom}' n'est pas autorisé pour la fréquence '{detail_ap.frequence.nom}'. "
                f"Périodes autorisées: {', '.join(allowed_periodes_labels)}"
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
        """Vérifier que l'utilisateur a la permission de créer un suivi et que l'AP est validée"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            # Super admin : permettre la création même si ce n'est pas le créateur
            from parametre.permissions import can_manage_users, is_super_admin
            is_super = can_manage_users(request.user) or is_super_admin(request.user)
            
            # Si ce n'est pas un super admin, vérifier la permission create_suivi_activite_periodique
            # ou update_suivi_activite_periodique comme fallback (logique métier : si on peut modifier, on peut créer)
            if not is_super:
                # Vérifier si l'utilisateur a la permission create_suivi_activite_periodique pour ce processus
                from permissions.services.permission_service import PermissionService
                processus_uuid = str(value.activite_periodique.processus.uuid) if value.activite_periodique.processus else None
                if processus_uuid:
                    # Vérifier d'abord create_suivi_activite_periodique
                    has_create_permission, _ = PermissionService.can_perform_action(
                        user=request.user,
                        app_name='activite_periodique',
                        action='create_suivi_activite_periodique',
                        processus_uuid=processus_uuid
                    )
                    
                    # Si create n'est pas accordée, vérifier update comme fallback
                    if not has_create_permission:
                        has_update_permission, _ = PermissionService.can_perform_action(
                            user=request.user,
                            app_name='activite_periodique',
                            action='update_suivi_activite_periodique',
                            processus_uuid=processus_uuid
                        )
                        if not has_update_permission:
                            raise serializers.ValidationError(
                                "Vous n'avez pas les permissions pour ajouter un suivi à ce détail AP."
                            )
                else:
                    # Si pas de processus UUID, vérifier si c'est le créateur (fallback)
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
        # Exception : permettre la création lors de la copie d'amendement ou pour les super admins
        from_amendment_copy = self.initial_data.get('from_amendment_copy', False)
        request = self.context.get('request')
        is_super = False
        if request and hasattr(request, 'user'):
            from parametre.permissions import can_manage_users, is_super_admin
            is_super = can_manage_users(request.user) or is_super_admin(request.user)
        
        if not detail_ap.activite_periodique.is_validated and not from_amendment_copy and not is_super:
            raise serializers.ValidationError(
                "L'Activité Périodique doit être validée avant de pouvoir renseigner les suivis. Veuillez remplir tous les champs requis des détails et valider le tableau."
            )

        # Si pas de fréquence définie, autoriser tous les mois
        if not detail_ap.frequence:
            return value

        frequence_nom = detail_ap.frequence.nom.lower()
        mois_numero = value.numero

        # Définir les mois autorisés selon la fréquence (logique fixe comme dans le tableau de bord)
        # Utilise la même logique que Periodicite.get_periodes_for_frequence
        from parametre.models import Periodicite
        
        # Mapping des trimestres aux mois
        trimestres_mois = {
            'T1': [1, 2, 3],      # 1er Trimestre
            'T2': [4, 5, 6],      # 2ème Trimestre
            'T3': [7, 8, 9],      # 3ème Trimestre
            'T4': [10, 11, 12]    # 4ème Trimestre
        }

        # Récupérer les périodes autorisées pour cette fréquence (même logique que le tableau de bord)
        periodes_autorisees = Periodicite.get_periodes_for_frequence(detail_ap.frequence.nom)
        periodes_codes = [p[0] for p in periodes_autorisees]  # Extraire les codes (T1, T2, etc.)

        # Convertir les périodes en mois autorisés
        mois_autorises = []
        for periode_code in periodes_codes:
            if periode_code in trimestres_mois:
                mois_autorises.extend(trimestres_mois[periode_code])

        if mois_numero not in mois_autorises:
            mois_nom = value.nom
            periode_labels = {
                'T1': '1er Trimestre',
                'T2': '2ème Trimestre',
                'T3': '3ème Trimestre',
                'T4': '4ème Trimestre'
            }
            allowed_periodes_labels = [
                periode_labels.get(p[0], p[1]) for p in periodes_autorisees
            ]
            raise serializers.ValidationError(
                f"Le mois '{mois_nom}' n'est pas autorisé pour la fréquence '{detail_ap.frequence.nom}'. "
                f"Périodes autorisées: {', '.join(allowed_periodes_labels)}"
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


class MediaSerializer(serializers.ModelSerializer):
    """Serializer pour les Media (utilisé dans MediaLivrable)"""
    fichier_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Media
        fields = ['uuid', 'fichier', 'url_fichier', 'fichier_url', 'description', 'created_at']
        read_only_fields = ['uuid', 'created_at']
    
    def get_fichier_url(self, obj):
        """Retourner l'URL du fichier"""
        return obj.get_url()


if MediaLivrable is not None:
    class MediaLivrableSerializer(serializers.ModelSerializer):
        """Serializer pour les MediaLivrable"""
        medias_data = serializers.SerializerMethodField()
        suivi_ap_uuid = serializers.UUIDField(source='suivi_ap.uuid', read_only=True)
        medias_count = serializers.SerializerMethodField()
        
        class Meta:
            model = MediaLivrable
            fields = ['uuid', 'titre_document', 'autre_livrable', 'medias', 
                      'medias_data', 'medias_count', 'suivi_ap', 'suivi_ap_uuid', 
                      'created_at', 'updated_at']
            read_only_fields = ['uuid', 'created_at', 'updated_at']
        
        def get_medias_data(self, obj):
            """Retourner les données des médias"""
            medias = obj.medias.all()
            return MediaSerializer(medias, many=True).data
        
        def get_medias_count(self, obj):
            """Retourner le nombre de médias"""
            return obj.medias.count()


    class MediaLivrableCreateSerializer(serializers.ModelSerializer):
        """Serializer pour la création de MediaLivrable"""
        
        class Meta:
            model = MediaLivrable
            fields = ['titre_document', 'autre_livrable', 'medias', 'suivi_ap']
        
        def validate_suivi_ap(self, value):
            """Valider que le suivi AP existe"""
            if not value:
                raise serializers.ValidationError("Le suivi AP est requis")
            return value
        
        def validate_titre_document(self, value):
            """Valider que le titre n'est pas vide"""
            if not value or not value.strip():
                raise serializers.ValidationError("Le titre du document est requis")
            return value.strip()


    class MediaLivrableUpdateSerializer(serializers.ModelSerializer):
        """Serializer pour la mise à jour de MediaLivrable"""
        
        class Meta:
            model = MediaLivrable
            fields = ['titre_document', 'autre_livrable', 'medias']
        
        def validate_titre_document(self, value):
            """Valider que le titre n'est pas vide"""
            if not value or not value.strip():
                raise serializers.ValidationError("Le titre du document est requis")
            return value.strip()
else:
    # Créer des classes vides si MediaLivrable n'est pas disponible
    class MediaLivrableSerializer(serializers.Serializer):
        pass
    
    class MediaLivrableCreateSerializer(serializers.Serializer):
        pass
    
    class MediaLivrableUpdateSerializer(serializers.Serializer):
        pass

