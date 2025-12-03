from django.contrib import admin
from django.contrib.auth.models import User
from .models import ActivitePeriodique, DetailsAP, SuivisAP


@admin.register(ActivitePeriodique)
class ActivitePeriodiqueAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'processus', 'annee', 'type_tableau', 'is_validated', 'cree_par', 'validated_by', 'validated_at')
    list_filter = ('annee', 'type_tableau', 'processus', 'is_validated', 'cree_par', 'validated_by')
    search_fields = ('uuid', 'processus__nom', 'cree_par__username', 'cree_par__email', 'validated_by__username')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    raw_id_fields = ('processus', 'annee', 'type_tableau', 'cree_par', 'validated_by', 'initial_ref')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'processus')
        }),
        ('Classification', {
            'fields': ('annee', 'type_tableau', 'initial_ref')
        }),
        ('Validation', {
            'fields': ('is_validated', 'validated_at', 'validated_by')
        }),
        ('Utilisateurs', {
            'fields': ('cree_par',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(DetailsAP)
class DetailsAPAdmin(admin.ModelAdmin):
    list_display = ('numero_ap', 'uuid', 'activite_periodique', 'frequence')
    list_filter = ('activite_periodique__processus', 'activite_periodique__annee', 'frequence')
    search_fields = ('numero_ap', 'uuid', 'activites_periodiques', 'activite_periodique__uuid', 'frequence__nom')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    raw_id_fields = ('activite_periodique', 'frequence')
    filter_horizontal = ('responsables_directions', 'responsables_sous_directions', 'responsables_services')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'numero_ap', 'activite_periodique')
        }),
        ('Activités périodiques', {
            'fields': ('activites_periodiques', 'frequence')
        }),
        ('Responsabilités', {
            'fields': ('responsables_directions', 'responsables_sous_directions', 'responsables_services')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(SuivisAP)
class SuivisAPAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'details_ap', 'mois', 'etat_mise_en_oeuvre', 'date_realisation', 'created_at')
    list_filter = ('mois__numero', 'etat_mise_en_oeuvre', 'details_ap__activite_periodique__processus')
    search_fields = ('details_ap__numero_ap', 'mois__nom', 'etat_mise_en_oeuvre__nom', 'livrable')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    raw_id_fields = ('details_ap', 'mois', 'etat_mise_en_oeuvre')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'details_ap', 'mois')
        }),
        ('Suivi', {
            'fields': ('etat_mise_en_oeuvre', 'livrable', 'date_realisation')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at')
        }),
    )
