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
    
    # ==================== API PAC ====================
    path('pac/', views.pac_list, name='pac_list'),
    path('pac/create/', views.pac_create, name='pac_create'),
    path('pac/<uuid:uuid>/', views.pac_detail, name='pac_detail'),
    path('pac/<uuid:uuid>/update/', views.pac_update, name='pac_update'),
    
    # ==================== API TRAITEMENTS ====================
    path('pac/traitements/', views.traitement_list, name='traitement_list'),
    path('pac/traitements/create/', views.traitement_create, name='traitement_create'),
    path('pac/traitements/<uuid:uuid>/', views.traitement_detail, name='traitement_detail'),
    path('pac/traitements/<uuid:uuid>/update/', views.traitement_update, name='traitement_update'),
    path('pac/<uuid:uuid>/traitements/', views.pac_traitements, name='pac_traitements'),
    
    # ==================== API SUIVIS ====================
    path('pac/suivis/', views.suivi_list, name='suivi_list'),
    path('pac/suivis/create/', views.suivi_create, name='suivi_create'),
]
