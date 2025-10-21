from django.contrib import admin
from .models import Objectives, Indicateur, Observation, TableauBord


@admin.register(Objectives)
class ObjectivesAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les objectifs"""
    
    list_display = [
        'number', 'libelle', 'cree_par', 'indicateurs_count', 'created_at', 'updated_at'
    ]
    list_filter = [
        'created_at', 'updated_at', 'cree_par'
    ]
    search_fields = [
        'number', 'libelle', 'cree_par__username', 'cree_par__first_name', 'cree_par__last_name'
    ]
    readonly_fields = [
        'uuid', 'number', 'created_at', 'updated_at'
    ]
    ordering = ['number']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'number', 'libelle', 'tableau_bord')
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Rendre certains champs en lecture seule selon le contexte"""
        if obj:  # Modification d'un objet existant
            return self.readonly_fields + ['cree_par']
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        """Sauvegarder le modèle avec l'utilisateur connecté"""
        if not change:  # Création d'un nouvel objet
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)
    
    def indicateurs_count(self, obj):
        """Afficher le nombre d'indicateurs associés"""
        return obj.indicateurs.count()
    indicateurs_count.short_description = 'Nb Indicateurs'


@admin.register(Indicateur)
class IndicateurAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les indicateurs"""
    
    list_display = [
        'libelle', 'objective_id', 'frequence_id', 'created_at', 'updated_at'
    ]
    list_filter = [
        'objective_id', 'frequence_id', 'created_at', 'updated_at'
    ]
    search_fields = [
        'libelle', 'objective_id__number', 'objective_id__libelle', 'frequence_id__nom'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['objective_id', 'libelle']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'libelle', 'objective_id', 'frequence_id')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('objective_id', 'frequence_id')


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les observations"""
    
    list_display = [
        'indicateur_id', 'libelle', 'cree_par', 'created_at', 'updated_at'
    ]
    list_filter = [
        'created_at', 'updated_at', 'cree_par', 'indicateur_id__objective_id'
    ]
    search_fields = [
        'libelle', 'indicateur_id__libelle', 'indicateur_id__objective_id__number',
        'cree_par__username', 'cree_par__first_name', 'cree_par__last_name'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['indicateur_id__objective_id', 'created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'indicateur_id', 'libelle')
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Rendre certains champs en lecture seule selon le contexte"""
        if obj:  # Modification d'un objet existant
            return self.readonly_fields + ['cree_par', 'indicateur_id']
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        """Sauvegarder le modèle avec l'utilisateur connecté"""
        if not change:  # Création d'un nouvel objet
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'indicateur_id', 'indicateur_id__objective_id', 'cree_par'
        )


@admin.register(TableauBord)
class TableauBordAdmin(admin.ModelAdmin):
    """Administration pour Tableau de bord"""
    list_display = ['annee', 'processus', 'type_tableau', 'initial_ref', 'cree_par', 'created_at']
    list_filter = ['annee', 'type_tableau', 'processus', 'created_at']
    search_fields = ['processus__nom', 'processus__numero_processus']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    ordering = ['-annee', 'processus__numero_processus', 'type_tableau']
    fieldsets = (
        ('Informations', {
            'fields': ('uuid', 'annee', 'processus', 'type_tableau', 'initial_ref')
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)