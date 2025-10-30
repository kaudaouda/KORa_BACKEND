from django.contrib import admin
from .models import (
    Nature, Categorie, Source, ActionType, Statut, 
    EtatMiseEnOeuvre, Appreciation, Media, Preuve,
    Direction, SousDirection, Service, Processus,
    ActivityLog, NotificationSettings, DashboardNotificationSettings, EmailSettings, ReminderEmailLog,
    DysfonctionnementRecommandation, Frequence, Periodicite, Cible, TypeTableau, Annee
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


@admin.register(TypeTableau)
class TypeTableauAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les types de tableaux"""
    
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