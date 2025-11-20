from django.contrib import admin
from .models import CDR, DetailsCDR, EvaluationRisque, PlanAction, SuiviAction


@admin.register(CDR)
class CDRAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les CDR"""
    
    list_display = [
        'annee', 'processus', 'type_tableau', 'is_validated', 'valide_par', 'date_validation', 'cree_par', 'created_at'
    ]
    list_filter = [
        'annee', 'type_tableau', 'processus', 'is_validated', 'created_at'
    ]
    search_fields = [
        'processus__nom', 'processus__numero_processus', 'cree_par__username', 'raison_amendement'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 'date_validation', 'valide_par'
    ]
    ordering = ['-annee', 'processus__numero_processus', 'type_tableau']

    fieldsets = (
        ('Informations', {
            'fields': ('uuid', 'annee', 'processus', 'type_tableau')
        }),
        ('Amendement', {
            'fields': ('initial_ref', 'raison_amendement'),
            'description': 'Informations sur l\'amendement (si applicable)'
        }),
        ('Validation', {
            'fields': ('is_validated', 'date_validation', 'valide_par'),
            'description': 'État de validation de la cartographie'
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Sauvegarder le modèle avec l'utilisateur connecté"""
        if not change:
            obj.cree_par = request.user
        
        # Si la cartographie est validée et que ce n'était pas le cas avant
        if obj.is_validated and (not change or not form.initial.get('is_validated', False)):
            from django.utils import timezone
            obj.date_validation = timezone.now()
            obj.valide_par = request.user
        
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('processus', 'type_tableau', 'cree_par', 'valide_par')


@admin.register(DetailsCDR)
class DetailsCDRAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les détails CDR"""
    
    list_display = [
        'numero_cdr', 'cdr', 'evaluations_count', 'plans_action_count', 'created_at', 'updated_at'
    ]
    list_filter = [
        'cdr__annee', 'cdr__processus', 'created_at', 'updated_at'
    ]
    search_fields = [
        'numero_cdr', 'activites', 'objectifs', 'cdr__processus__nom'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['cdr', 'numero_cdr', 'created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'numero_cdr', 'cdr')
        }),
        ('Détails', {
            'fields': ('activites', 'objectifs', 'evenements_indesirables_risques', 'causes', 'consequences')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def evaluations_count(self, obj):
        """Afficher le nombre d'évaluations associées"""
        return obj.evaluations.count()
    evaluations_count.short_description = 'Nb Évaluations'
    
    def plans_action_count(self, obj):
        """Afficher le nombre de plans d'action associés"""
        return obj.plans_action.count()
    plans_action_count.short_description = 'Nb Plans d\'Action'
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('cdr', 'cdr__processus')


@admin.register(EvaluationRisque)
class EvaluationRisqueAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les évaluations de risque"""
    
    list_display = [
        'details_cdr', 'risque', 'frequence', 'gravite', 'criticite', 'created_at', 'updated_at'
    ]
    list_filter = [
        'frequence', 'gravite', 'criticite', 'risque', 'created_at', 'updated_at'
    ]
    search_fields = [
        'details_cdr__numero_cdr', 'risque__libelle', 'details_cdr__cdr__processus__nom'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['details_cdr', 'created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'details_cdr')
        }),
        ('Évaluation', {
            'fields': ('frequence', 'gravite', 'criticite', 'risque')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'details_cdr', 'details_cdr__cdr', 'frequence', 'gravite', 'criticite', 'risque'
        )


@admin.register(PlanAction)
class PlanActionAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les plans d'action"""
    
    list_display = [
        'details_cdr', 'responsable', 'delai_realisation', 'suivis_count', 'created_at', 'updated_at'
    ]
    list_filter = [
        'delai_realisation', 'responsable', 'details_cdr__cdr__processus', 'created_at', 'updated_at'
    ]
    search_fields = [
        'actions_mesures', 'details_cdr__numero_cdr', 'responsable__username', 'responsable__email'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['details_cdr', 'delai_realisation', 'created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'details_cdr')
        }),
        ('Plan d\'action', {
            'fields': ('actions_mesures', 'responsable', 'delai_realisation')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def suivis_count(self, obj):
        """Afficher le nombre de suivis associés"""
        return obj.suivis.count()
    suivis_count.short_description = 'Nb Suivis'
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'details_cdr', 'details_cdr__cdr', 'responsable'
        )


@admin.register(SuiviAction)
class SuiviActionAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les suivis d'action"""
    
    list_display = [
        'plan_action', 'statut_action', 'date_realisation', 'date_cloture', 'created_at', 'updated_at'
    ]
    list_filter = [
        'statut_action', 'date_realisation', 'date_cloture', 'created_at', 'updated_at'
    ]
    search_fields = [
        'plan_action__actions_mesures', 'plan_action__details_cdr__numero_cdr',
        'critere_efficacite_objectif_vise', 'resultats_mise_en_oeuvre'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['plan_action', '-date_realisation', 'created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'plan_action')
        }),
        ('Suivi', {
            'fields': ('date_realisation', 'statut_action', 'date_cloture')
        }),
        ('Résultats', {
            'fields': ('element_preuve', 'critere_efficacite_objectif_vise', 'resultats_mise_en_oeuvre')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'plan_action', 'plan_action__details_cdr', 'plan_action__details_cdr__cdr', 'element_preuve'
        )

