"""
URLs pour l'application Dashboard
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== API OBJECTIFS ====================
    path('objectives/', views.objectives_list, name='objectives_list'),
    path('objectives/create/', views.objectives_create, name='objectives_create'),
    path('objectives/<uuid:uuid>/', views.objectives_detail, name='objectives_detail'),
    path('objectives/<uuid:uuid>/update/', views.objectives_update, name='objectives_update'),
    path('objectives/<uuid:uuid>/delete/', views.objectives_delete, name='objectives_delete'),
    path('objectives/<uuid:objective_uuid>/indicateurs/', views.objectives_indicateurs, name='objectives_indicateurs'),
    
    # ==================== API INDICATEURS ====================
    path('indicateurs/', views.indicateurs_list, name='indicateurs_list'),
    path('indicateurs/create/', views.indicateurs_create, name='indicateurs_create'),
    path('indicateurs/<uuid:uuid>/', views.indicateurs_detail, name='indicateurs_detail'),
    path('indicateurs/<uuid:uuid>/update/', views.indicateurs_update, name='indicateurs_update'),
    path('indicateurs/<uuid:uuid>/delete/', views.indicateurs_delete, name='indicateurs_delete'),
    
    # ==================== API CIBLES ====================
    path('cibles/', views.cibles_list, name='cibles_list'),
    path('cibles/create/', views.cibles_create, name='cibles_create'),
    path('cibles/<uuid:uuid>/', views.cibles_detail, name='cibles_detail'),
    path('cibles/<uuid:uuid>/update/', views.cibles_update, name='cibles_update'),
    path('cibles/<uuid:uuid>/delete/', views.cibles_delete, name='cibles_delete'),
    path('cibles/indicateur/<uuid:indicateur_uuid>/', views.cibles_by_indicateur, name='cibles_by_indicateur'),
    
    # ==================== API PERIODICITES ====================
    path('periodicites/', views.periodicites_list, name='periodicites_list'),
    path('periodicites/create/', views.periodicites_create, name='periodicites_create'),
    path('periodicites/<uuid:uuid>/', views.periodicites_detail, name='periodicites_detail'),
    path('periodicites/<uuid:uuid>/update/', views.periodicites_update, name='periodicites_update'),
    path('periodicites/<uuid:uuid>/delete/', views.periodicites_delete, name='periodicites_delete'),
    path('periodicites/indicateur/<uuid:indicateur_uuid>/', views.periodicites_by_indicateur, name='periodicites_by_indicateur'),
    
    # ==================== API OBSERVATIONS ====================
    path('observations/', views.observations_list, name='observations_list'),
    path('observations/create/', views.observations_create, name='observations_create'),
    path('observations/<uuid:uuid>/', views.observations_detail, name='observations_detail'),
    path('observations/<uuid:uuid>/update/', views.observations_update, name='observations_update'),
    path('observations/<uuid:uuid>/delete/', views.observations_delete, name='observations_delete'),
    path('observations/indicateur/<uuid:indicateur_uuid>/', views.observations_by_indicateur, name='observations_by_indicateur'),
    
    # ==================== STATISTIQUES ====================
    path('stats/', views.dashboard_stats, name='dashboard_stats'),

    # ==================== TABLEAUX DE BORD ====================
    path('tableaux-bord/', views.tableaux_bord_list_create, name='tableaux_bord_list_create'),
    path('tableaux-bord/<uuid:uuid>/', views.tableau_bord_detail, name='tableau_bord_detail'),
    path('tableaux-bord/<uuid:uuid>/objectives/', views.tableau_bord_objectives, name='tableau_bord_objectives'),
    path('tableaux-bord/<uuid:uuid>/validate/', views.validate_tableau_bord, name='validate_tableau_bord'),
    path('tableaux-bord/<uuid:tableau_initial_uuid>/amendements/', views.create_amendement, name='create_amendement'),
    path('tableaux-bord/<uuid:tableau_initial_uuid>/amendements/list/', views.get_amendements_by_initial, name='get_amendements_by_initial'),
]
