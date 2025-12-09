"""
Serializers pour l'application Documentation
"""
from rest_framework import serializers
from .models import Document
from parametre.models import Annee


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer pour les documents"""
    annee_nom = serializers.SerializerMethodField()
    edition_nom = serializers.SerializerMethodField()
    amendement_nom = serializers.SerializerMethodField()
    categories_details = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()
    has_amendments = serializers.SerializerMethodField()
    is_amendment = serializers.SerializerMethodField()
    version_info = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'uuid', 'name', 'description', 'date_application',
            'is_active', 'annee', 'annee_nom', 'edition', 'edition_nom',
            'amendement', 'amendement_nom', 'categories', 'categories_details',
            'media_url', 'created_at', 'updated_at',
            'parent_document', 'has_amendments', 'is_amendment', 'version_info'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_annee_nom(self, obj):
        """Retourner le nom de l'année"""
        if obj.annee:
            if hasattr(obj.annee, 'libelle') and obj.annee.libelle:
                return obj.annee.libelle
            return str(obj.annee.annee)
        return None

    def get_edition_nom(self, obj):
        """Retourner le nom de l'édition"""
        if obj.edition:
            return obj.edition.title
        return None

    def get_amendement_nom(self, obj):
        """Retourner le nom de l'amendement"""
        if obj.amendement:
            return obj.amendement.title
        return None

    def get_categories_details(self, obj):
        """Retourner les détails des catégories"""
        return [
            {
                'uuid': str(cat.uuid),
                'nom': cat.nom,
                'code': cat.code
            }
            for cat in obj.categories.all()
        ]

    def get_media_url(self, obj):
        """Retourner l'URL du premier média associé au document"""
        try:
            if obj.medias.exists():
                media_document = obj.medias.first()
                if media_document and media_document.media:
                    media = media_document.media
                    if hasattr(media, 'get_url'):
                        url = media.get_url()
                        # Construire l'URL complète si c'est un chemin relatif
                        if url and not url.startswith('http'):
                            # Récupérer la requête depuis le contexte
                            request = self.context.get('request')
                            if request:
                                return request.build_absolute_uri(url)
                            # Fallback si pas de requête
                            from django.conf import settings
                            base_url = getattr(settings, 'MEDIA_URL', '/medias/')
                            return f"{base_url.rstrip('/')}{url}" if url.startswith('/') else f"{base_url}{url}"
                        return url
                    return media.url_fichier
        except Exception:
            pass
        return None
    
    def get_has_amendments(self, obj):
        """Indique si ce document a des amendements"""
        return obj.amendments.exists()
    
    def get_is_amendment(self, obj):
        """Indique si ce document est lui-même un amendement"""
        return obj.parent_document is not None
    
    def get_version_info(self, obj):
        """Retourner les informations de version"""
        version_label = f"{obj.edition.title if obj.edition else 'N/A'} - {obj.amendement.title if obj.amendement else 'N/A'}"
        return {
            'version_label': version_label,
            'has_parent': obj.parent_document is not None,
            'parent_uuid': str(obj.parent_document.uuid) if obj.parent_document else None,
            'amendments_count': obj.amendments.count()
        }


class DocumentCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de documents"""

    class Meta:
        model = Document
        fields = [
            'name', 'description', 'date_application',
            'is_active', 'annee', 'edition', 'amendement', 'categories'
        ]

    def validate_name(self, value):
        """Valider que le nom n'est pas vide"""
        if not value or not value.strip():
            raise serializers.ValidationError("Le nom du document est requis")
        return value.strip()

    def create(self, validated_data):
        """
        Créer un document avec Edition 1 et Amendement 0 par défaut
        si ces valeurs ne sont pas fournies ou sont vides
        """
        from parametre.models import EditionDocument, AmendementDocument

        # Récupérer ou créer Edition 1 par défaut si non fourni ou vide
        edition = validated_data.get('edition')
        if not edition or edition == '':
            edition_1, _ = EditionDocument.objects.get_or_create(
                title='Edition 1',
                defaults={
                    'description': 'Première édition par défaut',
                    'is_active': True
                }
            )
            validated_data['edition'] = edition_1

        # Récupérer ou créer Amendement 0 par défaut si non fourni ou vide
        amendement = validated_data.get('amendement')
        if not amendement or amendement == '':
            amendement_0, _ = AmendementDocument.objects.get_or_create(
                title='Amendement 0',
                defaults={
                    'description': 'Amendement initial par défaut',
                    'is_active': True
                }
            )
            validated_data['amendement'] = amendement_0

        return super().create(validated_data)


class DocumentUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour de documents"""

    class Meta:
        model = Document
        fields = [
            'name', 'description', 'date_application',
            'is_active', 'annee', 'edition', 'amendement', 'categories'
        ]

    def validate_name(self, value):
        """Valider que le nom n'est pas vide"""
        if not value or not value.strip():
            raise serializers.ValidationError("Le nom du document est requis")
        return value.strip()


class DocumentAmendSerializer(serializers.ModelSerializer):
    """Serializer pour amender un document (créer une nouvelle version)"""
    
    class Meta:
        model = Document
        fields = [
            'name', 'description', 'date_application',
            'is_active', 'annee', 'edition', 'amendement', 
            'categories', 'parent_document'
        ]
    
    def validate_name(self, value):
        """Valider que le nom n'est pas vide"""
        if not value or not value.strip():
            raise serializers.ValidationError("Le nom du document est requis")
        return value.strip()
    
    def validate(self, data):
        """
        Validation personnalisée pour l'amendement
        Règle : Si Edition 1, alors Amendement DOIT être > 0
        """
        from parametre.models import EditionDocument, AmendementDocument
        
        edition = data.get('edition')
        amendement = data.get('amendement')
        
        # Vérifier qu'un parent_document est fourni
        if not data.get('parent_document'):
            raise serializers.ValidationError({
                'parent_document': 'Le document parent est requis pour un amendement'
            })
        
        # Règle : Si Edition 1, alors Amendement DOIT être > 0
        if edition and amendement:
            try:
                edition_1 = EditionDocument.objects.get(title='Edition 1')
                amendement_0 = AmendementDocument.objects.get(title='Amendement 0')
                
                if edition.uuid == edition_1.uuid and amendement.uuid == amendement_0.uuid:
                    raise serializers.ValidationError({
                        'amendement': 'Pour Edition 1, vous devez choisir un amendement supérieur à 0 (Amendement 1, 2, 3...)'
                    })
            except (EditionDocument.DoesNotExist, AmendementDocument.DoesNotExist):
                pass
        
        return data
    
    def create(self, validated_data):
        """
        Créer un nouvel amendement et désactiver le document parent
        """
        parent = validated_data.get('parent_document')
        
        # Désactiver le document parent si le nouvel amendement est actif
        if parent and validated_data.get('is_active', True):
            parent.is_active = False
            parent.save()
        
        return super().create(validated_data)
