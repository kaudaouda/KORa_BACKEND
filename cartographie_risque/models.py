"""
Modèles pour l'application Cartographie de Risque
"""
from django.db import models
from django.contrib.auth.models import User
from parametre.models import Processus, Versions, Media, FrequenceRisque, GraviteRisque, CriticiteRisque, Risque, Direction
import uuid


class BaseModel(models.Model):
    """Modèle de base avec UUID et timestamps"""
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class CDR(BaseModel):
    """
    Modèle pour la Cartographie des Risques (CDR)
    """
    annee = models.PositiveIntegerField(
        help_text="Année de la cartographie des risques (ex: 2025)"
    )
    processus = models.ForeignKey(
        Processus,
        on_delete=models.CASCADE,
        related_name='cdrs',
        help_text="Processus associé à la cartographie"
    )
    type_tableau = models.ForeignKey(
        Versions,
        on_delete=models.CASCADE,
        related_name='cdrs',
        help_text="Type de tableau (Initial, Amendement, etc.)"
    )
    is_validated = models.BooleanField(
        default=False,
        help_text="Indique si la cartographie est validée"
    )
    initial_ref = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='amendements',
        null=True,
        blank=True,
        help_text='Référence au CDR initial (pour les amendements)'
    )
    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cdrs_crees',
        help_text="Utilisateur qui a créé la cartographie"
    )
    valide_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cdrs_valides',
        help_text="Utilisateur qui a validé la cartographie"
    )
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de validation de la cartographie"
    )

    class Meta:
        db_table = 'cdr'
        verbose_name = 'Cartographie des Risques'
        verbose_name_plural = 'Cartographies des Risques'
        ordering = ['-annee', 'processus']
        unique_together = ['annee', 'processus', 'type_tableau']

    def __str__(self):
        return f"CDR {self.annee} - {self.processus.nom} - {self.type_tableau.nom}"


class DetailsCDR(BaseModel):
    """
    Modèle pour les détails de la Cartographie des Risques
    """
    numero_cdr = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Numéro d'identification du détail CDR"
    )
    activites = models.TextField(
        null=True,
        blank=True,
        help_text="Activités concernées"
    )
    objectifs = models.TextField(
        null=True,
        blank=True,
        help_text="Objectifs visés"
    )
    evenements_indesirables_risques = models.TextField(
        null=True,
        blank=True,
        help_text="Événements indésirables et risques identifiés"
    )
    causes = models.TextField(
        null=True,
        blank=True,
        help_text="Causes des risques"
    )
    consequences = models.TextField(
        null=True,
        blank=True,
        help_text="Conséquences potentielles"
    )
    cdr = models.ForeignKey(
        CDR,
        on_delete=models.CASCADE,
        related_name='details',
        help_text="Cartographie des risques associée"
    )

    class Meta:
        db_table = 'details_cdr'
        verbose_name = 'Détail CDR'
        verbose_name_plural = 'Détails CDR'
        ordering = ['numero_cdr', 'created_at']

    def __str__(self):
        return f"Detail CDR {self.numero_cdr} - {self.cdr}"


class EvaluationRisque(BaseModel):
    """
    Modèle pour l'évaluation des risques
    """
    details_cdr = models.ForeignKey(
        DetailsCDR,
        on_delete=models.CASCADE,
        related_name='evaluations',
        help_text="Détail CDR associé"
    )
    frequence = models.ForeignKey(
        FrequenceRisque,
        on_delete=models.CASCADE,
        related_name='evaluations',
        null=True,
        blank=True,
        help_text="Fréquence du risque"
    )
    gravite = models.ForeignKey(
        GraviteRisque,
        on_delete=models.CASCADE,
        related_name='evaluations',
        null=True,
        blank=True,
        help_text="Gravité du risque"
    )
    criticite = models.ForeignKey(
        CriticiteRisque,
        on_delete=models.CASCADE,
        related_name='evaluations',
        null=True,
        blank=True,
        help_text="Criticité du risque"
    )
    risque = models.ForeignKey(
        Risque,
        on_delete=models.CASCADE,
        related_name='evaluations',
        null=True,
        blank=True,
        help_text="Type de risque"
    )

    class Meta:
        db_table = 'evaluation_risque'
        verbose_name = 'Évaluation des Risques'
        verbose_name_plural = 'Évaluations des Risques'
        ordering = ['details_cdr', 'created_at']

    def __str__(self):
        return f"Évaluation {self.risque.libelle} - {self.details_cdr.numero_cdr}"


class PlanAction(BaseModel):
    """
    Modèle pour les plans d'action
    """
    details_cdr = models.ForeignKey(
        DetailsCDR,
        on_delete=models.CASCADE,
        related_name='plans_action',
        help_text="Détail CDR associé"
    )
    actions_mesures = models.TextField(
        help_text="Actions et mesures à mettre en œuvre"
    )
    responsable = models.ForeignKey(
        Direction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plans_action_responsable',
        help_text="Responsable de la mise en œuvre (Direction)"
    )
    delai_realisation = models.DateField(
        null=True,
        blank=True,
        help_text="Délai de réalisation prévu"
    )

    class Meta:
        db_table = 'plan_action'
        verbose_name = 'Plan d\'Action'
        verbose_name_plural = 'Plans d\'Action'
        ordering = ['details_cdr', 'delai_realisation', 'created_at']

    def __str__(self):
        return f"Plan d'action - {self.details_cdr.numero_cdr}"


class SuiviAction(BaseModel):
    """
    Modèle pour le suivi des actions
    """
    STATUT_CHOICES = [
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('suspendu', 'Suspendu'),
        ('annule', 'Annulé'),
    ]
    
    plan_action = models.ForeignKey(
        PlanAction,
        on_delete=models.CASCADE,
        related_name='suivis',
        help_text="Plan d'action associé"
    )
    date_realisation = models.DateField(
        null=True,
        blank=True,
        help_text="Date de réalisation effective"
    )
    statut_action = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='en_cours',
        help_text="Statut de l'action"
    )
    date_cloture = models.DateField(
        null=True,
        blank=True,
        help_text="Date de clôture de l'action"
    )
    element_preuve = models.ForeignKey(
        'parametre.Preuve',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suivis_actions',
        help_text="Élément de preuve (peut contenir plusieurs médias)"
    )
    critere_efficacite_objectif_vise = models.TextField(
        blank=True,
        null=True,
        help_text="Critère d'efficacité et objectif visé"
    )
    resultats_mise_en_oeuvre = models.TextField(
        blank=True,
        null=True,
        help_text="Résultats de la mise en œuvre des actions"
    )

    class Meta:
        db_table = 'suivi_action'
        verbose_name = 'Suivi d\'Action'
        verbose_name_plural = 'Suivis d\'Actions'
        ordering = ['plan_action', '-date_realisation', 'created_at']

    def __str__(self):
        return f"Suivi - {self.plan_action} - {self.get_statut_action_display()}"

