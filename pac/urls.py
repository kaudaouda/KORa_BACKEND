"""
URLs pour l'application PAC
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== AUTHENTIFICATION ====================
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/profile/', views.user_profile, name='user_profile'),
    path('auth/profile/update/', views.update_profile, name='update_profile'),
    path('auth/profile/admin-update/', views.admin_update_profile, name='admin_update_profile'),
    path('auth/password/change/', views.change_password, name='change_password'),
    path('auth/refresh/', views.refresh_token, name='refresh_token'),
    path('auth/recaptcha-config/', views.recaptcha_config, name='recaptcha_config'),
    
    # ==================== API PAC ====================
    path('pac/', views.pac_list, name='pac_list'),
    path('pac/create/', views.pac_create, name='pac_create'),
    path('pac/get-or-create/', views.pac_get_or_create, name='pac_get_or_create'),
    path('pac/<uuid:uuid>/', views.pac_detail, name='pac_detail'),
    path('pac/<uuid:uuid>/complet/', views.pac_complet, name='pac_complet'),
    path('pac/<uuid:uuid>/update/', views.pac_update, name='pac_update'),
    path('pac/<uuid:uuid>/delete/', views.pac_delete, name='pac_delete'),
    path('pac/<uuid:uuid>/validate/', views.pac_validate, name='pac_validate'),
    path('pac/validate-by-type/', views.pac_validate_by_type, name='pac_validate_by_type'),
    path('pac/<uuid:uuid>/unvalidate/', views.pac_unvalidate, name='pac_unvalidate'),
    
    # ==================== API TRAITEMENTS ====================
    path('pac/traitements/', views.traitement_list, name='traitement_list'),
    path('pac/traitements/create/', views.traitement_create, name='traitement_create'),
    path('pac/traitements/<uuid:uuid>/', views.traitement_detail, name='traitement_detail'),
    path('pac/traitements/<uuid:uuid>/update/', views.traitement_update, name='traitement_update'),
    path('pac/<uuid:uuid>/traitements/', views.pac_traitements, name='pac_traitements'),
    
    # ==================== API SUIVIS ====================
    path('pac/suivis/', views.suivi_list, name='suivi_list'),
    path('pac/suivis/create/', views.suivi_create, name='suivi_create'),
    path('pac/suivis/<uuid:uuid>/', views.suivi_detail, name='suivi_detail'),
    path('pac/suivis/<uuid:uuid>/update/', views.suivi_update, name='suivi_update'),
    path('pac/traitements/<uuid:uuid>/suivis/', views.traitement_suivis, name='traitement_suivis'),
    
    # ==================== API DETAILS PAC ====================
    path('pac/<uuid:uuid>/details/', views.details_pac_list, name='details_pac_list'),
    path('pac/details/create/', views.details_pac_create, name='details_pac_create'),
    path('pac/details/<uuid:uuid>/', views.details_pac_detail, name='details_pac_detail'),
    path('pac/details/<uuid:uuid>/update/', views.details_pac_update, name='details_pac_update'),
    path('pac/details/<uuid:uuid>/delete/', views.details_pac_delete, name='details_pac_delete'),
    
    # ==================== STATISTIQUES PAC ====================
    path('pac/stats/', views.pac_stats, name='pac_stats'),

    # ==================== COPIE ANNÉE PRÉCÉDENTE ====================
    path('pac/last-previous-year/', views.get_last_pac_previous_year, name='get_last_pac_previous_year'),

    # ==================== NOTIFICATIONS ====================
    path('pac/upcoming-notifications/', views.pac_upcoming_notifications, name='pac_upcoming_notifications'),
]
