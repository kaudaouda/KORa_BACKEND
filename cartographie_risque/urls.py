"""
URLs pour l'application Cartographie de Risque
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== API CARTographie DE RISQUE ====================
    path('', views.cartographie_risque_home, name='cartographie_risque_home'),
    
    # CDR endpoints
    path('cdrs/', views.cdr_list, name='cdr_list'),
    path('cdrs/get-or-create/', views.cdr_get_or_create, name='cdr_get_or_create'),
    path('cdrs/<uuid:uuid>/', views.cdr_detail, name='cdr_detail'),
    path('cdrs/<uuid:uuid>/validate/', views.validate_cdr, name='validate_cdr'),
    
    # Details CDR endpoints
    path('details-cdr/cdr/<uuid:cdr_uuid>/', views.details_cdr_by_cdr, name='details_cdr_by_cdr'),
    path('details-cdr/create/', views.details_cdr_create, name='details_cdr_create'),
    path('details-cdr/<uuid:uuid>/update/', views.details_cdr_update, name='details_cdr_update'),
    path('details-cdr/<uuid:uuid>/delete/', views.details_cdr_delete, name='details_cdr_delete'),
    
    # Evaluation Risque endpoints
    path('details-cdr/<uuid:detail_cdr_uuid>/evaluations/', views.evaluations_by_detail_cdr, name='evaluations_by_detail_cdr'),
    path('evaluations-risque/create/', views.evaluation_risque_create, name='evaluation_risque_create'),
    path('evaluations-risque/<uuid:uuid>/update/', views.evaluation_risque_update, name='evaluation_risque_update'),
    
    # Plan Action endpoints
    path('details-cdr/<uuid:detail_cdr_uuid>/plans-action/', views.plans_action_by_detail_cdr, name='plans_action_by_detail_cdr'),
    path('plans-action/create/', views.plan_action_create, name='plan_action_create'),
    path('plans-action/<uuid:uuid>/update/', views.plan_action_update, name='plan_action_update'),
    
    # Suivi Action endpoints
    path('plans-action/<uuid:plan_action_uuid>/suivis/', views.suivis_by_plan_action, name='suivis_by_plan_action'),
    path('suivis-action/<uuid:uuid>/', views.suivi_action_detail, name='suivi_action_detail'),
    path('suivis-action/create/', views.suivi_action_create, name='suivi_action_create'),
    path('suivis-action/<uuid:uuid>/update/', views.suivi_action_update, name='suivi_action_update'),

    # Versions d'évaluation CDR endpoints
    path('versions-evaluation/', views.versions_evaluation_list, name='versions_evaluation_list'),
    path('details-cdr/<uuid:detail_cdr_uuid>/create-reevaluation/', views.create_reevaluation, name='create_reevaluation'),

    # Copie depuis l'année précédente
    path('cdrs/last-previous-year/', views.get_last_cdr_previous_year, name='get_last_cdr_previous_year'),
]

