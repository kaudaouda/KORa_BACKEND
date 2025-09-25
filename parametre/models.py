from django.db import models
import uuid


class Nature(models.Model):
    """
    Modèle pour les types de nature (Recommandation, Non-conformité)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'nature'
        verbose_name = 'Nature'
        verbose_name_plural = 'Natures'

    def __str__(self):
        return self.nom


class Categorie(models.Model):
    """
    Modèle pour les catégories
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categorie'
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'

    def __str__(self):
        return self.nom


class Source(models.Model):
    """
    Modèle pour les sources (Revue de processus, Audit interne...)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'source'
        verbose_name = 'Source'
        verbose_name_plural = 'Sources'

    def __str__(self):
        return self.nom


class ActionType(models.Model):
    """
    Modèle pour les types d'action (Corrective, Préventive)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'action_type'
        verbose_name = 'Type d\'action'
        verbose_name_plural = 'Types d\'action'

    def __str__(self):
        return self.nom


class Statut(models.Model):
    """
    Modèle pour les statuts (Ouverte, Clôturée, Suspendue)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'statut'
        verbose_name = 'Statut'
        verbose_name_plural = 'Statuts'

    def __str__(self):
        return self.nom


class EtatMiseEnOeuvre(models.Model):
    """
    Modèle pour les états de mise en œuvre (En cours, Réalisée, Partiellement réalisée)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'etat_mise_en_oeuvre'
        verbose_name = 'État de mise en œuvre'
        verbose_name_plural = 'États de mise en œuvre'

    def __str__(self):
        return self.nom


class Appreciation(models.Model):
    """
    Modèle pour les appréciations (Satisfaisant, Non satisfaisant)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appreciation'
        verbose_name = 'Appréciation'
        verbose_name_plural = 'Appréciations'

    def __str__(self):
        return self.nom


class Media(models.Model):
    """
    Modèle pour les médias (fichiers)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url_fichier = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'media'
        verbose_name = 'Média'
        verbose_name_plural = 'Médias'

    def __str__(self):
        return f"Média {self.uuid}"


class Direction(models.Model):
    """
    Modèle pour les directions
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'direction'
        verbose_name = 'Direction'
        verbose_name_plural = 'Directions'

    def __str__(self):
        return self.nom


class SousDirection(models.Model):
    """
    Modèle pour les sous-directions
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='sous_directions')
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sous_direction'
        verbose_name = 'Sous-direction'
        verbose_name_plural = 'Sous-directions'
        unique_together = ['direction', 'nom']

    def __str__(self):
        return f"{self.direction.nom} - {self.nom}"


class Service(models.Model):
    """
    Modèle pour les services
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sous_direction = models.ForeignKey(SousDirection, on_delete=models.CASCADE, related_name='services')
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'service'
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        unique_together = ['sous_direction', 'nom']

    def __str__(self):
        return f"{self.sous_direction.direction.nom} - {self.sous_direction.nom} - {self.nom}"


class Preuve(models.Model):
    """
    Modèle pour les preuves (Evidence) - Déplacé de pac vers parametre
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.TextField()
    media = models.ForeignKey(
        Media, 
        on_delete=models.CASCADE, 
        related_name='preuves'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'preuve'
        verbose_name = 'Preuve'
        verbose_name_plural = 'Preuves'

    def __str__(self):
        return f"Preuve {self.uuid} - {self.description[:50]}..."