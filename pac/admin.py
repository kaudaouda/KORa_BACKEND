from django.contrib import admin
from django.contrib.auth.models import User
from .models import Pac, TraitementPac, PacSuivi, DetailsPac
from parametre.models import Processus

# Utilisation de l'admin User par défaut de Django


# L'admin Processus est maintenant géré dans l'app parametre


@admin.register(Pac)
class PacAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'processus', 'annee', 'type_tableau', 'is_validated', 'cree_par', 'validated_by', 'validated_at')
    list_filter = ('annee', 'type_tableau', 'processus', 'is_validated', 'cree_par', 'validated_by')
    search_fields = ('uuid', 'processus__nom', 'cree_par__username', 'cree_par__email', 'validated_by__username')
    readonly_fields = ('uuid',)
    raw_id_fields = ('processus', 'annee', 'type_tableau', 'cree_par', 'validated_by')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'processus')
        }),
        ('Classification', {
            'fields': ('annee', 'type_tableau')
        }),
        ('Validation', {
            'fields': ('is_validated', 'validated_at', 'validated_by')
        }),
        ('Utilisateurs', {
            'fields': ('cree_par',)
        }),
    )




@admin.register(TraitementPac)
class TraitementPacAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'details_pac', 'action', 'type_action', 'delai_realisation')
    list_filter = ('type_action', 'delai_realisation', 'details_pac__pac__processus')
    search_fields = ('action', 'details_pac__libelle', 'details_pac__numero_pac', 'details_pac__pac__uuid')
    readonly_fields = ('uuid',)
    raw_id_fields = ('details_pac', 'type_action', 'preuve')
    # OneToOneField : on ne peut avoir qu'un seul traitement par détail


@admin.register(PacSuivi)
class PacSuiviAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'traitement', 'etat_mise_en_oeuvre', 'appreciation', 'cree_par', 'created_at')
    list_filter = ('etat_mise_en_oeuvre', 'appreciation', 'cree_par', 'created_at')
    search_fields = ('resultat', 'traitement__action', 'cree_par__username', 'cree_par__email')
    readonly_fields = ('uuid', 'created_at')
    raw_id_fields = ('traitement', 'etat_mise_en_oeuvre', 'appreciation', 'cree_par')
    # OneToOneField : on ne peut avoir qu'un seul suivi par traitement


@admin.register(DetailsPac)
class DetailsPacAdmin(admin.ModelAdmin):
    list_display = ('numero_pac', 'uuid', 'pac', 'libelle', 'nature', 'categorie', 'source', 'periode_de_realisation')
    list_filter = ('nature', 'categorie', 'source', 'periode_de_realisation', 'pac__processus')
    search_fields = ('numero_pac', 'libelle', 'pac__uuid', 'dysfonctionnement_recommandation__nom', 'nature__nom', 'categorie__nom', 'source__nom')
    readonly_fields = ('uuid', 'numero_pac')
    raw_id_fields = ('pac', 'dysfonctionnement_recommandation', 'nature', 'categorie', 'source')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'numero_pac', 'pac')
        }),
        ('Détails', {
            'fields': ('libelle', 'dysfonctionnement_recommandation')
        }),
        ('Classification', {
            'fields': ('nature', 'categorie', 'source')
        }),
        ('Période', {
            'fields': ('periode_de_realisation',)
        }),
    )