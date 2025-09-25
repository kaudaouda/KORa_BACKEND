"""
URLs pour l'application Paramètre
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== NATURES ====================
    path('natures/', views.nature_list, name='nature_list'),
    path('natures/create/', views.nature_create, name='nature_create'),
    path('natures/<uuid:uuid>/', views.nature_detail, name='nature_detail'),
    
    # ==================== CATÉGORIES ====================
    path('categories/', views.categorie_list, name='categorie_list'),
    path('categories/create/', views.categorie_create, name='categorie_create'),
    path('categories/<uuid:uuid>/', views.categorie_detail, name='categorie_detail'),
    
    # ==================== SOURCES ====================
    path('sources/', views.source_list, name='source_list'),
    path('sources/create/', views.source_create, name='source_create'),
    path('sources/<uuid:uuid>/', views.source_detail, name='source_detail'),
    
    # ==================== TYPES D'ACTION ====================
    path('action-types/', views.action_type_list, name='action_type_list'),
    path('action-types/create/', views.action_type_create, name='action_type_create'),
    path('action-types/<uuid:uuid>/', views.action_type_detail, name='action_type_detail'),
    
    # ==================== STATUTS ====================
    path('statuts/', views.statut_list, name='statut_list'),
    path('statuts/create/', views.statut_create, name='statut_create'),
    path('statuts/<uuid:uuid>/', views.statut_detail, name='statut_detail'),
    
    # ==================== ÉTATS DE MISE EN ŒUVRE ====================
    path('etat-mise-en-oeuvres/', views.etat_mise_en_oeuvre_list, name='etat_mise_en_oeuvre_list'),
    path('etat-mise-en-oeuvres/create/', views.etat_mise_en_oeuvre_create, name='etat_mise_en_oeuvre_create'),
    path('etat-mise-en-oeuvres/<uuid:uuid>/', views.etat_mise_en_oeuvre_detail, name='etat_mise_en_oeuvre_detail'),
    
    # ==================== APPRÉCIATIONS ====================
    path('appreciations/', views.appreciation_list, name='appreciation_list'),
    path('appreciations/create/', views.appreciation_create, name='appreciation_create'),
    path('appreciations/<uuid:uuid>/', views.appreciation_detail, name='appreciation_detail'),
    
    # ==================== DIRECTIONS ====================
    path('directions/', views.direction_list, name='direction_list'),
    path('directions/create/', views.direction_create, name='direction_create'),
    path('directions/<uuid:uuid>/', views.direction_detail, name='direction_detail'),
    path('directions/<uuid:uuid>/sous-directions/', views.sous_direction_list, name='sous_direction_list'),
]
