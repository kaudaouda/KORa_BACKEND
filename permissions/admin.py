"""
Configuration Admin Django pour le système générique de permissions
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PermissionAction,
    RolePermissionMapping,
    AppPermission,
    PermissionOverride,
    PermissionAudit
)


@admin.register(PermissionAction)
class PermissionActionAdmin(admin.ModelAdmin):
    """
    Admin pour PermissionAction - Catalogue des actions possibles
    """
    list_display = ('code', 'nom', 'app_name', 'category', 'is_active', 'created_at')
    list_filter = ('app_name', 'category', 'is_active', 'created_at')
    search_fields = ('code', 'nom', 'description', 'app_name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('app_name', 'code')
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('app_name', 'code', 'nom', 'description')
        }),
        ('Classification', {
            'fields': ('category', 'is_active')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RolePermissionMapping)
class RolePermissionMappingAdmin(admin.ModelAdmin):
    """
    Admin pour RolePermissionMapping - Mapping rôle → permissions
    """
    list_display = ('role', 'permission_action', 'granted', 'priority', 'is_active', 'created_at')
    list_filter = ('granted', 'is_active', 'permission_action__app_name', 'role', 'created_at')
    search_fields = ('role__nom', 'role__code', 'permission_action__code', 'permission_action__nom')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('role', 'permission_action')
    ordering = ('role', 'priority', 'permission_action')
    
    fieldsets = (
        ('Mapping', {
            'fields': ('role', 'permission_action', 'granted')
        }),
        ('Configuration', {
            'fields': ('priority', 'conditions', 'is_active')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AppPermission)
class AppPermissionAdmin(admin.ModelAdmin):
    """
    Admin pour AppPermission - Permissions résolues et calculées
    """
    list_display = (
        'user', 'app_name', 'processus', 'permission_action', 
        'can_read', 'can_create', 'can_update', 'can_delete', 
        'is_active', 'last_calculated_at'
    )
    list_filter = (
        'app_name', 'is_active', 'can_create', 'can_read', 
        'can_update', 'can_delete', 'can_validate', 'source_type',
        'last_calculated_at'
    )
    search_fields = (
        'user__username', 'user__email', 'processus__nom', 
        'permission_action__code', 'permission_action__nom'
    )
    readonly_fields = (
        'uuid', 'created_at', 'updated_at', 'last_calculated_at',
        'source_type', 'source_id'
    )
    raw_id_fields = ('user', 'processus', 'permission_action')
    ordering = ('user', 'app_name', 'processus', 'permission_action')
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('user', 'processus', 'app_name', 'permission_action')
        }),
        ('Permissions principales', {
            'fields': (
                'can_create', 'can_read', 'can_update', 
                'can_delete', 'can_validate', 'can_create_amendement'
            ),
            'classes': ('wide',)
        }),
        ('Permissions sous-entités', {
            'fields': (
                'can_manage_details', 'can_manage_evaluations',
                'can_manage_plans_action', 'can_manage_suivis'
            ),
            'classes': ('wide',)
        }),
        ('Conditions contextuelles', {
            'fields': (
                'can_edit_when_validated', 'can_edit_only_own',
                'can_delete_only_own', 'can_validate_own'
            ),
            'classes': ('wide',)
        }),
        ('Validité temporelle', {
            'fields': ('date_debut', 'date_fin', 'is_active')
        }),
        ('Métadonnées', {
            'fields': ('source_type', 'source_id', 'last_calculated_at'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PermissionOverride)
class PermissionOverrideAdmin(admin.ModelAdmin):
    """
    Admin pour PermissionOverride - Permissions personnalisées
    """
    list_display = (
        'user', 'app_name', 'processus', 'permission_action', 
        'granted', 'is_active', 'cree_par', 'created_at'
    )
    list_filter = (
        'app_name', 'granted', 'is_active', 'cree_par', 'created_at'
    )
    search_fields = (
        'user__username', 'user__email', 'processus__nom',
        'permission_action__code', 'raison'
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    raw_id_fields = ('user', 'processus', 'permission_action', 'cree_par')
    ordering = ('user', 'app_name', 'processus', 'permission_action')
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('user', 'processus', 'app_name', 'permission_action', 'granted')
        }),
        ('Configuration', {
            'fields': ('conditions', 'raison', 'is_active')
        }),
        ('Validité temporelle', {
            'fields': ('date_debut', 'date_fin')
        }),
        ('Audit', {
            'fields': ('cree_par',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PermissionAudit)
class PermissionAuditAdmin(admin.ModelAdmin):
    """
    Admin pour PermissionAudit - Traçabilité des vérifications
    """
    list_display = (
        'user', 'app_name', 'action', 'processus', 
        'granted_display', 'timestamp', 'resolution_method', 'execution_time_ms'
    )
    list_filter = (
        'app_name', 'action', 'granted', 'resolution_method', 
        'cache_hit', 'timestamp'
    )
    search_fields = (
        'user__username', 'user__email', 'action', 
        'processus__nom', 'reason', 'ip_address'
    )
    readonly_fields = (
        'id', 'user', 'app_name', 'action', 'processus', 
        'entity_id', 'entity_type', 'granted', 'reason',
        'ip_address', 'user_agent', 'timestamp',
        'resolution_method', 'execution_time_ms', 'cache_hit'
    )
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    def granted_display(self, obj):
        """Affiche granted avec une couleur"""
        if obj.granted:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Accordée</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Refusée</span>'
            )
    granted_display.short_description = 'Statut'
    
    fieldsets = (
        ('Vérification', {
            'fields': (
                'user', 'app_name', 'action', 'processus',
                'entity_type', 'entity_id', 'granted', 'reason'
            )
        }),
        ('Contexte', {
            'fields': ('ip_address', 'user_agent', 'timestamp')
        }),
        ('Performance', {
            'fields': ('resolution_method', 'execution_time_ms', 'cache_hit'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Les audits ne peuvent pas être créés manuellement"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Les audits sont en lecture seule"""
        return False
