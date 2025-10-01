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
    path('directions/', views.directions_list, name='directions_list'),
    path('sous-directions/', views.sous_directions_list, name='sous_directions_list'),
    path('services/', views.services_list, name='services_list'),
    path('processus/', views.processus_list, name='processus_list'),
]
