from django.contrib import admin
from .models import (
    Nature, Categorie, Source, ActionType, Statut, 
    EtatMiseEnOeuvre, Appreciation, Media, Preuve,
    Direction, SousDirection, Service, Processus,
    ActivityLog, NotificationSettings, EmailSettings, ReminderEmailLog
)


@admin.register(Nature)
class NatureAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(ActionType)
class ActionTypeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
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
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Appreciation)
class AppreciationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
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
    list_display = ('nom', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('nom', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(SousDirection)
class SousDirectionAdmin(admin.ModelAdmin):
    list_display = ('nom', 'direction', 'description', 'created_at')
    list_filter = ('direction', 'created_at')
    search_fields = ('nom', 'description', 'direction__nom')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'sous_direction', 'description', 'created_at')
    list_filter = ('sous_direction__direction', 'sous_direction', 'created_at')
    search_fields = ('nom', 'description', 'sous_direction__nom', 'sous_direction__direction__nom')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(Processus)
class ProcessusAdmin(admin.ModelAdmin):
    list_display = ('nom', 'cree_par', 'created_at')
    list_filter = ('created_at', 'cree_par')
    search_fields = ('nom', 'description', 'cree_par__username', 'cree_par__email')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


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