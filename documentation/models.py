from django.db import models
import uuid


class Document(models.Model):
    """
    Modèle pour les documents
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200,
        help_text="Nom du document"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description du document"
    )
    date_application = models.DateField(
        help_text="Date d'application du document"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indique si ce document est actif et peut être utilisé"
    )
    annee = models.ForeignKey(
        'parametre.Annee',
        on_delete=models.SET_NULL,
        related_name='documents',
        null=True,
        blank=True,
        help_text="Année associée au document"
    )
    edition = models.ForeignKey(
        'parametre.EditionDocument',
        on_delete=models.SET_NULL,
        related_name='documents',
        null=True,
        blank=True,
        help_text="Édition associée au document"
    )
    amendement = models.ForeignKey(
        'parametre.AmendementDocument',
        on_delete=models.SET_NULL,
        related_name='documents',
        null=True,
        blank=True,
        help_text="Amendement associé au document"
    )
    categories = models.ManyToManyField(
        'parametre.CategorieDocument',
        related_name='documents',
        blank=True,
        help_text="Catégories associées au document"
    )
    parent_document = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='amendments',
        help_text="Document parent pour le suivi des amendements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document'
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-created_at']

    def __str__(self):
        return self.name
    
    def get_version_chain(self):
        """Récupérer toute la chaîne de versions (du plus ancien au plus récent)"""
        chain = []
        current = self
        
        # Remonter jusqu'au document racine
        while current.parent_document:
            chain.insert(0, current.parent_document)
            current = current.parent_document
        
        # Ajouter le document actuel
        chain.append(self)
        
        # Ajouter les amendements suivants
        def get_all_amendments(doc):
            amendments = []
            for amendment in doc.amendments.all().order_by('created_at'):
                amendments.append(amendment)
                amendments.extend(get_all_amendments(amendment))
            return amendments
        
        chain.extend(get_all_amendments(self))
        
        return chain
