from django.contrib import admin
from django import forms
from django.http import JsonResponse
from django.urls import path
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import (
    Nature, Categorie, Source, ActionType, Statut,
    EtatMiseEnOeuvre, Appreciation, Media, Preuve, StatutActionCDR,
    Direction, SousDirection, Service, Processus,
    ActivityLog, NotificationSettings, DashboardNotificationSettings, EmailSettings, ReminderEmailLog,
    DysfonctionnementRecommandation, Mois, Frequence, Periodicite, Cible, Versions, Annee,
    FrequenceRisque, GraviteRisque, CriticiteRisque, Risque, VersionEvaluationCDR,
    TypeDocument, EditionDocument, AmendementDocument, MediaDocument,
    Role, UserProcessus, UserProcessusRole, ApplicationConfig
)


@admin.register(Nature)
class NatureAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(ActionType)
class ActionTypeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Statut)
class StatutAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(EtatMiseEnOeuvre)
class EtatMiseEnOeuvreAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Appreciation)
class AppreciationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(StatutActionCDR)
class StatutActionCDRAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    ordering = ('nom',)


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'url_fichier', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('url_fichier',)
    readonly_fields = ('uuid', 'created_at')


@admin.register(Preuve)
class PreuveAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'description', 'get_medias_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('description',)
    readonly_fields = ('uuid', 'created_at')
    filter_horizontal = ('medias',)

    def get_medias_count(self, obj):
        return obj.medias.count()
    get_medias_count.short_description = 'Nombre de médias'


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(SousDirection)
class SousDirectionAdmin(admin.ModelAdmin):
    list_display = ('nom', 'direction', 'description', 'is_active', 'created_at')
    list_filter = ('direction', 'is_active', 'created_at')
    search_fields = ('nom', 'description', 'direction__nom')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'sous_direction', 'description', 'is_active', 'created_at')
    list_filter = ('sous_direction__direction', 'sous_direction', 'is_active', 'created_at')
    search_fields = ('nom', 'description', 'sous_direction__nom', 'sous_direction__direction__nom')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Processus)
class ProcessusAdmin(admin.ModelAdmin):
    list_display = ('nom', 'cree_par', 'is_active', 'created_at')
    list_filter = ('created_at', 'cree_par', 'is_active')
    search_fields = ('nom', 'description', 'cree_par__username', 'cree_par__email')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(DysfonctionnementRecommandation)
class DysfonctionnementRecommandationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'cree_par', 'is_active', 'created_at')
    list_filter = ('created_at', 'cree_par', 'is_active')
    search_fields = ('nom', 'description', 'cree_par__username', 'cree_par__email')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'description', 'cree_par')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'entity_type', 'entity_name', 'created_at')
    list_filter = ('action', 'entity_type', 'created_at', 'user')
    search_fields = (
        'user__username',
        'user__email',
        'entity_name',
        'entity_id',
        'description',
    )
    readonly_fields = (
        'uuid',
        'user',
        'action',
        'entity_type',
        'entity_id',
        'entity_name',
        'description',
        'ip_address',
        'user_agent',
        'created_at',
    )
    ordering = ('-created_at',)


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'traitement_delai_notice_days',
        'traitement_reminder_frequency_days',
        'updated_at',
    )
    fieldsets = (
        ('Paramètres de notification', {
            'fields': ('traitement_delai_notice_days', 'traitement_reminder_frequency_days')
        }),
        ('Métadonnées', {
            'fields': ('uuid', 'created_at', 'updated_at', 'singleton_enforcer'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'singleton_enforcer')


@admin.register(DashboardNotificationSettings)
class DashboardNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'days_before_period_end',
        'days_after_period_end',
        'reminder_frequency_days',
        'updated_at',
    )
    fieldsets = (
        ('Paramètres de notification tableau de bord', {
            'fields': ('days_before_period_end', 'days_after_period_end', 'reminder_frequency_days')
        }),
        ('Métadonnées', {
            'fields': ('uuid', 'created_at', 'updated_at', 'singleton_enforcer'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'singleton_enforcer')


@admin.register(EmailSettings)
class EmailSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'email_host',
        'email_host_user',
        'email_port',
        'email_use_tls',
        'updated_at',
    )
    fieldsets = (
        ('Configuration SMTP', {
            'fields': ('email_host', 'email_port', 'email_host_user', 'email_host_password')
        }),
        ('Sécurité', {
            'fields': ('email_use_tls', 'email_use_ssl')
        }),
        ('Paramètres d\'envoi', {
            'fields': ('email_from_name', 'email_timeout')
        }),
        ('Métadonnées', {
            'fields': ('uuid', 'created_at', 'updated_at', 'singleton_enforcer'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'singleton_enforcer')
    
    def get_readonly_fields(self, request, obj=None):
        """Rendre le mot de passe en lecture seule après création"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:  # Si l'objet existe déjà
            readonly_fields.append('email_host_password')
        return readonly_fields


@admin.register(ReminderEmailLog)
class ReminderEmailLogAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'subject', 'context_hash', 'sent_at')
    search_fields = ('recipient', 'subject', 'context_hash')
    list_filter = ('sent_at',)
    readonly_fields = ('uuid', 'recipient', 'subject', 'context_hash', 'sent_at')


@admin.register(Mois)
class MoisAdmin(admin.ModelAdmin):
    list_display = ('numero', 'nom', 'abreviation', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('nom', 'abreviation')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    ordering = ('numero',)
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'numero', 'nom', 'abreviation')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Frequence)
class FrequenceAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les fréquences"""
    
    list_display = [
        'nom', 'indicateurs_count', 'created_at', 'updated_at'
    ]
    list_filter = [
        'created_at', 'updated_at'
    ]
    search_fields = [
        'nom'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['nom']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'nom')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def indicateurs_count(self, obj):
        """Afficher le nombre d'indicateurs utilisant cette fréquence"""
        return obj.indicateurs.count()
    indicateurs_count.short_description = 'Nb Indicateurs'


@admin.register(Periodicite)
class PeriodiciteAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les périodicités"""
    
    list_display = [
        'indicateur_id', 'periode', 'a_realiser', 'realiser', 'taux', 'created_at', 'updated_at'
    ]
    list_filter = [
        'periode', 'indicateur_id__objective_id', 'created_at', 'updated_at'
    ]
    search_fields = [
        'indicateur_id__libelle', 'indicateur_id__objective_id__libelle'
    ]
    readonly_fields = [
        'uuid', 'taux', 'created_at', 'updated_at'
    ]
    ordering = ['indicateur_id', 'periode', '-created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'indicateur_id', 'periode')
        }),
        ('Mesures', {
            'fields': ('a_realiser', 'realiser', 'taux')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('indicateur_id', 'indicateur_id__objective_id')


@admin.register(Cible)
class CibleAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les cibles"""
    
    list_display = [
        'indicateur_id', 'condition', 'valeur', 'created_at', 'updated_at'
    ]
    list_filter = [
        'condition', 'indicateur_id', 'created_at', 'updated_at'
    ]
    search_fields = [
        'indicateur_id__libelle'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['indicateur_id', '-created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'indicateur_id')
        }),
        ('Cible', {
            'fields': ('condition', 'valeur')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('indicateur_id')


@admin.register(Versions)
class VersionsAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les versions"""
    
    list_display = [
        'code', 'nom', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'code', 'nom', 'description'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['nom']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'code', 'nom', 'description')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Annee)
class AnneeAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les années"""
    
    list_display = [
        'annee', 'libelle', 'is_active', 'pacs_count', 'created_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'annee', 'libelle', 'description'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['-annee']  # Années récentes en premier
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'annee', 'libelle', 'description')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def pacs_count(self, obj):
        """Afficher le nombre de PACs associés à cette année"""
        return obj.pacs.count()
    pacs_count.short_description = 'Nb PACs'


# ==================== ADMIN POUR LA CARTOGRAPHIE DES RISQUES ====================

@admin.register(FrequenceRisque)
class FrequenceRisqueAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les fréquences de risque"""
    
    list_display = [
        'libelle', 'evaluations_count', 'is_active', 'created_at', 'updated_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'libelle'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['libelle']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'libelle')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def evaluations_count(self, obj):
        """Afficher le nombre d'évaluations utilisant cette fréquence"""
        return obj.evaluations.count()
    evaluations_count.short_description = 'Nb Évaluations'


@admin.register(GraviteRisque)
class GraviteRisqueAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les gravités de risque"""
    
    list_display = [
        'libelle', 'evaluations_count', 'is_active', 'created_at', 'updated_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'libelle'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['libelle']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'libelle')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def evaluations_count(self, obj):
        """Afficher le nombre d'évaluations utilisant cette gravité"""
        return obj.evaluations.count()
    evaluations_count.short_description = 'Nb Évaluations'


@admin.register(CriticiteRisque)
class CriticiteRisqueAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les criticités de risque"""
    
    list_display = [
        'libelle', 'evaluations_count', 'is_active', 'created_at', 'updated_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'libelle'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['libelle']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'libelle')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def evaluations_count(self, obj):
        """Afficher le nombre d'évaluations utilisant cette criticité"""
        return obj.evaluations.count()
    evaluations_count.short_description = 'Nb Évaluations'


class RisqueAdminForm(forms.ModelForm):
    """Formulaire personnalisé pour gérer les niveaux de risque comme une chaîne"""
    niveaux_risque_text = forms.CharField(
        required=False,
        label='Niveaux de risque',
        help_text='Entrez les niveaux séparés par des virgules (ex: 5D, 5E, 4C, 4D, 4E, 3B, 3C, 3D, 2A, 2B, 1A)',
        widget=forms.TextInput(attrs={'size': 100})
    )
    
    class Meta:
        model = Risque
        fields = '__all__'
        exclude = ['niveaux_risque']  # Exclure le champ JSON original
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialiser le champ texte avec les valeurs existantes
        if self.instance and self.instance.pk and self.instance.niveaux_risque:
            if isinstance(self.instance.niveaux_risque, list):
                self.fields['niveaux_risque_text'].initial = ', '.join(self.instance.niveaux_risque)
            else:
                self.fields['niveaux_risque_text'].initial = str(self.instance.niveaux_risque)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Convertir la chaîne en liste
        niveaux_text = self.cleaned_data.get('niveaux_risque_text', '')
        if niveaux_text:
            niveaux = [n.strip().upper() for n in niveaux_text.split(',') if n.strip()]
            instance.niveaux_risque = niveaux
        else:
            instance.niveaux_risque = []
        
        if commit:
            instance.save()
        return instance


@admin.register(Risque)
class RisqueAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les types de risques"""
    form = RisqueAdminForm
    
    list_display = [
        'libelle', 'niveaux_risque_display', 'evaluations_count', 'is_active', 'created_at', 'updated_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'libelle', 'description'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['libelle']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'libelle', 'description')
        }),
        ('Niveaux de risque', {
            'fields': ('niveaux_risque_text',),
            'description': 'Entrez les niveaux séparés par des virgules (ex: 5D, 5E, 4C, 4D, 4E, 3B, 3C, 3D, 2A, 2B, 1A)'
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def evaluations_count(self, obj):
        """Afficher le nombre d'évaluations utilisant ce type de risque"""
        return obj.evaluations.count()
    evaluations_count.short_description = 'Nb Évaluations'
    
    def niveaux_risque_display(self, obj):
        """Afficher les niveaux de risque dans la liste"""
        if obj.niveaux_risque and isinstance(obj.niveaux_risque, list) and len(obj.niveaux_risque) > 0:
            return ', '.join(obj.niveaux_risque)
        return '-'
    niveaux_risque_display.short_description = 'Niveaux de risque'

class EvaluationRisqueInline(admin.TabularInline):
    """Inline pour afficher les évaluations de risque liées à une version"""
    model = None  # Sera défini après l'import
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('details_cdr', 'frequence', 'gravite', 'criticite', 'risque', 'created_at')
    readonly_fields = ('details_cdr', 'frequence', 'gravite', 'criticite', 'risque', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(VersionEvaluationCDR)
class VersionEvaluationCDRAdmin(admin.ModelAdmin):
    list_display = ('nom', 'evaluations_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'evaluations_count')
    ordering = ('created_at', 'nom')

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'description')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Statistiques', {
            'fields': ('evaluations_count',)
        }),
        ('Métadonnées', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def evaluations_count(self, obj):
        """Afficher le nombre d'évaluations utilisant cette version"""
        return obj.evaluations.count()
    evaluations_count.short_description = 'Nombre d\'évaluations'


# ==================== ADMIN POUR LA DOCUMENTATION ====================

@admin.register(TypeDocument)
class TypeDocumentAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les types de documents"""

    list_display = [
        'nom', 'code', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'nom', 'code', 'description'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['nom']

    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'nom', 'code', 'description')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EditionDocument)
class EditionDocumentAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les éditions de documents"""

    list_display = [
        'title', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'title', 'description'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'title', 'description')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AmendementDocument)
class AmendementDocumentAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les amendements de documents"""

    list_display = [
        'title', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'title', 'description'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'title', 'description')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MediaDocument)
class MediaDocumentAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les médias de documents"""
    
    list_display = [
        'document', 'media', 'created_at'
    ]
    list_filter = [
        'created_at', 'document'
    ]
    search_fields = [
        'document__name', 'media__description'
    ]
    readonly_fields = [
        'uuid', 'created_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'document', 'media')
        }),
        ('Métadonnées', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('document', 'media')


# ==================== ADMIN POUR LE SYSTÈME DE RÔLES ====================

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les rôles"""
    
    list_display = [
        'code', 'nom', 'description', 'is_active', 'created_at', 'updated_at'
    ]
    list_filter = [
        'is_active', 'created_at', 'updated_at'
    ]
    search_fields = [
        'code', 'nom', 'description'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at'
    ]
    ordering = ['nom']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'code', 'nom', 'description')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class ProcessusMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Champ personnalisé pour n'afficher que le nom du processus"""
    def label_from_instance(self, obj):
        """Retourner seulement le nom du processus, pas le numéro"""
        return obj.nom


class UserProcessusForm(forms.ModelForm):
    """Formulaire personnalisé pour permettre la sélection multiple de processus"""
    processus_multiple = ProcessusMultipleChoiceField(
        queryset=Processus.objects.filter(is_active=True).order_by('nom'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'compact-checkboxes'}),
        required=False,
        label='Processus',
        help_text='Sélectionnez un ou plusieurs processus à attribuer'
    )
    
    class Meta:
        model = UserProcessus
        fields = ['user', 'attribue_par', 'is_active']
        widgets = {
            'user': forms.Select(attrs={'class': 'user-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si on modifie un objet existant, pré-sélectionner tous les processus de l'utilisateur
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'user') and self.instance.user_id:
                # Récupérer tous les processus actifs de cet utilisateur
                existing_processus = UserProcessus.objects.filter(
                    user=self.instance.user,
                    is_active=True
                ).values_list('processus', flat=True)
                self.fields['processus_multiple'].initial = list(existing_processus)
                # Pré-remplir aussi l'utilisateur et le rendre readonly
                self.fields['user'].initial = self.instance.user
                self.fields['user'].widget.attrs['readonly'] = True
                self.fields['user'].widget.attrs['disabled'] = True
    
    def clean(self):
        # Définir un processus temporaire AVANT la validation du modèle
        # pour éviter l'erreur RelatedObjectDoesNotExist
        if hasattr(self.data, 'getlist'):
            processus_ids = self.data.getlist('processus_multiple')
        elif 'processus_multiple' in self.data:
            processus_ids = [self.data['processus_multiple']] if isinstance(self.data['processus_multiple'], str) else self.data['processus_multiple']
        else:
            processus_ids = []
            
        if processus_ids:
            try:
                processus_uuid = processus_ids[0] if isinstance(processus_ids[0], str) else str(processus_ids[0])
                processus = Processus.objects.get(uuid=processus_uuid)
                self.instance.processus = processus
            except (Processus.DoesNotExist, ValueError, TypeError):
                pass
        
        cleaned_data = super().clean()
        processus_multiple = cleaned_data.get('processus_multiple')
        
        if not processus_multiple:
            raise ValidationError('Vous devez sélectionner au moins un processus.')
        
        # Si le champ user est disabled, récupérer la valeur depuis l'instance
        if 'user' not in cleaned_data or not cleaned_data['user']:
            if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
                cleaned_data['user'] = self.instance.user
        
        return cleaned_data
    
    def _post_clean(self):
        """Surcharger _post_clean pour exclure processus de la validation unique"""
        # Exclure processus de la validation unique car nous créons plusieurs instances
        # Le processus temporaire a déjà été défini dans clean()
        exclude = set()
        if hasattr(self, '_get_validation_exclusions'):
            exclude = self._get_validation_exclusions()
        
        # Appeler la méthode parente qui validera le modèle
        super()._post_clean()


@admin.register(UserProcessus)
class UserProcessusAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les attributions processus-utilisateur"""
    
    form = UserProcessusForm
    
    list_display = [
        'user', 'processus', 'attribue_par', 'date_attribution', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_active', 'date_attribution', 'created_at', 'processus'
    ]
    search_fields = [
        'user__username', 'user__email', 'processus__nom', 'processus__numero_processus'
    ]
    readonly_fields = [
        'uuid', 'date_attribution', 'created_at', 'updated_at'
    ]
    ordering = ['-date_attribution']
    
    fieldsets = (
        ('Attribution', {
            'fields': ('uuid', 'user', 'processus_multiple', 'attribue_par')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('date_attribution', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Sauvegarder le modèle - créer plusieurs UserProcessus pour chaque processus sélectionné"""
        processus_list = form.cleaned_data.get('processus_multiple', [])
        user = form.cleaned_data['user']
        attribue_par = form.cleaned_data.get('attribue_par') or request.user
        is_active = form.cleaned_data.get('is_active', True)
        
        if not change:  # Création
            # Créer un UserProcessus pour chaque processus sélectionné
            for processus in processus_list:
                # Vérifier si la relation existe déjà
                user_processus, created = UserProcessus.objects.get_or_create(
                    user=user,
                    processus=processus,
                    defaults={
                        'attribue_par': attribue_par,
                        'is_active': is_active
                    }
                )
                if not created:
                    # Mettre à jour si existe déjà
                    user_processus.attribue_par = attribue_par
                    user_processus.is_active = is_active
                    user_processus.save()
        else:  # Modification
            # Récupérer l'utilisateur depuis l'objet existant ou le formulaire
            user_to_update = obj.user if hasattr(obj, 'user') and obj.user else user
            
            # Supprimer les processus non sélectionnés pour cet utilisateur
            UserProcessus.objects.filter(
                user=user_to_update
            ).exclude(processus__in=processus_list).delete()
            
            # Créer ou mettre à jour les processus sélectionnés
            for processus in processus_list:
                user_processus, created = UserProcessus.objects.get_or_create(
                    user=user_to_update,
                    processus=processus,
                    defaults={
                        'attribue_par': attribue_par,
                        'is_active': is_active
                    }
                )
                if not created:
                    user_processus.attribue_par = attribue_par
                    user_processus.is_active = is_active
                    user_processus.save()
    
    def response_post_save_add(self, request, obj):
        """Rediriger vers la liste après l'ajout"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:parametre_userprocessus_changelist'))
    
    def response_post_save_change(self, request, obj):
        """Rediriger vers la liste après la modification"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:parametre_userprocessus_changelist'))
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('user', 'processus', 'attribue_par')
    
    class Media:
        css = {
            'all': ('admin/css/userprocessusrole_admin.css',)
        }


class RoleMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Champ personnalisé pour n'afficher que le nom du rôle"""
    def label_from_instance(self, obj):
        """Retourner seulement le nom du rôle, pas le code"""
        return obj.nom


class ProcessusMultipleChoiceFieldForRole(forms.ModelMultipleChoiceField):
    """Champ personnalisé pour n'afficher que le nom du processus"""
    def label_from_instance(self, obj):
        """Retourner seulement le nom du processus, pas le numéro"""
        return obj.nom


class UserProcessusRoleForm(forms.ModelForm):
    """Formulaire personnalisé pour permettre la sélection multiple de processus et rôles"""
    processus_multiple = ProcessusMultipleChoiceFieldForRole(
        queryset=Processus.objects.filter(is_active=True).order_by('nom'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'compact-checkboxes'}),
        required=False,
        label='Processus',
        help_text='Sélectionnez un ou plusieurs processus'
    )
    roles = RoleMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'compact-checkboxes'}),
        required=False,
        label='Rôles',
        help_text='Sélectionnez un ou plusieurs rôles à attribuer'
    )
    
    class Meta:
        model = UserProcessusRole
        fields = ['user', 'attribue_par', 'is_active']
        widgets = {
            'user': forms.Select(attrs={'class': 'user-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrer les processus disponibles selon l'utilisateur sélectionné
        user_id = None
        if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user_id:
            user_id = self.instance.user_id
        elif self.data and 'user' in self.data:
            user_id = self.data.get('user')
        
        if user_id:
            # Filtrer pour ne montrer que les processus où l'utilisateur est attribué
            processus_ids = UserProcessus.objects.filter(
                user_id=user_id,
                is_active=True
            ).values_list('processus_id', flat=True)
            self.fields['processus_multiple'].queryset = Processus.objects.filter(
                uuid__in=processus_ids,
                is_active=True
            ).order_by('nom')
        
        # Si on modifie un objet existant, pré-sélectionner tous les processus et rôles de l'utilisateur
        if self.instance and self.instance.pk:
            try:
                if hasattr(self.instance, 'user') and self.instance.user_id:
                    # Récupérer tous les processus distincts où cet utilisateur a des rôles
                    existing_processus = UserProcessusRole.objects.filter(
                        user=self.instance.user,
                        is_active=True
                    ).values_list('processus', flat=True).distinct()
                    self.fields['processus_multiple'].initial = list(existing_processus)
                    
                    # Récupérer tous les rôles distincts attribués à cet utilisateur
                    existing_roles = UserProcessusRole.objects.filter(
                        user=self.instance.user,
                        is_active=True
                    ).values_list('role', flat=True).distinct()
                    self.fields['roles'].initial = list(existing_roles)
                    
                    # Pré-remplir l'utilisateur et le rendre readonly
                    self.fields['user'].initial = self.instance.user
                    self.fields['user'].widget.attrs['readonly'] = True
                    self.fields['user'].widget.attrs['disabled'] = True
            except Exception:
                # Si une erreur survient, initialiser avec une liste vide
                pass
        
        # Filtrer les rôles actifs et personnaliser les choix pour n'afficher que le nom
        queryset = Role.objects.filter(is_active=True).order_by('code', 'nom')
        self.fields['roles'].queryset = queryset
        
        # Personnaliser les choix pour n'afficher que le nom
        choices = [(role.uuid, role.nom) for role in queryset]
        self.fields['roles'].choices = choices
    
    def clean(self):
        # Définir un processus temporaire AVANT la validation du modèle
        # pour éviter l'erreur RelatedObjectDoesNotExist
        if hasattr(self.data, 'getlist'):
            processus_ids = self.data.getlist('processus_multiple')
        elif 'processus_multiple' in self.data:
            processus_ids = [self.data['processus_multiple']] if isinstance(self.data['processus_multiple'], str) else self.data['processus_multiple']
        else:
            processus_ids = []
            
        if processus_ids:
            try:
                processus_uuid = processus_ids[0] if isinstance(processus_ids[0], str) else str(processus_ids[0])
                processus = Processus.objects.get(uuid=processus_uuid)
                self.instance.processus = processus
            except (Processus.DoesNotExist, ValueError, TypeError):
                pass
        
        cleaned_data = super().clean()
        processus_multiple = cleaned_data.get('processus_multiple')
        roles = cleaned_data.get('roles')
        
        if not processus_multiple:
            raise ValidationError('Vous devez sélectionner au moins un processus.')
        
        if not roles:
            raise ValidationError('Vous devez sélectionner au moins un rôle.')
        
        # Si le champ user est disabled, récupérer la valeur depuis l'instance
        if 'user' not in cleaned_data or not cleaned_data['user']:
            if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
                cleaned_data['user'] = self.instance.user
        
        return cleaned_data
    
    def _post_clean(self):
        """Surcharger _post_clean pour exclure processus de la validation unique"""
        # Exclure processus de la validation unique car nous créons plusieurs instances
        # Le processus temporaire a déjà été défini dans clean()
        exclude = set()
        if hasattr(self, '_get_validation_exclusions'):
            exclude = self._get_validation_exclusions()
        
        # Appeler la méthode parente qui validera le modèle
        super()._post_clean()


@admin.register(UserProcessusRole)
class UserProcessusRoleAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les rôles utilisateur-processus"""
    
    form = UserProcessusRoleForm
    
    list_display = [
        'user', 'processus', 'role', 'attribue_par', 'date_attribution', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_active', 'date_attribution', 'created_at', 'processus', 'role'
    ]
    search_fields = [
        'user__username', 'user__email', 'processus__nom', 'processus__numero_processus', 'role__code', 'role__nom'
    ]
    readonly_fields = [
        'uuid', 'date_attribution', 'created_at', 'updated_at'
    ]
    ordering = ['-date_attribution']
    
    fieldsets = (
        ('Attribution de rôles', {
            'fields': ('uuid', 'user', 'processus_multiple', 'roles', 'attribue_par')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('date_attribution', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    class Media:
        js = ('admin/js/userprocessusrole_filter.js',)
        css = {
            'all': ('admin/css/userprocessusrole_admin.css',)
        }
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('user', 'processus', 'role', 'attribue_par')
    
    def get_urls(self):
        """Ajouter des URLs personnalisées pour récupérer les processus et rôles d'un utilisateur"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'get_processus/',
                self.admin_site.admin_view(self.get_user_processus),
                name='parametre_userprocessusrole_get_processus',
            ),
            path(
                'get_user_roles/',
                self.admin_site.admin_view(self.get_user_roles),
                name='parametre_userprocessusrole_get_user_roles',
            ),
        ]
        return custom_urls + urls
    
    def get_user_processus(self, request):
        """Vue pour récupérer les processus d'un utilisateur via AJAX"""
        from django.contrib.auth.models import User
        
        if request.method != 'GET':
            return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
        
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'processus': []}, safe=False)
        
        try:
            user = User.objects.get(id=user_id)
            processus_list = UserProcessus.objects.filter(
                user=user,
                is_active=True
            ).select_related('processus')
            
            processus_data = []
            for up in processus_list:
                processus_data.append({
                    'uuid': str(up.processus.uuid),
                    'nom': up.processus.nom,
                    'numero_processus': up.processus.numero_processus
                })
            
            return JsonResponse({'processus': processus_data}, safe=False)
        except User.DoesNotExist:
            return JsonResponse({'processus': []}, safe=False)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de la récupération des processus utilisateur: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
    
    def get_user_roles(self, request):
        """Vue pour récupérer les rôles déjà attribués à un utilisateur pour ses processus"""
        from django.contrib.auth.models import User
        
        if request.method != 'GET':
            return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
        
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'roles': []}, safe=False)
        
        try:
            user = User.objects.get(id=user_id)
            user_roles = UserProcessusRole.objects.filter(
                user=user,
                is_active=True
            ).select_related('processus', 'role')
            
            roles_data = []
            for ur in user_roles:
                roles_data.append({
                    'processus_uuid': str(ur.processus.uuid),
                    'role_uuid': str(ur.role.uuid),
                    'role_nom': ur.role.nom
                })
            
            return JsonResponse({'roles': roles_data}, safe=False)
        except User.DoesNotExist:
            return JsonResponse({'roles': []}, safe=False)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de la récupération des rôles utilisateur: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
    
    def save_model(self, request, obj, form, change):
        """Sauvegarder le modèle - créer plusieurs instances pour chaque combinaison processus-rôle"""
        processus_list = form.cleaned_data.get('processus_multiple', [])
        roles = form.cleaned_data.get('roles', [])
        
        if not processus_list or not roles:
            # Assigner des valeurs temporaires à obj pour éviter l'erreur dans __str__
            # lors du logging par Django
            if not hasattr(obj, 'processus') or not obj.processus:
                # Assigner le premier processus temporairement
                if processus_list:
                    obj.processus = processus_list[0] if isinstance(processus_list, list) else processus_list
            if not hasattr(obj, 'role') or not obj.role:
                # Assigner le premier rôle temporairement
                if roles:
                    obj.role = roles[0] if isinstance(roles, list) else roles
            return
        
        # Récupérer les valeurs du formulaire
        user = form.cleaned_data.get('user')
        attribue_par = form.cleaned_data.get('attribue_par') or request.user
        is_active = form.cleaned_data.get('is_active', True)
        
        if not change:  # Création
            # Créer un UserProcessusRole pour chaque combinaison processus-rôle
            for processus in processus_list:
                for role in roles:
                    UserProcessusRole.objects.get_or_create(
                        user=user,
                        processus=processus,
                        role=role,
                        defaults={
                            'attribue_par': attribue_par,
                            'is_active': is_active
                        }
                    )
        else:  # Modification
            # Récupérer l'utilisateur depuis l'objet existant ou le formulaire
            user_to_update = obj.user if hasattr(obj, 'user') and obj.user else user
            
            # Supprimer tous les UserProcessusRole existants pour cet utilisateur
            # qui ne sont pas dans les nouvelles sélections
            existing_combinations = UserProcessusRole.objects.filter(
                user=user_to_update
            )
            
            # Supprimer les combinaisons qui ne sont plus sélectionnées
            for existing in existing_combinations:
                if existing.processus not in processus_list or existing.role not in roles:
                    existing.delete()
            
            # Créer ou mettre à jour les combinaisons sélectionnées
            for processus in processus_list:
                for role in roles:
                    user_processus_role, created = UserProcessusRole.objects.get_or_create(
                        user=user_to_update,
                        processus=processus,
                        role=role,
                        defaults={
                            'attribue_par': attribue_par,
                            'is_active': is_active
                        }
                    )
                    if not created:
                        user_processus_role.attribue_par = attribue_par
                        user_processus_role.is_active = is_active
                        user_processus_role.save()
    
    def response_post_save_add(self, request, obj):
        """Rediriger vers la liste après l'ajout"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:parametre_userprocessusrole_changelist'))
    
    def response_post_save_change(self, request, obj):
        """Rediriger vers la liste après la modification"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:parametre_userprocessusrole_changelist'))


@admin.register(ApplicationConfig)
class ApplicationConfigAdmin(admin.ModelAdmin):
    """
    Interface d'administration pour activer/désactiver les applications
    """
    list_display = [
        'app_name_display',
        'status_badge',
        'maintenance_message_short',
        'maintenance_period',
        'updated_by',
        'updated_at'
    ]
    list_filter = ['is_enabled', 'app_name']
    search_fields = ['app_name', 'maintenance_message']
    readonly_fields = ['updated_at', 'created_at']
    
    fieldsets = (
        ('Application', {
            'fields': ('app_name', 'is_enabled')
        }),
        ('Maintenance', {
            'fields': ('maintenance_message', 'maintenance_start', 'maintenance_end'),
            'classes': ('collapse',)
        }),
        ('Informations', {
            'fields': ('updated_by', 'updated_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def app_name_display(self, obj):
        """Affiche le nom complet de l'application"""
        return obj.get_app_name_display()
    app_name_display.short_description = 'Application'
    
    def status_badge(self, obj):
        """Badge coloré pour le statut"""
        if obj.is_enabled:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✅ ACTIVÉE</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ef4444; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">🔧 MAINTENANCE</span>'
            )
    status_badge.short_description = 'Statut'
    
    def maintenance_message_short(self, obj):
        """Affiche un extrait du message de maintenance"""
        if obj.maintenance_message:
            return obj.maintenance_message[:50] + '...' if len(obj.maintenance_message) > 50 else obj.maintenance_message
        return '-'
    maintenance_message_short.short_description = 'Message'
    
    def maintenance_period(self, obj):
        """Affiche la période de maintenance"""
        if obj.maintenance_start or obj.maintenance_end:
            start = obj.maintenance_start.strftime('%d/%m/%Y %H:%M') if obj.maintenance_start else '?'
            end = obj.maintenance_end.strftime('%d/%m/%Y %H:%M') if obj.maintenance_end else '?'
            return f"{start} → {end}"
        return '-'
    maintenance_period.short_description = 'Période'
    
    def save_model(self, request, obj, form, change):
        """Enregistre l'utilisateur qui a fait la modification"""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        
        # Log de l'action
        action = "désactivée" if not obj.is_enabled else "activée"
        self.message_user(
            request,
            f"Application '{obj.get_app_name_display()}' {action} avec succès.",
            level='SUCCESS' if obj.is_enabled else 'WARNING'
        )
    
