"""
Serializers pour le système générique de permissions
"""
from rest_framework import serializers
from django.contrib.auth.models import User

from permissions.models import (
    PermissionAction,
    RolePermissionMapping,
    AppPermission,
    PermissionOverride,
    PermissionAudit
)
from parametre.models import Role, Processus


class PermissionActionSerializer(serializers.ModelSerializer):
    """Serializer pour PermissionAction"""
    
    class Meta:
        model = PermissionAction
        fields = [
            'id', 'app_name', 'code', 'nom', 'description',
            'category', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PermissionActionListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des PermissionAction"""
    
    class Meta:
        model = PermissionAction
        fields = ['id', 'code', 'nom', 'app_name', 'category', 'is_active']


class RolePermissionMappingSerializer(serializers.ModelSerializer):
    """Serializer pour RolePermissionMapping"""
    
    role_nom = serializers.CharField(source='role.nom', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    permission_action_code = serializers.CharField(source='permission_action.code', read_only=True)
    permission_action_nom = serializers.CharField(source='permission_action.nom', read_only=True)
    app_name = serializers.CharField(source='permission_action.app_name', read_only=True)
    
    class Meta:
        model = RolePermissionMapping
        fields = [
            'id', 'role', 'role_nom', 'role_code',
            'permission_action', 'permission_action_code', 'permission_action_nom', 'app_name',
            'granted', 'conditions', 'priority', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RolePermissionMappingCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un RolePermissionMapping"""
    
    role = serializers.UUIDField(required=True)
    permission_action = serializers.IntegerField(required=True)
    # Important: required=False mais pas de default pour accepter explicitement False
    granted = serializers.BooleanField(required=False, allow_null=False)
    conditions = serializers.JSONField(required=False, allow_null=True)
    priority = serializers.IntegerField(required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True, allow_null=False)
    
    class Meta:
        model = RolePermissionMapping
        fields = [
            'role', 'permission_action', 'granted',
            'conditions', 'priority', 'is_active'
        ]
        # Désactiver la validation d'unicité au niveau du serializer
        # car nous utilisons update_or_create dans la vue pour gérer l'unicité
        validators = []
    
    def validate_role(self, value):
        """Valider que le rôle existe"""
        from parametre.models import Role
        try:
            role = Role.objects.get(uuid=value)
            return role
        except Role.DoesNotExist:
            raise serializers.ValidationError(f"Le rôle avec l'UUID {value} n'existe pas.")
    
    def validate_permission_action(self, value):
        """Valider que l'action de permission existe"""
        from permissions.models import PermissionAction
        try:
            action = PermissionAction.objects.get(id=value)
            return action
        except PermissionAction.DoesNotExist:
            raise serializers.ValidationError(f"L'action de permission avec l'ID {value} n'existe pas.")
    
    def validate_granted(self, value):
        """Valider et normaliser la valeur de granted"""
        # S'assurer que c'est bien un boolean
        if value is None:
            return True  # Valeur par défaut
        return bool(value)
    
    def validate(self, attrs):
        """Validation globale"""
        # S'assurer que granted a une valeur par défaut si non fourni dans les données
        # Mais seulement si la clé n'existe vraiment pas dans request.data
        # (pas si elle vaut False)
        if 'granted' not in attrs:
            attrs['granted'] = True
        return attrs


class AppPermissionSerializer(serializers.ModelSerializer):
    """Serializer pour AppPermission"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    processus_uuid = serializers.UUIDField(source='processus.uuid', read_only=True)
    permission_action_code = serializers.CharField(source='permission_action.code', read_only=True)
    permission_action_nom = serializers.CharField(source='permission_action.nom', read_only=True)
    
    class Meta:
        model = AppPermission
        fields = [
            'uuid', 'user', 'user_username', 'user_email',
            'processus', 'processus_nom', 'processus_uuid',
            'app_name', 'permission_action', 'permission_action_code', 'permission_action_nom',
            'can_create', 'can_read', 'can_update', 'can_delete',
            'can_validate', 'can_create_amendement',
            'can_manage_details', 'can_manage_evaluations',
            'can_manage_plans_action', 'can_manage_suivis',
            'can_edit_when_validated', 'can_edit_only_own',
            'can_delete_only_own', 'can_validate_own',
            'date_debut', 'date_fin', 'is_active',
            'source_type', 'source_id', 'last_calculated_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'created_at', 'updated_at',
            'last_calculated_at', 'source_type', 'source_id'
        ]


class PermissionOverrideSerializer(serializers.ModelSerializer):
    """Serializer pour PermissionOverride"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    processus_nom = serializers.CharField(source='processus.nom', read_only=True)
    permission_action_code = serializers.CharField(source='permission_action.code', read_only=True)
    cree_par_username = serializers.CharField(source='cree_par.username', read_only=True, allow_null=True)
    
    class Meta:
        model = PermissionOverride
        fields = [
            'uuid', 'user', 'user_username',
            'processus', 'processus_nom',
            'app_name', 'permission_action', 'permission_action_code',
            'granted', 'conditions', 'raison',
            'date_debut', 'date_fin', 'is_active',
            'cree_par', 'cree_par_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class PermissionOverrideCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un PermissionOverride"""
    
    class Meta:
        model = PermissionOverride
        fields = [
            'user', 'processus', 'app_name', 'permission_action',
            'granted', 'conditions', 'raison',
            'date_debut', 'date_fin', 'is_active', 'cree_par'
        ]
    
    def validate(self, data):
        """Valider les dates"""
        date_debut = data.get('date_debut')
        date_fin = data.get('date_fin')
        
        if date_debut and date_fin and date_debut > date_fin:
            raise serializers.ValidationError({
                'date_fin': 'La date de fin doit être postérieure à la date de début'
            })
        
        return data


class PermissionAuditSerializer(serializers.ModelSerializer):
    """Serializer pour PermissionAudit (lecture seule)"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    processus_nom = serializers.CharField(source='processus.nom', read_only=True, allow_null=True)
    granted_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PermissionAudit
        fields = [
            'id', 'user', 'user_username', 'user_email',
            'app_name', 'action_code',
            'processus', 'processus_nom',
            'granted', 'granted_display', 'reason',
            'ip_address', 'user_agent', 'timestamp',
            'resolution_method', 'execution_time_ms', 'cache_hit'
        ]
        read_only_fields = '__all__'
    
    def get_granted_display(self, obj):
        """Affiche le statut de manière lisible"""
        return "Accordée" if obj.granted else "Refusée"


class UserPermissionsSummarySerializer(serializers.Serializer):
    """Serializer pour résumer les permissions d'un utilisateur"""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    app_name = serializers.CharField()
    processus_uuid = serializers.UUIDField()
    processus_nom = serializers.CharField()
    permissions = serializers.DictField()
    total_permissions = serializers.IntegerField()
    granted_permissions = serializers.IntegerField()
    denied_permissions = serializers.IntegerField()
