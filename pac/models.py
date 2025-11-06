from django.db import models
from django.contrib.auth.models import User
import uuid
from parametre.models import Processus


class Pac(models.Model):
    """
    Modèle pour les PAC (Plan d'Action Corrective)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cree_par = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='pacs_crees'
    )
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pacs_valides',
        help_text='Utilisateur qui a validé le PAC'
    )
    is_validated = models.BooleanField(
        default=False,
        help_text='Indique que tous les détails et traitements sont renseignés. Permet la création des suivis.'
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date de validation des détails et traitements'
    )
    processus = models.ForeignKey(
        Processus, 
        on_delete=models.CASCADE, 
        related_name='pacs'
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
        'parametre.Versions',
        on_delete=models.SET_NULL,
        related_name='pacs',
        null=True,
        blank=True,
        help_text='Version associée au PAC (Initial, Amendement, etc.)'
    )
    initial_ref = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='amendements',
        null=True,
        blank=True,
        help_text='Référence au PAC initial (pour les amendements)'
    )

    class Meta:
        db_table = 'pac'
        verbose_name = 'PAC'
        verbose_name_plural = 'PACs'
        constraints = [
            models.UniqueConstraint(
                fields=['processus', 'annee', 'type_tableau', 'cree_par'],
                name='unique_pac_per_processus_annee_type_tableau_user'
            )
        ]

    def __str__(self):
        return f"PAC {self.uuid}"


class DetailsPac(models.Model):
    """
    Modèle pour les détails d'un PAC
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_pac = models.CharField(max_length=50, null=True, blank=True, help_text='Numéro du détail PAC (peut être dupliqué pour les amendements)')
    pac = models.ForeignKey(
        Pac,
        on_delete=models.CASCADE,
        related_name='details',
        null=True,
        blank=True,
        help_text='PAC associé'
    )
    dysfonctionnement_recommandation = models.ForeignKey(
        'parametre.DysfonctionnementRecommandation',
        on_delete=models.CASCADE,
        related_name='details_pacs',
        null=True,
        blank=True,
        help_text='Dysfonctionnement ou recommandation'
    )
    libelle = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Libellé du détail'
    )
    nature = models.ForeignKey(
        'parametre.Nature',
        on_delete=models.CASCADE,
        related_name='details_pacs',
        null=True,
        blank=True,
        help_text='Nature du détail'
    )
    categorie = models.ForeignKey(
        'parametre.Categorie',
        on_delete=models.CASCADE,
        related_name='details_pacs',
        null=True,
        blank=True,
        help_text='Catégorie du détail'
    )
    source = models.ForeignKey(
        'parametre.Source',
        on_delete=models.CASCADE,
        related_name='details_pacs',
        null=True,
        blank=True,
        help_text='Source du détail'
    )
    periode_de_realisation = models.DateField(
        null=True,
        blank=True,
        help_text='Période de réalisation'
    )

    class Meta:
        db_table = 'details_pac'
        verbose_name = 'Détail PAC'
        verbose_name_plural = 'Détails PAC'

    def __str__(self):
        return f"Détail {self.numero_pac} - {self.uuid}"


class TraitementPac(models.Model):
    """
    Modèle pour les traitements PAC
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    details_pac = models.OneToOneField(
        DetailsPac,
        on_delete=models.CASCADE,
        related_name='traitement',
        null=True,
        blank=True,
        help_text='Détails PAC associé'
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
        verbose_name = 'Traitement PAC'
        verbose_name_plural = 'Traitements PAC'

    def __str__(self):
        return f"Traitement PAC {self.uuid} - {self.action[:50]}..."


class PacSuivi(models.Model):
    """
    Modèle pour le suivi des traitements PAC
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traitement = models.OneToOneField(
        TraitementPac, 
        on_delete=models.CASCADE, 
        related_name='suivi',
        null=True,
        blank=True,
        help_text='Traitement PAC associé'
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
        verbose_name = 'Suivi PAC'
        verbose_name_plural = 'Suivis PAC'

    def __str__(self):
        return f"Suivi PAC {self.uuid} - {self.etat_mise_en_oeuvre.nom}"
