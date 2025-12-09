from django.contrib import admin
from django.utils.html import format_html
from .models import Document
from parametre.models import MediaDocument


class MediaDocumentInline(admin.TabularInline):
    """Inline pour afficher les médias associés à un document"""
    model = MediaDocument
    extra = 1
    fields = ('media', 'created_at')
    readonly_fields = ('created_at',)
    verbose_name = 'Média'
    verbose_name_plural = 'Médias de Documents'


class AmendmentInline(admin.TabularInline):
    """Inline pour afficher les amendements d'un document"""
    model = Document
    fk_name = 'parent_document'
    extra = 0
    fields = ('name', 'edition', 'amendement', 'date_application', 'is_active', 'created_at')
    readonly_fields = ('created_at',)
    verbose_name = 'Amendement'
    verbose_name_plural = 'Amendements de ce document'
    can_delete = False
    show_change_link = True


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'date_application',
        'is_active',
        'get_edition',
        'get_amendement',
        'get_is_amendment_badge',
        'get_parent_document',
        'get_amendments_count',
        'get_medias_count',
        'created_at'
    )
    list_filter = (
        'is_active',
        'date_application',
        ('parent_document', admin.EmptyFieldListFilter),  # Filtre pour documents originaux vs amendements
    )
    search_fields = ('name', 'description')
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'get_version_chain_display')
    date_hierarchy = 'date_application'
    autocomplete_fields = ['parent_document']  # Autocomplétion pour le champ parent_document

    def get_edition(self, obj):
        return obj.edition.title if obj.edition else '-'
    get_edition.short_description = 'Édition'

    def get_amendement(self, obj):
        return obj.amendement.title if obj.amendement else '-'
    get_amendement.short_description = 'Amendement'

    def get_medias_count(self, obj):
        """Affiche le nombre de médias associés au document"""
        count = obj.medias.count()
        return count if count > 0 else '-'
    get_medias_count.short_description = 'Nb Médias'

    def get_type(self, obj):
        """Affiche le type du document"""
        return obj.type.nom if obj.type else '-'
    get_type.short_description = 'Type'

    def get_is_amendment_badge(self, obj):
        """Badge pour indiquer si c'est un amendement"""
        if obj.parent_document:
            return format_html(
                '<span style="background-color: #F59E0B; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">AMENDEMENT</span>'
            )
        return format_html(
            '<span style="background-color: #10B981; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">ORIGINAL</span>'
        )
    get_is_amendment_badge.short_description = 'Type'

    def get_parent_document(self, obj):
        """Affiche le document parent s'il existe"""
        if obj.parent_document:
            return format_html(
                '<a href="/admin/documentation/document/{}/change/" style="color: #2563EB; '
                'text-decoration: underline;">📄 {}</a>',
                obj.parent_document.uuid,
                obj.parent_document.name[:50] + ('...' if len(obj.parent_document.name) > 50 else '')
            )
        return '-'
    get_parent_document.short_description = 'Document parent'

    def get_amendments_count(self, obj):
        """Affiche le nombre d'amendements de ce document"""
        count = obj.amendments.count()
        if count > 0:
            return format_html(
                '<span style="background-color: #EFF6FF; color: #2563EB; padding: 3px 8px; '
                'border-radius: 4px; font-weight: bold;">{} amendement{}</span>',
                count,
                's' if count > 1 else ''
            )
        return '-'
    get_amendments_count.short_description = 'Amendements'

    def get_version_chain_display(self, obj):
        """Affiche toute la chaîne de versions"""
        chain = obj.get_version_chain()
        html_parts = ['<div style="font-family: monospace; padding: 10px; background: #F3F4F6; border-radius: 8px;">']
        
        for idx, doc in enumerate(chain):
            is_current = doc.uuid == obj.uuid
            style = 'font-weight: bold; color: #2563EB;' if is_current else 'color: #6B7280;'
            
            edition_label = doc.edition.title if doc.edition else 'N/A'
            amendement_label = doc.amendement.title if doc.amendement else 'N/A'
            
            html_parts.append(
                f'<div style="{style}; padding: 8px 0; border-bottom: 1px solid #E5E7EB;">'
                f'{"➤ " if is_current else ""}V{idx + 1}: {doc.name} '
                f'<span style="background: #DBEAFE; padding: 2px 6px; border-radius: 3px; font-size: 11px;">'
                f'{edition_label} - {amendement_label}</span> '
                f'<span style="color: #9CA3AF; font-size: 11px;">({doc.created_at.strftime("%d/%m/%Y")})</span>'
                f'</div>'
            )
        
        html_parts.append('</div>')
        return format_html(''.join(html_parts))
    get_version_chain_display.short_description = 'Chaîne de versions complète'

    inlines = [MediaDocumentInline, AmendmentInline]

    fieldsets = (
        ('Informations générales', {
            'fields': ('uuid', 'name', 'description')
        }),
        ('🔗 Versioning & Amendements', {
            'fields': ('parent_document', 'get_version_chain_display'),
            'description': 'Gestion des versions et amendements du document. '
                          'Si ce document amende un autre document, sélectionnez le document parent.'
        }),
        ('Relations', {
            'fields': ('edition', 'amendement', 'type')
        }),
        ('Dates', {
            'fields': ('date_application',)
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
