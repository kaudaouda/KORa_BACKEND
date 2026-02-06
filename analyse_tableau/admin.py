from django.contrib import admin
from .models import AnalyseTableau, AnalyseLigne, AnalyseAction


class AnalyseActionInline(admin.TabularInline):
    model = AnalyseAction
    extra = 0


class AnalyseLigneInline(admin.TabularInline):
    model = AnalyseLigne
    extra = 0


@admin.register(AnalyseTableau)
class AnalyseTableauAdmin(admin.ModelAdmin):
    list_display = ('tableau_bord', 'cree_par', 'created_at', 'updated_at')
    search_fields = ('tableau_bord__processus__nom', 'cree_par__username')
    inlines = [AnalyseLigneInline]


@admin.register(AnalyseLigne)
class AnalyseLigneAdmin(admin.ModelAdmin):
    list_display = ('objectif_non_atteint', 'analyse_tableau', 'created_at')
    search_fields = ('objectif_non_atteint', 'causes')
    inlines = [AnalyseActionInline]


@admin.register(AnalyseAction)
class AnalyseActionAdmin(admin.ModelAdmin):
    list_display = ('action', 'ligne', 'delai_realisation', 'etat_mise_en_oeuvre')
    search_fields = ('action', 'commentaire')
