"""
URLs pour l'application Permissions
"""
from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # ==================== PERMISSION ACTIONS ====================
    path('actions/', views.permission_actions_list, name='permission_actions_list'),
    path('actions/<int:action_id>/', views.permission_action_detail, name='permission_action_detail'),
    
    # ==================== ROLE PERMISSION MAPPINGS ====================
    path('mappings/', views.role_permission_mappings_list, name='role_permission_mappings_list'),
    path('mappings/create/', views.role_permission_mapping_create, name='role_permission_mapping_create'),
    
    # ==================== USER PERMISSIONS ====================
    path('users/<int:user_id>/permissions/', views.user_permissions, name='user_permissions'),
    path('users/permissions/', views.user_permissions, name='user_permissions_self'),
    path('users/<int:user_id>/permissions/summary/', views.user_permissions_summary, name='user_permissions_summary'),
    path('users/permissions/summary/', views.user_permissions_summary, name='user_permissions_summary_self'),
    
    # ==================== PERMISSION OVERRIDES ====================
    path('overrides/', views.permission_overrides_list, name='permission_overrides_list'),
    path('overrides/create/', views.permission_override_create, name='permission_override_create'),
    path('overrides/<uuid:override_uuid>/delete/', views.permission_override_delete, name='permission_override_delete'),
    
    # ==================== PERMISSION AUDIT ====================
    path('audit/', views.permission_audit_list, name='permission_audit_list'),
    
    # ==================== UTILITAIRES ====================
    path('check/', views.check_permission, name='check_permission'),
    path('cache/invalidate/', views.invalidate_cache, name='invalidate_cache'),
]

