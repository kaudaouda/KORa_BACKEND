from django.urls import path

from . import views


urlpatterns = [
    # POST /api/analyse-tableau/lignes/from-tableau/ (route spécifique en premier)
    path(
        'lignes/from-tableau/',
        views.create_ligne_from_tableau,
        name='analyse_ligne_from_tableau',
    ),
    # PATCH /api/analyse-tableau/lignes/<uuid>/ (mise à jour d'une ligne)
    path(
        'lignes/<uuid:ligne_uuid>/',
        views.update_ligne,
        name='analyse_ligne_update',
    ),
    # POST /api/analyse-tableau/actions/ (créer une action)
    path(
        'actions/',
        views.create_action,
        name='analyse_action_create',
    ),
    # PATCH /api/analyse-tableau/actions/<uuid>/ (mise à jour d'une action)
    path(
        'actions/<uuid:action_uuid>/',
        views.update_action,
        name='analyse_action_update',
    ),
    # DELETE /api/analyse-tableau/actions/<uuid>/ (supprimer une action)
    path(
        'actions/<uuid:action_uuid>/delete/',
        views.delete_action,
        name='analyse_action_delete',
    ),
    # GET /api/analyse-tableau/par-tableau/<uuid>/ (route avec paramètre)
    path(
        'par-tableau/<uuid:tableau_uuid>/',
        views.get_analyse_by_tableau,
        name='analyse_tableau_by_tableau',
    ),
    # POST /api/analyse-tableau/ (route racine en dernier)
    path(
        '',
        views.create_analyse_tableau,
        name='analyse_tableau_create',
    ),
]

