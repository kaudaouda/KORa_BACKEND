"""
URLs pour l'application Documentation
"""
from django.urls import path
from . import views

urlpatterns = [
    # ==================== API DOCUMENTS ====================
    path('documents/', views.document_list, name='document_list'),
    path('documents/active/', views.document_list_active, name='document_list_active'),
    path('documents/create/', views.document_create, name='document_create'),
    path('documents/<uuid:uuid>/', views.document_detail, name='document_detail'),
    path('documents/<uuid:uuid>/update/', views.document_update, name='document_update'),
    path('documents/<uuid:uuid>/delete/', views.document_delete, name='document_delete'),
    path('documents/<uuid:uuid>/amend/', views.document_amend, name='document_amend'),
    path('documents/<uuid:uuid>/version-chain/', views.document_version_chain, name='document_version_chain'),

    # ==================== API EDITIONS, AMENDEMENTS & CATEGORIES ====================
    path('editions/', views.editions_list, name='editions_list'),
    path('amendements/', views.amendements_list, name='amendements_list'),
    path('categories/', views.categories_list, name='categories_list'),
]
