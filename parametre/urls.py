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
    # Endpoints pour les formulaires (éléments actifs uniquement)
    path('natures/', views.natures_list, name='natures_list'),
    path('categories/', views.categories_list, name='categories_list'),
    path('sources/', views.sources_list, name='sources_list'),
    path('action-types/', views.action_types_list, name='action_types_list'),
    path('statuts/', views.statuts_list, name='statuts_list'),
    path('etats-mise-en-oeuvre/', views.etats_mise_en_oeuvre_list, name='etats_mise_en_oeuvre_list'),
    path('appreciations/', views.appreciations_list, name='appreciations_list'),
    
    # Endpoints pour l'affichage des données existantes (tous les éléments)
    path('natures/all/', views.natures_all_list, name='natures_all_list'),
    path('categories/all/', views.categories_all_list, name='categories_all_list'),
    path('sources/all/', views.sources_all_list, name='sources_all_list'),
    path('action-types/all/', views.action_types_all_list, name='action_types_all_list'),
    path('statuts/all/', views.statuts_all_list, name='statuts_all_list'),
    path('etats-mise-en-oeuvre/all/', views.etats_mise_en_oeuvre_all_list, name='etats_mise_en_oeuvre_all_list'),
    path('appreciations/all/', views.appreciations_all_list, name='appreciations_all_list'),
    path('appreciations/create/', views.appreciation_create, name='appreciation_create'),
    path('appreciations/<uuid:uuid>/update/', views.appreciation_update, name='appreciation_update'),
    path('appreciations/<uuid:uuid>/delete/', views.appreciation_delete, name='appreciation_delete'),
    
    path('categories/', views.categories_list, name='categories_list'),
    path('categories/create/', views.categorie_create, name='categorie_create'),
    path('categories/<uuid:uuid>/update/', views.categorie_update, name='categorie_update'),
    path('categories/<uuid:uuid>/delete/', views.categorie_delete, name='categorie_delete'),
    
    path('directions/', views.directions_list, name='directions_list'),
    path('directions/all/', views.directions_all_list, name='directions_all_list'),
    path('directions/create/', views.direction_create, name='direction_create'),
    path('directions/<uuid:uuid>/update/', views.direction_update, name='direction_update'),
    path('directions/<uuid:uuid>/delete/', views.direction_delete, name='direction_delete'),
    
    path('sous-directions/', views.sous_directions_list, name='sous_directions_list'),
    path('sous-directions/all/', views.sous_directions_all_list, name='sous_directions_all_list'),
    path('sous-directions/create/', views.sous_direction_create, name='sous_direction_create'),
    path('sous-directions/<uuid:uuid>/update/', views.sous_direction_update, name='sous_direction_update'),
    path('sous-directions/<uuid:uuid>/delete/', views.sous_direction_delete, name='sous_direction_delete'),
    
    path('action-types/', views.action_types_list, name='action_types_list'),
    path('action-types/create/', views.action_type_create, name='action_type_create'),
    path('action-types/<uuid:uuid>/update/', views.action_type_update, name='action_type_update'),
    path('action-types/<uuid:uuid>/delete/', views.action_type_delete, name='action_type_delete'),
    
    path('services/', views.services_list, name='services_list'),
    path('services/all/', views.services_all_list, name='services_all_list'),
    path('processus/', views.processus_list, name='processus_list'),
    path('processus/all/', views.processus_all_list, name='processus_all_list'),
    path('dysfonctionnements/', views.dysfonctionnements_list, name='dysfonctionnements_list'),
    path('dysfonctionnements/all/', views.dysfonctionnements_all_list, name='dysfonctionnements_all_list'),

    # ==================== NOTIFICATION SETTINGS ====================
    path('notification-settings/', views.notification_settings_get, name='notification_settings_get'),
    path('notification-settings/update/', views.notification_settings_update, name='notification_settings_update'),
    path('notification-settings/effective/', views.notification_settings_effective, name='notification_settings_effective'),
    
    # ==================== DASHBOARD NOTIFICATION SETTINGS ====================
    path('dashboard-notification-settings/', views.dashboard_notification_settings_get, name='dashboard_notification_settings_get'),
    path('dashboard-notification-settings/update/', views.dashboard_notification_settings_update, name='dashboard_notification_settings_update'),
    
    
    # ==================== UPCOMING NOTIFICATIONS ====================
    path('upcoming-notifications/', views.upcoming_notifications, name='upcoming_notifications'),
    
    # ==================== EMAIL SETTINGS ====================
    path('email-settings/', views.email_settings_detail, name='email_settings_detail'),
    path('email-settings/update/', views.email_settings_update, name='email_settings_update'),
    path('email-settings/test/', views.test_email_configuration, name='test_email_configuration'),
    
    # ==================== MEDIAS ====================
    path('medias/create/', views.media_create, name='media_create'),
    path('medias/', views.media_list, name='media_list'),

    # ==================== PREUVES ====================
    path('preuves/create-with-medias/', views.preuve_create_with_medias, name='preuve_create_with_medias'),
    path('preuves/', views.preuves_list, name='preuves_list'),
    
    # ==================== FRÉQUENCES ====================
    path('frequences/', views.frequences_list, name='frequences_list'),
    
    # ==================== PÉRIODICITÉS ====================
    path('periodicites/', views.periodicites_list, name='periodicites_list'),
    
    # ==================== ANNÉES ====================
    path('annees/', views.annees_list, name='annees_list'),
    path('annees/all/', views.annees_all_list, name='annees_all_list'),
    
    # ==================== TYPES DE TABLEAU ====================
    path('types-tableau/', views.types_tableau_list, name='types_tableau_list'),
    path('types-tableau/all/', views.types_tableau_all_list, name='types_tableau_all_list'),
]
