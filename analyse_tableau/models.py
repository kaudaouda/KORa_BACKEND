from django.db import models
from django.contrib.auth.models import User
import uuid

from dashboard.models import TableauBord
from parametre.models import (
    Direction,
    SousDirection,
    Preuve,
    EtatMiseEnOeuvre,
    Appreciation,
    Periodicite,
)


class AnalyseTableau(models.Model):
    """
    Une (et une seule) analyse par TableauBord (INITIAL, AMENDEMENT_1, AMENDEMENT_2)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tableau_bord = models.OneToOneField(
        TableauBord,
        on_delete=models.CASCADE,
        related_name='analyse_tableau',
        help_text="Tableau de bord concerné par cette analyse"
    )

    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='analyses_tableau_creees',
        help_text="Utilisateur qui a créé l'analyse"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analyse_tableau'
        verbose_name = 'Analyse du tableau'
        verbose_name_plural = 'Analyses des tableaux'

    def __str__(self):
        return f"Analyse {self.tableau_bord}"


class AnalyseLigne(models.Model):
    """
    Ligne d'analyse (un objectif non atteint) dans une AnalyseTableau.
    Pour une cause (ligne), il y aura plusieurs actions liées.
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    analyse_tableau = models.ForeignKey(
        AnalyseTableau,
        on_delete=models.CASCADE,
        related_name='lignes',
        help_text='Analyse à laquelle appartient cette ligne'
    )

    periode = models.CharField(
        max_length=10,
        choices=Periodicite.PERIODE_CHOICES,
        blank=True,
        null=True,
        help_text="Trimestre / période de l'analyse (T1, T2, ...)"
    )

    objectif_non_atteint = models.TextField(
        help_text="Description de l'objectif non atteint"
    )

    cible = models.TextField(
        blank=True,
        null=True,
        help_text='Cible (texte libre)'
    )

    resultat = models.TextField(
        blank=True,
        null=True,
        help_text='Résultat constaté (texte libre)'
    )

    causes = models.TextField(
        blank=True,
        null=True,
        help_text="Causes de la non atteinte de l'objectif"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analyse_ligne'
        verbose_name = "Ligne d'analyse"
        verbose_name_plural = "Lignes d'analyse"
        constraints = [
            models.UniqueConstraint(
                fields=['analyse_tableau', 'periode'],
                name='unique_ligne_per_analyse_tableau_periode'
            )
        ]

    def __str__(self):
        return f"Ligne analyse {self.uuid} - {self.objectif_non_atteint[:50]}..."


class AnalyseAction(models.Model):
    """
    Action liée à une cause (ligne d'analyse).
    Pour une cause on peut avoir plusieurs actions.
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ligne = models.ForeignKey(
        AnalyseLigne,
        on_delete=models.CASCADE,
        related_name='actions',
        help_text="Ligne d'analyse (cause) associée"
    )

    action = models.TextField(
        help_text="Description de l'action à mener"
    )

    # Responsables (comme dans TraitementPac)
    responsables_directions = models.ManyToManyField(
        Direction,
        related_name='analyses_actions_responsables_directions',
        blank=True,
        help_text='Directions responsables de cette action'
    )
    responsables_sous_directions = models.ManyToManyField(
        SousDirection,
        related_name='analyses_actions_responsables_sous_directions',
        blank=True,
        help_text='Sous-directions responsables de cette action'
    )

    # Délai théorique
    delai_realisation = models.DateField(
        null=True,
        blank=True,
        help_text="Délai prévu pour la réalisation de l'action"
    )

    # État et date réelle de réalisation
    etat_mise_en_oeuvre = models.ForeignKey(
        EtatMiseEnOeuvre,
        on_delete=models.SET_NULL,
        related_name='analyses_actions',
        null=True,
        blank=True,
        help_text="État de mise en œuvre de l'action"
    )

    date_realisation = models.DateField(
        null=True,
        blank=True,
        help_text='Date effective de réalisation (si réalisée)'
    )

    # Preuves (1 Preuve qui contient plusieurs médias)
    preuve = models.ForeignKey(
        Preuve,
        on_delete=models.SET_NULL,
        related_name='analyses_actions',
        null=True,
        blank=True,
        help_text="Preuve(s) associée(s) à l'action"
    )

    # Évaluation et commentaire
    evaluation = models.ForeignKey(
        Appreciation,
        on_delete=models.SET_NULL,
        related_name='analyses_actions',
        null=True,
        blank=True,
        help_text="Évaluation de l'efficacité de l'action"
    )

    commentaire = models.TextField(
        blank=True,
        null=True,
        help_text='Commentaire complémentaire'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analyse_action'
        verbose_name = "Action d'analyse"
        verbose_name_plural = "Actions d'analyse"

    def __str__(self):
        return f"Action analyse {self.uuid} - {self.action[:50]}..."
