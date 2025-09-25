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
    path('auth/refresh/', views.refresh_token, name='refresh_token'),
    path('auth/recaptcha-config/', views.recaptcha_config, name='recaptcha_config'),
    
    # ==================== API PROCESSUS ====================
    path('pac/processus/', views.processus_list, name='processus_list'),
    path('pac/processus/create/', views.processus_create, name='processus_create'),
    path('pac/processus/<uuid:uuid>/', views.processus_detail, name='processus_detail'),
    
    # ==================== API PAC ====================
    path('pac/', views.pac_list, name='pac_list'),
    path('pac/create/', views.pac_create, name='pac_create'),
    path('pac/<uuid:uuid>/', views.pac_detail, name='pac_detail'),
    
    # ==================== API TRAITEMENTS ====================
    path('pac/traitements/', views.traitement_list, name='traitement_list'),
    path('pac/traitements/create/', views.traitement_create, name='traitement_create'),
    
    # ==================== API SUIVIS ====================
    path('pac/suivis/', views.suivi_list, name='suivi_list'),
    path('pac/suivis/create/', views.suivi_create, name='suivi_create'),
]
