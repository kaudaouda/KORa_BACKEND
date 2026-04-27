"""
URLs pour l'application Paramètre
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== ACTIVITÉS ====================
    path('activities/recent/', views.recent_activities, name='recent_activities'),
    path('activities/user/', views.user_activities, name='user_activities'),
    path('admin/email-logs/', views.admin_email_logs, name='admin_email_logs'),
    path('admin/notifications/', views.admin_notifications_list, name='admin_notifications_list'),
    
    # ==================== PARAMÈTRES ====================
    # Endpoints pour les formulaires (éléments actifs uniquement)
    path('natures/', views.natures_list, name='natures_list'),
    path('categories/', views.categories_list, name='categories_list'),
    path('sources/', views.sources_list, name='sources_list'),
    path('action-types/', views.action_types_list, name='action_types_list'),
    path('statuts/', views.statuts_list, name='statuts_list'),
    path('etats-mise-en-oeuvre/', views.etats_mise_en_oeuvre_list, name='etats_mise_en_oeuvre_list'),
    path('appreciations/', views.appreciations_list, name='appreciations_list'),
    path('statuts-action-cdr/', views.statuts_action_cdr_list, name='statuts_action_cdr_list'),
    path('statuts-action-cdr/all/', views.statuts_action_cdr_all_list, name='statuts_action_cdr_all_list'),
    path('statuts-action-cdr/create/', views.statut_action_cdr_create, name='statut_action_cdr_create'),
    path('statuts-action-cdr/<uuid:uuid>/update/', views.statut_action_cdr_update, name='statut_action_cdr_update'),
    path('statuts-action-cdr/<uuid:uuid>/delete/', views.statut_action_cdr_delete, name='statut_action_cdr_delete'),

    path('types-document/', views.types_document_list, name='types_document_list'),
    path('types-document/all/', views.types_document_all_list, name='types_document_all_list'),
    path('types-document/create/', views.type_document_create, name='type_document_create'),
    path('types-document/<uuid:uuid>/update/', views.type_document_update, name='type_document_update'),
    path('types-document/<uuid:uuid>/delete/', views.type_document_delete, name='type_document_delete'),
    
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
    path('services/create/', views.service_create, name='service_create'),
    path('services/<uuid:uuid>/update/', views.service_update, name='service_update'),
    path('services/<uuid:uuid>/delete/', views.service_delete, name='service_delete'),

    path('processus/', views.processus_list, name='processus_list'),
    path('processus/all/', views.processus_all_list, name='processus_all_list'),
    path('processus/create/', views.processus_create, name='processus_create'),
    path('processus/<uuid:uuid>/update/', views.processus_update, name='processus_update'),
    path('processus/<uuid:uuid>/delete/', views.processus_delete, name='processus_delete'),

    path('natures/create/', views.nature_create, name='nature_create'),
    path('natures/<uuid:uuid>/update/', views.nature_update, name='nature_update'),
    path('natures/<uuid:uuid>/delete/', views.nature_delete, name='nature_delete'),

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
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<uuid:uuid>/read/', views.notification_mark_read, name='notification_mark_read'),

    # ==================== EMAIL SETTINGS ====================
    path('email-settings/', views.email_settings_detail, name='email_settings_detail'),
    path('email-settings/update/', views.email_settings_update, name='email_settings_update'),
    path('email-settings/test/', views.test_email_configuration, name='test_email_configuration'),
    
    # ==================== MEDIAS ====================
    path('medias/create/', views.media_create, name='media_create'),
    path('medias/<uuid:uuid>/update-description/', views.media_update_description, name='media_update_description'),
    path('medias/', views.media_list, name='media_list'),

    # ==================== PREUVES ====================
    path('preuves/create-with-medias/', views.preuve_create_with_medias, name='preuve_create_with_medias'),
    path('preuves/<uuid:uuid>/add-medias/', views.preuve_add_medias, name='preuve_add_medias'),
    path('preuves/<uuid:uuid>/remove-media/<uuid:media_uuid>/', views.preuve_remove_media, name='preuve_remove_media'),
    path('preuves/', views.preuves_list, name='preuves_list'),
    
    # ==================== FRÉQUENCES ====================
    path('frequences/', views.frequences_list, name='frequences_list'),
    path('frequences/all/', views.frequences_all_list, name='frequences_all_list'),
    path('frequences/create/', views.frequence_create, name='frequence_create'),
    path('frequences/<uuid:uuid>/update/', views.frequence_update, name='frequence_update'),
    path('frequences/<uuid:uuid>/delete/', views.frequence_delete, name='frequence_delete'),

    # ==================== MOIS ====================
    path('mois/', views.mois_list, name='mois_list'),
    path('mois/create/', views.mois_create, name='mois_create'),
    path('mois/<uuid:uuid>/update/', views.mois_update, name='mois_update'),
    path('mois/<uuid:uuid>/delete/', views.mois_delete, name='mois_delete'),
    
    # ==================== PÉRIODICITÉS ====================
    path('periodicites/', views.periodicites_list, name='periodicites_list'),
    
    # ==================== ANNÉES ====================
    path('annees/', views.annees_list, name='annees_list'),
    path('annees/all/', views.annees_all_list, name='annees_all_list'),
    path('annees/create/', views.annee_create, name='annee_create'),
    path('annees/<uuid:uuid>/update/', views.annee_update, name='annee_update'),
    path('annees/<uuid:uuid>/delete/', views.annee_delete, name='annee_delete'),
    
    # ==================== DYSFONCTIONNEMENTS/RECOMMANDATIONS ====================
    path('dysfonctionnements/create/', views.dysfonctionnement_create, name='dysfonctionnement_create'),
    path('dysfonctionnements/<uuid:uuid>/update/', views.dysfonctionnement_update, name='dysfonctionnement_update'),
    path('dysfonctionnements/<uuid:uuid>/delete/', views.dysfonctionnement_delete, name='dysfonctionnement_delete'),

    # ==================== CARTOGRAPHIE DES RISQUES ====================
    path('frequences-risque/', views.frequences_risque_list, name='frequences_risque_list'),
    path('frequences-risque/all/', views.frequences_risque_all_list, name='frequences_risque_all_list'),
    path('frequences-risque/create/', views.frequence_risque_create, name='frequence_risque_create'),
    path('frequences-risque/<uuid:uuid>/update/', views.frequence_risque_update, name='frequence_risque_update'),
    path('frequences-risque/<uuid:uuid>/delete/', views.frequence_risque_delete, name='frequence_risque_delete'),
    path('gravites-risque/', views.gravites_risque_list, name='gravites_risque_list'),
    path('gravites-risque/all/', views.gravites_risque_all_list, name='gravites_risque_all_list'),
    path('gravites-risque/create/', views.gravite_risque_create, name='gravite_risque_create'),
    path('gravites-risque/<uuid:uuid>/update/', views.gravite_risque_update, name='gravite_risque_update'),
    path('gravites-risque/<uuid:uuid>/delete/', views.gravite_risque_delete, name='gravite_risque_delete'),
    path('criticites-risque/', views.criticités_risque_list, name='criticites_risque_list'),
    path('criticites-risque/all/', views.criticites_all_list, name='criticites_all_list'),
    path('criticites-risque/create/', views.criticite_create, name='criticite_create'),
    path('criticites-risque/<uuid:uuid>/update/', views.criticite_update, name='criticite_update'),
    path('criticites-risque/<uuid:uuid>/delete/', views.criticite_delete, name='criticite_delete'),
    path('risques/', views.risques_list, name='risques_list'),
    path('risques/all/', views.risques_all_list, name='risques_all_list'),
    path('risques/create/', views.risque_create, name='risque_create'),
    path('risques/<uuid:uuid>/update/', views.risque_update, name='risque_update'),
    path('risques/<uuid:uuid>/delete/', views.risque_delete, name='risque_delete'),
    
    # ==================== SYSTÈME DE RÔLES ====================
    path('roles/', views.roles_list, name='roles_list'),
    path('roles/all/', views.roles_all_list, name='roles_all_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<uuid:uuid>/update/', views.role_update, name='role_update'),
    path('roles/<uuid:uuid>/delete/', views.role_delete, name='role_delete'),
    
    # ==================== USER PROCESSUS ====================
    path('user-processus/', views.user_processus_list, name='user_processus_list'),
    path('user-processus/create/', views.user_processus_create, name='user_processus_create'),
    path('user-processus/<uuid:uuid>/update/', views.user_processus_update, name='user_processus_update'),
    path('user-processus/<uuid:uuid>/delete/', views.user_processus_delete, name='user_processus_delete'),
    path('admin/user-processus/', views.admin_get_user_processus, name='admin_get_user_processus'),
    
    # ==================== USER PROCESSUS ROLE ====================
    path('user-processus-role/', views.user_processus_role_list, name='user_processus_role_list'),
    path('user-processus-role/create/', views.user_processus_role_create, name='user_processus_role_create'),
    path('user-processus-role/<uuid:uuid>/update/', views.user_processus_role_update, name='user_processus_role_update'),
    path('user-processus-role/<uuid:uuid>/delete/', views.user_processus_role_delete, name='user_processus_role_delete'),
    
    # ==================== GESTION DES UTILISATEURS ====================
    path('users/', views.users_list, name='users_list'),
    path('users/create/', views.users_create, name='users_create'),
    path('users/invite/', views.users_invite, name='users_invite'),

    # ==================== APPLICATION CONFIG ====================
    path('application-configs/', views.application_config_list, name='application_config_list'),
    path('application-configs/<str:app_name>/toggle/', views.application_config_toggle, name='application_config_toggle'),
    path('app-status/', views.app_status, name='app_status'),
    path('app-status/stream/', views.app_status_stream, name='app_status_stream'),
]
