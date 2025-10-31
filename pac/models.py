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
    libelle = models.CharField(max_length=500, null=True, blank=True)
    
    # Relations vers les modèles de l'app parametre
    nature = models.ForeignKey(
        'parametre.Nature', 
        on_delete=models.CASCADE, 
        related_name='pacs',
        null=True,
        blank=True
    )
    categorie = models.ForeignKey(
        'parametre.Categorie', 
        on_delete=models.CASCADE, 
        related_name='pacs',
        null=True,
        blank=True
    )
    source = models.ForeignKey(
        'parametre.Source', 
        on_delete=models.CASCADE, 
        related_name='pacs',
        null=True,
        blank=True
    )
    dysfonctionnement_recommandation = models.ForeignKey(
        'parametre.DysfonctionnementRecommandation', 
        on_delete=models.CASCADE, 
        related_name='pacs',
        null=True,
        blank=True
    )
    annee = models.ForeignKey(
        'parametre.Annee',
        on_delete=models.SET_NULL,
        related_name='pacs',
        null=True,
        blank=True,
        help_text='Année associée au PAC'
    )
    type_tableau = models.ForeignKey(
        'parametre.TypeTableau',
        on_delete=models.SET_NULL,
        related_name='pacs',
        null=True,
        blank=True,
        help_text='Type de tableau associé au PAC (Initial, Amendement, etc.)'
    )
    
    periode_de_realisation = models.DateField(null=True, blank=True)
    
    # Champs de validation
    is_validated = models.BooleanField(
        default=False,
        help_text='Indique si le PAC est validé (verrouille les champs PAC et Traitement)'
    )
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date de validation du PAC'
    )
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pacs_valides',
        help_text='Utilisateur qui a validé le PAC'
    )
    
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
        related_name='traitements',
        null=True,
        blank=True
    )
    responsable_direction = models.ForeignKey(
        'parametre.Direction',
        on_delete=models.CASCADE,
        related_name='traitements_responsables',
        blank=True,
        null=True
    )
    responsable_sous_direction = models.ForeignKey(
        'parametre.SousDirection',
        on_delete=models.CASCADE,
        related_name='traitements_responsables',
        blank=True,
        null=True
    )
    # Nouveau: permettre plusieurs responsables en parallèle, tout en gardant les FK pour compatibilité
    responsables_directions = models.ManyToManyField(
        'parametre.Direction',
        related_name='traitements_responsables_m2m',
        blank=True
    )
    responsables_sous_directions = models.ManyToManyField(
        'parametre.SousDirection',
        related_name='traitements_responsables_sous_m2m',
        blank=True
    )
    preuve = models.ForeignKey(
        'parametre.Preuve',
        on_delete=models.SET_NULL,
        related_name='traitements',
        blank=True,
        null=True
    )
    delai_realisation = models.DateField(null=True, blank=True)

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
    preuve = models.ForeignKey(
        'parametre.Preuve',
        on_delete=models.SET_NULL,
        related_name='suivis',
        blank=True,
        null=True
    )
    statut = models.ForeignKey(
        'parametre.Statut',
        on_delete=models.SET_NULL,
        related_name='suivis',
        blank=True,
        null=True
    )
    date_mise_en_oeuvre_effective = models.DateField(blank=True, null=True)
    date_cloture = models.DateField(blank=True, null=True)
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