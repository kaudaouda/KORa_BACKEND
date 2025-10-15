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
    
    # ==================== STATISTIQUES ====================
    path('stats/', views.dashboard_stats, name='dashboard_stats'),
]
