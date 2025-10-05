from django.contrib import admin
from .models import (
    Nature, Categorie, Source, ActionType, Statut, 
    EtatMiseEnOeuvre, Appreciation, Media, Preuve,
    Direction, SousDirection, Service, Processus,
    ActivityLog, NotificationSettings, NotificationOverride, ReminderEmailLog
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
        'pac_echeance_notice_days',
        'traitement_delai_notice_days',
        'suivi_mise_en_oeuvre_notice_days',
        'suivi_cloture_notice_days',
        'reminders_count_before_day',
        'updated_at',
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'singleton_enforcer')


@admin.register(NotificationOverride)
class NotificationOverrideAdmin(admin.ModelAdmin):
    list_display = (
        'get_target_display',
        'pac_echeance_notice_days',
        'traitement_delai_notice_days',
        'suivi_mise_en_oeuvre_notice_days',
        'suivi_cloture_notice_days',
        'reminders_count_before_day',
        'created_at',
    )
    list_filter = (
        'direction',
        'processus',
        'action_type',
        'content_type',
        'created_at',
    )
    search_fields = (
        'direction__nom',
        'processus__nom',
        'action_type__nom',
    )
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Ciblage', {
            'fields': ('content_type', 'object_id', 'direction', 'processus', 'action_type')
        }),
        ('Paramètres de notification', {
            'fields': (
                'pac_echeance_notice_days',
                'traitement_delai_notice_days',
                'suivi_mise_en_oeuvre_notice_days',
                'suivi_cloture_notice_days',
                'reminders_count_before_day',
            )
        }),
        ('Métadonnées', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_target_display(self, obj):
        """Affiche la cible de l'override"""
        if obj.content_object:
            return f"Objet: {obj.content_object}"
        elif obj.direction:
            return f"Direction: {obj.direction.nom}"
        elif obj.processus:
            return f"Processus: {obj.processus.nom}"
        elif obj.action_type:
            return f"Type d'action: {obj.action_type.nom}"
        return "Aucune cible"
    
    get_target_display.short_description = "Cible"


@admin.register(ReminderEmailLog)
class ReminderEmailLogAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'subject', 'context_hash', 'sent_at')
    search_fields = ('recipient', 'subject', 'context_hash')
    list_filter = ('sent_at',)
    readonly_fields = ('uuid', 'recipient', 'subject', 'context_hash', 'sent_at')