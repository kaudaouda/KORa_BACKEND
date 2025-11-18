"""
Serializers pour l'application Cartographie de Risque
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import CDR, DetailsCDR, EvaluationRisque, PlanAction, SuiviAction
from parametre.models import Processus, Versions, Media


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
    class Meta:
        model = Processus
        fields = ['uuid', 'nom', 'numero_processus']
        read_only_fields = ['uuid']


class CDRSerializer(serializers.ModelSerializer):
    """Serializer pour les CDR"""
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    processus_numero = serializers.CharField(source='processus.numero_processus', read_only=True)
    processus_uuid = serializers.UUIDField(source='processus.uuid', read_only=True)
    type_tableau_code = serializers.CharField(source='type_tableau.code', read_only=True, allow_null=True)
    type_tableau_nom = serializers.CharField(source='type_tableau.nom', read_only=True, allow_null=True)
    type_tableau_uuid = serializers.UUIDField(source='type_tableau.uuid', read_only=True, allow_null=True)
    cree_par_nom = serializers.SerializerMethodField()
    valide_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = CDR
        fields = [
            'uuid', 'annee', 'processus', 'processus_nom', 'processus_numero', 'processus_uuid',
            'type_tableau', 'type_tableau_code', 'type_tableau_nom', 'type_tableau_uuid',
            'is_validated', 'date_validation', 'valide_par', 'valide_par_nom',
            'cree_par', 'cree_par_nom', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'is_validated', 'date_validation', 'valide_par', 'created_at', 'updated_at']

    def get_cree_par_nom(self, obj):
        """Retourner le nom du créateur"""
        if obj.cree_par:
            return f"{obj.cree_par.first_name} {obj.cree_par.last_name}".strip() or obj.cree_par.username
        return None

    def get_valide_par_nom(self, obj):
        """Retourner le nom du validateur"""
        if obj.valide_par:
            return f"{obj.valide_par.first_name} {obj.valide_par.last_name}".strip() or obj.valide_par.username
        return None


class CDRCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de CDR"""
    class Meta:
        model = CDR
        fields = ['annee', 'processus', 'type_tableau', 'initial_ref']
        extra_kwargs = {
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
                        f"Un amendement ({type_tableau.code}) doit être lié à un CDR initial. "
                        "Le champ 'initial_ref' est requis."
                    )

                # Vérifier que le CDR initial est validé
                if initial_ref and not initial_ref.is_validated:
                    raise serializers.ValidationError(
                        "Le CDR initial doit être validé avant de pouvoir créer un amendement. "
                        "Veuillez d'abord valider tous les détails du CDR initial."
                    )
            elif type_tableau.code == 'INITIAL':
                # Les CDR INITIAL ne doivent pas avoir d'initial_ref
                if initial_ref:
                    raise serializers.ValidationError(
                        "Un CDR INITIAL ne peut pas avoir de référence initiale (initial_ref)."
                    )

        return data

    def create(self, validated_data):
        """Créer une CDR avec l'utilisateur connecté"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['cree_par'] = request.user

        # S'assurer que processus est toujours fourni
        if 'processus' not in validated_data or validated_data['processus'] is None:
            raise serializers.ValidationError("Le champ 'processus' est requis")

        return super().create(validated_data)


class DetailsCDRSerializer(serializers.ModelSerializer):
    """Serializer pour les détails CDR"""
    cdr_uuid = serializers.UUIDField(source='cdr.uuid', read_only=True)
    
    class Meta:
        model = DetailsCDR
        fields = [
            'uuid', 'numero_cdr', 'activites', 'objectifs',
            'evenements_indesirables_risques', 'causes', 'consequences',
            'cdr', 'cdr_uuid', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class DetailsCDRCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de détails CDR"""
    numero_cdr = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = DetailsCDR
        fields = [
            'cdr', 'numero_cdr', 'activites', 'objectifs',
            'evenements_indesirables_risques', 'causes', 'consequences'
        ]
        extra_kwargs = {
            'activites': {'required': False, 'allow_null': True, 'allow_blank': True},
            'objectifs': {'required': False, 'allow_null': True, 'allow_blank': True},
            'evenements_indesirables_risques': {'required': False, 'allow_null': True, 'allow_blank': True},
            'causes': {'required': False, 'allow_null': True, 'allow_blank': True},
            'consequences': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate_cdr(self, value):
        """Vérifier que la CDR appartient à l'utilisateur connecté"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.cree_par != request.user:
                raise serializers.ValidationError(
                    "Vous n'avez pas les permissions pour ajouter un détail à cette CDR."
                )

        # Protection : empêcher la création de détail si la CDR est validée
        if value.is_validated:
            raise serializers.ValidationError(
                "Cette CDR est validée. Impossible de créer un nouveau détail."
            )

        return value

    def create(self, validated_data):
        """Créer un détail CDR avec génération automatique du numéro si nécessaire"""
        # Vérifier si c'est une copie d'amendement (flag from_amendment_copy)
        request = self.context.get('request')
        from_amendment_copy = request and (
            request.data.get('from_amendment_copy', False) or
            request.data.get('from_amendment_copy') == 'true' or
            request.data.get('from_amendment_copy') == True
        )
        numero_cdr_provided = validated_data.get('numero_cdr')
        cdr = validated_data.get('cdr')

        # Vérifier si le CDR est un amendement
        is_amendment = False
        if cdr and cdr.type_tableau:
            type_code = cdr.type_tableau.code
            is_amendment = type_code in ['AMENDEMENT_1', 'AMENDEMENT_2']

        # CAS 1: Copie d'amendement avec numéro fourni - TOUJOURS utiliser le numéro fourni
        # Pour les amendements, on peut toujours réutiliser le même numéro que l'initial
        if is_amendment and numero_cdr_provided and str(numero_cdr_provided).strip():
            original_numero = str(numero_cdr_provided).strip()
            validated_data['numero_cdr'] = original_numero
            return super().create(validated_data)

        # CAS 2: Copie d'amendement (flag explicite) avec numéro fourni
        if from_amendment_copy and numero_cdr_provided and str(numero_cdr_provided).strip():
            original_numero = str(numero_cdr_provided).strip()
            validated_data['numero_cdr'] = original_numero
            return super().create(validated_data)

        # CAS 3: Génération automatique du numéro
        # Si aucun numéro n'est fourni ou si c'est une chaîne vide, générer automatiquement
        if not numero_cdr_provided or (isinstance(numero_cdr_provided, str) and numero_cdr_provided.strip() == ''):
            # Compter les détails existants pour cette CDR
            existing_count = DetailsCDR.objects.filter(cdr=cdr).count()
            numero_cdr = f"CDR-{existing_count + 1}"
            validated_data['numero_cdr'] = numero_cdr

        return super().create(validated_data)


class DetailsCDRUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de détails CDR"""
    
    class Meta:
        model = DetailsCDR
        fields = [
            'numero_cdr', 'activites', 'objectifs',
            'evenements_indesirables_risques', 'causes', 'consequences'
        ]
        extra_kwargs = {
            'numero_cdr': {'required': False, 'allow_null': True, 'allow_blank': True},
            'activites': {'required': False, 'allow_null': True, 'allow_blank': True},
            'objectifs': {'required': False, 'allow_null': True, 'allow_blank': True},
            'evenements_indesirables_risques': {'required': False, 'allow_null': True, 'allow_blank': True},
            'causes': {'required': False, 'allow_null': True, 'allow_blank': True},
            'consequences': {'required': False, 'allow_null': True, 'allow_blank': True},
        }
    
    def update(self, instance, validated_data):
        """Mettre à jour un détail CDR"""
        # Protection : empêcher la modification si la CDR est validée
        if instance.cdr.is_validated:
            raise serializers.ValidationError(
                "Cette CDR est validée. Les champs de détail ne peuvent plus être modifiés."
            )
        
        return super().update(instance, validated_data)


class EvaluationRisqueSerializer(serializers.ModelSerializer):
    """Serializer pour les évaluations de risque"""
    frequence_libelle = serializers.CharField(source='frequence.libelle', read_only=True)
    gravite_libelle = serializers.CharField(source='gravite.libelle', read_only=True)
    criticite_libelle = serializers.CharField(source='criticite.libelle', read_only=True)
    risque_libelle = serializers.CharField(source='risque.libelle', read_only=True)
    details_cdr_uuid = serializers.UUIDField(source='details_cdr.uuid', read_only=True)
    
    class Meta:
        model = EvaluationRisque
        fields = [
            'uuid', 'details_cdr', 'details_cdr_uuid',
            'frequence', 'frequence_libelle',
            'gravite', 'gravite_libelle',
            'criticite', 'criticite_libelle',
            'risque', 'risque_libelle',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
        depth = 1  # Inclure les objets ForeignKey jusqu'à 1 niveau de profondeur


class EvaluationRisqueCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'évaluations de risque"""
    
    class Meta:
        model = EvaluationRisque
        fields = ['details_cdr', 'frequence', 'gravite', 'criticite', 'risque']
        extra_kwargs = {
            'frequence': {'required': False, 'allow_null': True},
            'gravite': {'required': False, 'allow_null': True},
            'criticite': {'required': False, 'allow_null': True},
            'risque': {'required': False, 'allow_null': True},
        }
    
    def validate_details_cdr(self, value):
        """Vérifier que le détail CDR appartient à l'utilisateur connecté"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.cdr.cree_par != request.user:
                raise serializers.ValidationError(
                    "Vous n'avez pas les permissions pour ajouter une évaluation à ce détail CDR."
                )
            if value.cdr.is_validated:
                raise serializers.ValidationError(
                    "Cette CDR est validée. Impossible de créer une nouvelle évaluation."
                )
        return value
    
    def calculate_criticite(self, frequence, gravite):
        """Calculer automatiquement la criticité à partir de la fréquence et de la gravité"""
        from parametre.models import CriticiteRisque
        
        if not frequence or not gravite:
            return None
        
        # Récupérer les valeurs de la fréquence et de la gravité
        # Utiliser le libellé comme fallback si valeur/code est null
        freq_valeur = frequence.valeur if hasattr(frequence, 'valeur') and frequence.valeur else (frequence.libelle if hasattr(frequence, 'libelle') else None)
        grav_code = gravite.code if hasattr(gravite, 'code') and gravite.code else (gravite.libelle if hasattr(gravite, 'libelle') else None)
        
        if not freq_valeur or not grav_code:
            return None
        
        # Calculer la criticité : combinaison de la valeur de fréquence et du code de gravité
        criticite_libelle = f"{freq_valeur}{grav_code}"
        
        # Chercher ou créer la CriticiteRisque correspondante
        criticite, created = CriticiteRisque.objects.get_or_create(
            libelle=criticite_libelle,
            defaults={'is_active': True}
        )
        
        return criticite
    
    def find_risque_by_criticite(self, criticite):
        """Trouver automatiquement le risque correspondant à une criticité"""
        from parametre.models import Risque
        
        if not criticite:
            return None
        
        # Récupérer le libellé de la criticité
        criticite_libelle = criticite.libelle if hasattr(criticite, 'libelle') else str(criticite)
        
        # Chercher un risque actif qui contient cette criticité dans ses niveaux_risque
        # Utiliser une recherche manuelle car JSONField peut avoir des problèmes avec __contains
        try:
            risques = Risque.objects.filter(is_active=True)
            for r in risques:
                if r.niveaux_risque and isinstance(r.niveaux_risque, list):
                    # Vérifier si la criticité est dans la liste des niveaux_risque
                    if criticite_libelle in r.niveaux_risque:
                        return r
        except Exception as e:
            # En cas d'erreur, logger et retourner None
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de la recherche du risque par criticité {criticite_libelle}: {str(e)}")
            return None
        
        return None
    
    def create(self, validated_data):
        """Créer une évaluation de risque avec calcul automatique de la criticité et détection du risque"""
        frequence = validated_data.get('frequence')
        gravite = validated_data.get('gravite')
        criticite = validated_data.get('criticite')
        risque = validated_data.get('risque')
        
        # Toujours calculer la criticité à partir de la fréquence et de la gravité si elles sont fournies
        # Cela garantit que la criticité est toujours cohérente
        if frequence and gravite:
            calculated_criticite = self.calculate_criticite(frequence, gravite)
            if calculated_criticite:
                validated_data['criticite'] = calculated_criticite
                criticite = calculated_criticite
        
        # Si une criticité est définie (calculée ou fournie) et qu'aucun risque n'est fourni,
        # chercher automatiquement le risque correspondant
        if criticite and not risque:
            risque_correspondant = self.find_risque_by_criticite(criticite)
            if risque_correspondant:
                validated_data['risque'] = risque_correspondant
        
        return super().create(validated_data)


class EvaluationRisqueUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'évaluations de risque"""
    
    class Meta:
        model = EvaluationRisque
        fields = ['frequence', 'gravite', 'criticite', 'risque']
        extra_kwargs = {
            'frequence': {'required': False},
            'gravite': {'required': False},
            'criticite': {'required': False},
            'risque': {'required': False},
        }
    
    def calculate_criticite(self, frequence, gravite):
        """Calculer automatiquement la criticité à partir de la fréquence et de la gravité"""
        from parametre.models import CriticiteRisque
        
        if not frequence or not gravite:
            return None
        
        # Récupérer les valeurs de la fréquence et de la gravité
        # Utiliser le libellé comme fallback si valeur/code est null
        freq_valeur = frequence.valeur if hasattr(frequence, 'valeur') and frequence.valeur else (frequence.libelle if hasattr(frequence, 'libelle') else None)
        grav_code = gravite.code if hasattr(gravite, 'code') and gravite.code else (gravite.libelle if hasattr(gravite, 'libelle') else None)
        
        if not freq_valeur or not grav_code:
            return None
        
        # Calculer la criticité : combinaison de la valeur de fréquence et du code de gravité
        criticite_libelle = f"{freq_valeur}{grav_code}"
        
        # Chercher ou créer la CriticiteRisque correspondante
        criticite, created = CriticiteRisque.objects.get_or_create(
            libelle=criticite_libelle,
            defaults={'is_active': True}
        )
        
        return criticite
    
    def find_risque_by_criticite(self, criticite):
        """Trouver automatiquement le risque correspondant à une criticité"""
        from parametre.models import Risque
        
        if not criticite:
            return None
        
        # Récupérer le libellé de la criticité
        criticite_libelle = criticite.libelle if hasattr(criticite, 'libelle') else str(criticite)
        
        # Chercher un risque actif qui contient cette criticité dans ses niveaux_risque
        # Utiliser une recherche manuelle car JSONField peut avoir des problèmes avec __contains
        try:
            risques = Risque.objects.filter(is_active=True)
            for r in risques:
                if r.niveaux_risque and isinstance(r.niveaux_risque, list):
                    # Vérifier si la criticité est dans la liste des niveaux_risque
                    if criticite_libelle in r.niveaux_risque:
                        return r
        except Exception as e:
            # En cas d'erreur, logger et retourner None
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de la recherche du risque par criticité {criticite_libelle}: {str(e)}")
            return None
        
        return None
    
    def update(self, instance, validated_data):
        """Mettre à jour une évaluation de risque avec détection automatique du risque"""
        # Protection : empêcher la modification si la CDR est validée
        if instance.details_cdr.cdr.is_validated:
            raise serializers.ValidationError(
                "Cette CDR est validée. Les champs d'évaluation ne peuvent plus être modifiés."
            )
        
        # Récupérer la fréquence et la gravité (soit depuis validated_data, soit depuis l'instance)
        frequence = validated_data.get('frequence', instance.frequence)
        gravite = validated_data.get('gravite', instance.gravite)
        criticite = validated_data.get('criticite', instance.criticite)
        risque = validated_data.get('risque', instance.risque)
        
        # Toujours recalculer la criticité à partir de la fréquence et de la gravité si elles sont fournies
        # Cela garantit que la criticité est toujours cohérente après une mise à jour
        criticite_a_change = False
        if frequence and gravite:
            calculated_criticite = self.calculate_criticite(frequence, gravite)
            if calculated_criticite:
                # Vérifier si la criticité a changé
                if instance.criticite != calculated_criticite:
                    criticite_a_change = True
                validated_data['criticite'] = calculated_criticite
                criticite = calculated_criticite
        
        # Si une criticité est définie (calculée ou fournie), chercher automatiquement le risque correspondant
        # Toujours vérifier et mettre à jour le risque pour qu'il corresponde à la criticité
        if criticite:
            risque_correspondant = self.find_risque_by_criticite(criticite)
            if risque_correspondant:
                # Récupérer le risque actuel et le risque fourni
                risque_fourni = validated_data.get('risque')
                risque_actuel = instance.risque if hasattr(instance, 'risque') else None
                
                # Déterminer quel risque utiliser pour la comparaison
                risque_a_verifier = risque_fourni if risque_fourni is not None else risque_actuel
                
                # Mettre à jour le risque si :
                # 1. La criticité a changé (donc le risque doit être mis à jour)
                # 2. Le risque actuel ou fourni ne correspond pas au risque correspondant
                # 3. Aucun risque n'existe
                doit_mettre_a_jour = False
                if criticite_a_change:
                    # Si la criticité a changé, toujours mettre à jour le risque
                    doit_mettre_a_jour = True
                elif not risque_a_verifier:
                    # Si aucun risque n'existe, mettre à jour
                    doit_mettre_a_jour = True
                elif risque_a_verifier != risque_correspondant:
                    # Si le risque ne correspond pas à la criticité, mettre à jour
                    doit_mettre_a_jour = True
                
                if doit_mettre_a_jour:
                    validated_data['risque'] = risque_correspondant
        
        return super().update(instance, validated_data)


class PlanActionSerializer(serializers.ModelSerializer):
    """Serializer pour les plans d'action"""
    responsable_nom = serializers.SerializerMethodField()
    details_cdr_uuid = serializers.UUIDField(source='details_cdr.uuid', read_only=True)
    
    class Meta:
        model = PlanAction
        fields = [
            'uuid', 'details_cdr', 'details_cdr_uuid',
            'actions_mesures', 'responsable', 'responsable_nom',
            'delai_realisation', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
        depth = 1  # Inclure les objets ForeignKey jusqu'à 1 niveau de profondeur
    
    def get_responsable_nom(self, obj):
        """Retourner le nom du responsable (Direction)"""
        if obj.responsable:
            return obj.responsable.nom
        return None


class PlanActionCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de plans d'action"""
    
    class Meta:
        model = PlanAction
        fields = ['details_cdr', 'actions_mesures', 'responsable', 'delai_realisation']
        extra_kwargs = {
            'actions_mesures': {'required': False, 'allow_null': True, 'allow_blank': True},
            'responsable': {'required': False, 'allow_null': True},
            'delai_realisation': {'required': False, 'allow_null': True},
        }
    
    def validate_responsable(self, value):
        """Valider que le responsable est une Direction valide"""
        if value is not None and value != '':
            from parametre.models import Direction
            import uuid as uuid_lib
            try:
                # Si value est déjà un objet Direction, c'est bon
                if isinstance(value, Direction):
                    return value
                # Si c'est une chaîne vide, retourner None
                if isinstance(value, str) and value.strip() == '':
                    return None
                # Sinon, c'est probablement un UUID (string ou UUID object)
                direction_uuid = str(value) if not isinstance(value, uuid_lib.UUID) else value
                direction = Direction.objects.get(uuid=direction_uuid)
                return direction
            except (Direction.DoesNotExist, ValueError, TypeError) as e:
                raise serializers.ValidationError(f"La direction sélectionnée n'existe pas: {str(e)}")
        return None
    
    def validate_details_cdr(self, value):
        """Vérifier que le détail CDR appartient à l'utilisateur connecté"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.cdr.cree_par != request.user:
                raise serializers.ValidationError(
                    "Vous n'avez pas les permissions pour ajouter un plan d'action à ce détail CDR."
                )
            if value.cdr.is_validated:
                raise serializers.ValidationError(
                    "Cette CDR est validée. Impossible de créer un nouveau plan d'action."
                )
        return value
    
    def create(self, validated_data):
        """Créer un plan d'action sans créer automatiquement de suivis"""
        # Créer uniquement le plan d'action, sans créer de suivis automatiquement
        return super().create(validated_data)


class PlanActionUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de plans d'action"""
    
    class Meta:
        model = PlanAction
        fields = ['actions_mesures', 'responsable', 'delai_realisation']
        extra_kwargs = {
            'actions_mesures': {'required': False, 'allow_null': True, 'allow_blank': True},
            'responsable': {'required': False, 'allow_null': True},
            'delai_realisation': {'required': False, 'allow_null': True},
        }
    
    def validate_responsable(self, value):
        """Valider que le responsable est une Direction valide"""
        if value is not None and value != '':
            from parametre.models import Direction
            import uuid as uuid_lib
            try:
                # Si value est déjà un objet Direction, c'est bon
                if isinstance(value, Direction):
                    return value
                # Si c'est une chaîne vide, retourner None
                if isinstance(value, str) and value.strip() == '':
                    return None
                # Sinon, c'est probablement un UUID (string ou UUID object)
                direction_uuid = str(value) if not isinstance(value, uuid_lib.UUID) else value
                direction = Direction.objects.get(uuid=direction_uuid)
                return direction
            except (Direction.DoesNotExist, ValueError, TypeError) as e:
                raise serializers.ValidationError(f"La direction sélectionnée n'existe pas: {str(e)}")
        return None
    
    def update(self, instance, validated_data):
        """Mettre à jour un plan d'action"""
        # Protection : empêcher la modification si la CDR est validée
        if instance.details_cdr.cdr.is_validated:
            raise serializers.ValidationError(
                "Cette CDR est validée. Les champs du plan d'action ne peuvent plus être modifiés."
            )
        
        return super().update(instance, validated_data)


class SuiviActionSerializer(serializers.ModelSerializer):
    """Serializer pour les suivis d'action"""
    plan_action_uuid = serializers.UUIDField(source='plan_action.uuid', read_only=True)
    element_preuve_nom = serializers.SerializerMethodField()
    element_preuve_url = serializers.SerializerMethodField()
    element_preuve_urls = serializers.SerializerMethodField()
    statut_action_display = serializers.CharField(source='get_statut_action_display', read_only=True)
    
    class Meta:
        model = SuiviAction
        fields = [
            'uuid', 'plan_action', 'plan_action_uuid',
            'date_realisation', 'statut_action', 'statut_action_display',
            'date_cloture', 'element_preuve', 'element_preuve_nom', 'element_preuve_url', 'element_preuve_urls',
            'critere_efficacite_objectif_vise', 'resultats_mise_en_oeuvre',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_element_preuve_nom(self, obj):
        """Retourner le nom/description de la preuve"""
        if obj.element_preuve:
            return obj.element_preuve.description
        return None
    
    def get_element_preuve_url(self, obj):
        """Retourner l'URL du premier média de la preuve"""
        try:
            if obj.element_preuve and obj.element_preuve.medias.exists():
                media = obj.element_preuve.medias.first()
                if media:
                    if hasattr(media, 'get_url'):
                        return media.get_url()
                    return getattr(media, 'url_fichier', None)
        except Exception:
            pass
        return None

    def get_element_preuve_urls(self, obj):
        """Retourner la liste de toutes les URLs des médias de la preuve"""
        urls = []
        try:
            if obj.element_preuve:
                for media in obj.element_preuve.medias.all():
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


class SuiviActionCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de suivis d'action"""
    
    class Meta:
        model = SuiviAction
        fields = [
            'plan_action', 'date_realisation', 'statut_action',
            'date_cloture', 'element_preuve',
            'critere_efficacite_objectif_vise', 'resultats_mise_en_oeuvre'
        ]
        extra_kwargs = {
            'date_realisation': {'required': False, 'allow_null': True},
            'statut_action': {'required': False, 'allow_null': True},
            'date_cloture': {'required': False, 'allow_null': True},
            'element_preuve': {'required': False, 'allow_null': True},
            'critere_efficacite_objectif_vise': {'required': False, 'allow_null': True, 'allow_blank': True},
            'resultats_mise_en_oeuvre': {'required': False, 'allow_null': True, 'allow_blank': True},
        }
    
    def validate_plan_action(self, value):
        """Vérifier que le plan d'action appartient à l'utilisateur connecté et que la CDR est validée"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.details_cdr.cdr.cree_par != request.user:
                raise serializers.ValidationError(
                    "Vous n'avez pas les permissions pour ajouter un suivi à ce plan d'action."
                )
            # Vérifier si c'est une copie d'amendement (flag from_amendment_copy)
            from_amendment_copy = request.data.get('from_amendment_copy', False) or \
                                 request.data.get('from_amendment_copy') == 'true' or \
                                 request.data.get('from_amendment_copy') == True
            # Les suivis d'actions ne peuvent être créés que si la CDR est validée
            # SAUF lors d'une copie d'amendement (où on copie les suivis existants)
            if not value.details_cdr.cdr.is_validated and not from_amendment_copy:
                raise serializers.ValidationError(
                    "Les suivis d'actions ne peuvent être créés qu'après validation de la CDR."
                )
        return value
    
    def validate_date_realisation(self, value):
        """Valider que la date de réalisation n'est pas inférieure au délai de réalisation du plan d'action"""
        if value is not None:
            plan_action = None
            # Pour la création, récupérer depuis initial_data
            if hasattr(self, 'initial_data'):
                plan_action = self.initial_data.get('plan_action')
            
            if plan_action:
                delai_realisation = None
                # Si plan_action est un objet, utiliser directement
                if hasattr(plan_action, 'delai_realisation'):
                    delai_realisation = plan_action.delai_realisation
                else:
                    # Sinon, c'est probablement un UUID, récupérer l'objet
                    from .models import PlanAction
                    try:
                        plan_action_uuid = str(plan_action) if not hasattr(plan_action, 'uuid') else plan_action.uuid
                        plan_action_obj = PlanAction.objects.select_related('details_cdr__cdr').get(uuid=plan_action_uuid)
                        delai_realisation = plan_action_obj.delai_realisation
                    except (PlanAction.DoesNotExist, ValueError, TypeError):
                        return value  # La validation du plan_action gérera cette erreur
                
                if delai_realisation and value < delai_realisation:
                    raise serializers.ValidationError(
                        f"La date de réalisation ({value}) ne peut pas être antérieure au délai de réalisation du plan d'action ({delai_realisation})."
                )
        return value


class SuiviActionUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de suivis d'action"""
    
    class Meta:
        model = SuiviAction
        fields = [
            'date_realisation', 'statut_action',
            'date_cloture', 'element_preuve',
            'critere_efficacite_objectif_vise', 'resultats_mise_en_oeuvre'
        ]
        extra_kwargs = {
            'date_realisation': {'required': False, 'allow_null': True},
            'statut_action': {'required': False, 'allow_null': True},
            'date_cloture': {'required': False, 'allow_null': True},
            'element_preuve': {'required': False, 'allow_null': True},
            'critere_efficacite_objectif_vise': {'required': False, 'allow_null': True, 'allow_blank': True},
            'resultats_mise_en_oeuvre': {'required': False, 'allow_null': True, 'allow_blank': True},
        }
    
    def validate_date_realisation(self, value):
        """Valider que la date de réalisation n'est pas inférieure au délai de réalisation du plan d'action"""
        if value is not None:
            # Pour la mise à jour, on peut accéder à l'instance
            if hasattr(self, 'instance') and self.instance:
                plan_action = self.instance.plan_action
                if plan_action and plan_action.delai_realisation:
                    if value < plan_action.delai_realisation:
                        raise serializers.ValidationError(
                            f"La date de réalisation ({value}) ne peut pas être antérieure au délai de réalisation du plan d'action ({plan_action.delai_realisation})."
                        )
        return value
    
    def update(self, instance, validated_data):
        """Mettre à jour un suivi d'action"""
        # Les suivis d'actions ne peuvent être modifiés que si la CDR est validée
        if not instance.plan_action.details_cdr.cdr.is_validated:
            raise serializers.ValidationError(
                "Les suivis d'actions ne peuvent être modifiés qu'après validation de la CDR."
            )
        
        return super().update(instance, validated_data)

