from django.contrib import admin
from django.contrib.auth.models import User
from .models import Pac, Traitement, Suivi
from parametre.models import Processus

# Utilisation de l'admin User par défaut de Django


# L'admin Processus est maintenant géré dans l'app parametre


@admin.register(Pac)
class PacAdmin(admin.ModelAdmin):
    list_display = ('numero_pac', 'libelle', 'processus', 'nature', 'categorie', 'source', 'cree_par', 'created_at')
    list_filter = ('nature', 'categorie', 'source', 'processus', 'cree_par', 'created_at')
    search_fields = ('numero_pac', 'libelle', 'processus__nom', 'cree_par__username', 'cree_par__email')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    raw_id_fields = ('processus', 'nature', 'categorie', 'source', 'cree_par')




@admin.register(Traitement)
class TraitementAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'pac', 'action', 'type_action', 'delai_realisation')
    list_filter = ('type_action', 'delai_realisation', 'pac__processus')
    search_fields = ('action', 'pac__numero_pac', 'pac__libelle')
    readonly_fields = ('uuid',)
    raw_id_fields = ('pac', 'type_action', 'preuve')


@admin.register(Suivi)
class SuiviAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'traitement', 'etat_mise_en_oeuvre', 'appreciation', 'cree_par', 'created_at')
    list_filter = ('etat_mise_en_oeuvre', 'appreciation', 'cree_par', 'created_at')
    search_fields = ('resultat', 'traitement__action', 'cree_par__username', 'cree_par__email')
    readonly_fields = ('uuid', 'created_at')
    raw_id_fields = ('traitement', 'etat_mise_en_oeuvre', 'appreciation', 'cree_par')