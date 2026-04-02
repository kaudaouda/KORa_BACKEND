"""
URLs pour l'application Activité Périodique
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== API ACTIVITE PERIODIQUE ====================
    path('', views.activite_periodique_home, name='activite_periodique_home'),
    
    # Activités Périodiques endpoints
    path('activites-periodiques/', views.activites_periodiques_list, name='activites_periodiques_list'),
    path('activites-periodiques/get-or-create/', views.activite_periodique_get_or_create, name='activite_periodique_get_or_create'),
    path('activites-periodiques/last-previous-year/', views.get_last_ap_previous_year, name='get_last_ap_previous_year'),
    path('activites-periodiques/stats/', views.activite_periodique_stats, name='activite_periodique_stats'),
    path('activites-periodiques/create/', views.activite_periodique_create, name='activite_periodique_create'),
    path('activites-periodiques/<uuid:uuid>/', views.activite_periodique_detail, name='activite_periodique_detail'),
    path('activites-periodiques/<uuid:uuid>/update/', views.activite_periodique_update, name='activite_periodique_update'),
    path('activites-periodiques/<uuid:uuid>/delete/', views.activite_periodique_delete, name='activite_periodique_delete'),
    path('activites-periodiques/<uuid:uuid>/validate/', views.activite_periodique_validate, name='activite_periodique_validate'),
    path('activites-periodiques/<uuid:uuid>/unvalidate/', views.activite_periodique_unvalidate, name='activite_periodique_unvalidate'),
    
    # Details AP endpoints
    path('details-ap/', views.details_ap_list, name='details_ap_list'),
    path('details-ap/activite-periodique/<uuid:ap_uuid>/', views.details_ap_by_activite_periodique, name='details_ap_by_activite_periodique'),
    path('details-ap/create/', views.details_ap_create, name='details_ap_create'),
    path('details-ap/<uuid:uuid>/update/', views.details_ap_update, name='details_ap_update'),
    path('details-ap/<uuid:uuid>/delete/', views.details_ap_delete, name='details_ap_delete'),
    
    # Suivis AP endpoints
    path('suivis-ap/', views.suivis_ap_list, name='suivis_ap_list'),
    path('suivis-ap/detail-ap/<uuid:detail_ap_uuid>/', views.suivis_ap_by_detail_ap, name='suivis_ap_by_detail_ap'),
    path('suivis-ap/create/', views.suivi_ap_create, name='suivi_ap_create'),
    path('suivis-ap/<uuid:uuid>/update/', views.suivi_ap_update, name='suivi_ap_update'),
    path('suivis-ap/<uuid:uuid>/delete/', views.suivi_ap_delete, name='suivi_ap_delete'),
    
    # MediaLivrable endpoints
    path('media-livrables/suivi/<uuid:suivi_uuid>/', views.media_livrables_by_suivi, name='media_livrables_by_suivi'),
    path('media-livrables/create/', views.media_livrable_create, name='media_livrable_create'),
    path('media-livrables/<uuid:uuid>/update/', views.media_livrable_update, name='media_livrable_update'),
    path('media-livrables/<uuid:uuid>/delete/', views.media_livrable_delete, name='media_livrable_delete'),
]

