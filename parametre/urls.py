"""
URLs pour l'application Paramètre
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== ACTIVITÉS ====================
    path('activities/recent/', views.recent_activities, name='recent_activities'),
    path('activities/user/', views.user_activities, name='user_activities'),
    
    # ==================== PARAMÈTRES ====================
    path('natures/', views.natures_list, name='natures_list'),
    path('categories/', views.categories_list, name='categories_list'),
    path('sources/', views.sources_list, name='sources_list'),
    path('action-types/', views.action_types_list, name='action_types_list'),
    path('statuts/', views.statuts_list, name='statuts_list'),
    path('etats-mise-en-oeuvre/', views.etats_mise_en_oeuvre_list, name='etats_mise_en_oeuvre_list'),
    path('appreciations/', views.appreciations_list, name='appreciations_list'),
    path('appreciations/create/', views.appreciation_create, name='appreciation_create'),
    path('appreciations/<uuid:uuid>/update/', views.appreciation_update, name='appreciation_update'),
    path('appreciations/<uuid:uuid>/delete/', views.appreciation_delete, name='appreciation_delete'),
    
    path('categories/', views.categories_list, name='categories_list'),
    path('categories/create/', views.categorie_create, name='categorie_create'),
    path('categories/<uuid:uuid>/update/', views.categorie_update, name='categorie_update'),
    path('categories/<uuid:uuid>/delete/', views.categorie_delete, name='categorie_delete'),
    
    path('directions/', views.directions_list, name='directions_list'),
    path('directions/create/', views.direction_create, name='direction_create'),
    path('directions/<uuid:uuid>/update/', views.direction_update, name='direction_update'),
    path('directions/<uuid:uuid>/delete/', views.direction_delete, name='direction_delete'),
    
    path('sous-directions/', views.sous_directions_list, name='sous_directions_list'),
    path('sous-directions/create/', views.sous_direction_create, name='sous_direction_create'),
    path('sous-directions/<uuid:uuid>/update/', views.sous_direction_update, name='sous_direction_update'),
    path('sous-directions/<uuid:uuid>/delete/', views.sous_direction_delete, name='sous_direction_delete'),
    
    path('action-types/', views.action_types_list, name='action_types_list'),
    path('action-types/create/', views.action_type_create, name='action_type_create'),
    path('action-types/<uuid:uuid>/update/', views.action_type_update, name='action_type_update'),
    path('action-types/<uuid:uuid>/delete/', views.action_type_delete, name='action_type_delete'),
    
    path('services/', views.services_list, name='services_list'),
    path('processus/', views.processus_list, name='processus_list'),

    # ==================== NOTIFICATION SETTINGS ====================
    path('notification-settings/', views.notification_settings_get, name='notification_settings_get'),
    path('notification-settings/update/', views.notification_settings_update, name='notification_settings_update'),
    path('notification-settings/effective/', views.notification_settings_effective, name='notification_settings_effective'),
    
    
    # ==================== UPCOMING NOTIFICATIONS ====================
    path('upcoming-notifications/', views.upcoming_notifications, name='upcoming_notifications'),
]
