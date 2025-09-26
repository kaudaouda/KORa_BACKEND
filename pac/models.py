from django.db import models
from django.contrib.auth.models import User
import uuid
from parametre.models import Processus


class Pac(models.Model):
    """
    Modèle pour les PAC (Plan d'Action Corrective)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_pac = models.CharField(max_length=50, unique=True)
    processus = models.ForeignKey(
        Processus, 
        on_delete=models.CASCADE, 
        related_name='pacs'
    )
    libelle = models.CharField(max_length=500)
    
    # Relations vers les modèles de l'app parametre
    nature = models.ForeignKey(
        'parametre.Nature', 
        on_delete=models.CASCADE, 
        related_name='pacs'
    )
    categorie = models.ForeignKey(
        'parametre.Categorie', 
        on_delete=models.CASCADE, 
        related_name='pacs'
    )
    source = models.ForeignKey(
        'parametre.Source', 
        on_delete=models.CASCADE, 
        related_name='pacs'
    )
    
    periode_de_realisation = models.DateField()
    cree_par = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='pacs_crees'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pac'
        verbose_name = 'PAC'
        verbose_name_plural = 'PACs'

    def __str__(self):
        return f"PAC {self.numero_pac} - {self.libelle}"




class Traitement(models.Model):
    """
    Modèle pour les traitements
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pac = models.ForeignKey(
        Pac, 
        on_delete=models.CASCADE, 
        related_name='traitements'
    )
    action = models.TextField()
    type_action = models.ForeignKey(
        'parametre.ActionType', 
        on_delete=models.CASCADE, 
        related_name='traitements'
    )
    preuve = models.ForeignKey(
        'parametre.Preuve', 
        on_delete=models.CASCADE, 
        related_name='traitements',
        blank=True,
        null=True
    )
    delai_realisation = models.DateField()

    class Meta:
        db_table = 'traitement'
        verbose_name = 'Traitement'
        verbose_name_plural = 'Traitements'

    def __str__(self):
        return f"Traitement {self.uuid} - {self.action[:50]}..."


class Suivi(models.Model):
    """
    Modèle pour le suivi des traitements
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traitement = models.ForeignKey(
        Traitement, 
        on_delete=models.CASCADE, 
        related_name='suivis'
    )
    etat_mise_en_oeuvre = models.ForeignKey(
        'parametre.EtatMiseEnOeuvre', 
        on_delete=models.CASCADE, 
        related_name='suivis'
    )
    resultat = models.TextField(blank=True, null=True)
    appreciation = models.ForeignKey(
        'parametre.Appreciation', 
        on_delete=models.CASCADE, 
        related_name='suivis'
    )
    cree_par = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='suivis_crees'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'suivi'
        verbose_name = 'Suivi'
        verbose_name_plural = 'Suivis'

    def __str__(self):
        return f"Suivi {self.uuid} - {self.etat_mise_en_oeuvre.nom}"