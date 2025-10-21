from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import uuid
from parametre.models import Processus


class Objectives(models.Model):
    """
    Modèle pour les objectifs du tableau de bord
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(
        max_length=20,
        help_text="Numéro de l'objectif (ex: OB01)"
    )
    libelle = models.CharField(
        max_length=500,
        help_text="Libellé de l'objectif (ex: Assurer à 70% la mise en œuvre du plan annuel)"
    )
    tableau_bord = models.ForeignKey(
        'dashboard.TableauBord',
        on_delete=models.CASCADE,
        related_name='objectives',
        null=True,
        blank=True,
        help_text="Tableau de bord auquel appartient cet objectif"
    )
    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='objectives_crees',
        help_text="Utilisateur qui a créé l'objectif"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'objectives'
        verbose_name = 'Objectif'
        verbose_name_plural = 'Objectifs'
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(
                fields=['tableau_bord', 'number'], 
                name='uniq_objective_number_per_tableau',
                condition=models.Q(tableau_bord__isnull=False)
            )
        ]

    def __str__(self):
        return f"{self.number} - {self.libelle}"

    def save(self, *args, **kwargs):
        """
        Génère automatiquement le numéro si non fourni
        """
        if not self.number:
            # S'assurer que tableau_bord est défini avant de générer le numéro
            if not self.tableau_bord:
                raise ValueError("tableau_bord est requis pour créer un objectif")
            self.number = self.generate_number()
        super().save(*args, **kwargs)

    def generate_number(self):
        """
        Génère un numéro d'objectif unique (OB01, OB02, etc.)
        """
        # Compter les objectifs existants du même tableau
        if not self.tableau_bord:
            # Par sécurité, mais en pratique tableau_bord est requis
            count = Objectives.objects.count()
            number = f"OB{count + 1:02d}"
            # Vérifier l'unicité globalement
            while Objectives.objects.filter(number=number).exists():
                count += 1
                number = f"OB{count + 1:02d}"
        else:
            count = Objectives.objects.filter(tableau_bord=self.tableau_bord).count()
            number = f"OB{count + 1:02d}"
            # Vérifier l'unicité dans le même tableau
            while Objectives.objects.filter(tableau_bord=self.tableau_bord, number=number).exists():
                count += 1
                number = f"OB{count + 1:02d}"

        return number


class Indicateur(models.Model):
    """
    Modèle pour les indicateurs du tableau de bord
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(
        max_length=500,
        help_text="Libellé de l'indicateur (ex: Taux de mise en œuvre des actions du plan ANAC 2025)"
    )
    objective_id = models.ForeignKey(
        Objectives,
        on_delete=models.CASCADE,
        related_name='indicateurs',
        help_text="Objectif associé à cet indicateur"
    )
    frequence_id = models.ForeignKey(
        'parametre.Frequence',
        on_delete=models.CASCADE,
        related_name='indicateurs',
        null=True,
        blank=True,
        help_text="Fréquence de mesure de cet indicateur"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'indicateur'
        verbose_name = 'Indicateur'
        verbose_name_plural = 'Indicateurs'
        ordering = ['objective_id', 'libelle']

    def __str__(self):
        return f"{self.objective_id.number} - {self.libelle}"


class Observation(models.Model):
    """
    Modèle pour les observations des indicateurs
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.TextField(
        help_text="Libellé de l'observation"
    )
    indicateur_id = models.OneToOneField(
        Indicateur,
        on_delete=models.CASCADE,
        related_name='observation',
        help_text="Indicateur associé à cette observation"
    )
    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='observations_creees',
        help_text="Utilisateur qui a créé l'observation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'observation'
        verbose_name = 'Observation'
        verbose_name_plural = 'Observations'
        ordering = ['indicateur_id', 'created_at']

    def __str__(self):
        return f"Observation pour {self.indicateur_id}"


class TableauBord(models.Model):
    """
    Tableau de bord par année et processus, avec types: Initial, Amendement 1, Amendement 2
    """
    TYPE_CHOICES = [
        ('INITIAL', 'Initial'),
        ('AMENDEMENT_1', 'Amendement 1'),
        ('AMENDEMENT_2', 'Amendement 2'),
    ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee = models.PositiveIntegerField(help_text="Année du tableau de bord (ex: 2025)")
    processus = models.ForeignKey(
        Processus,
        on_delete=models.CASCADE,
        related_name='tableaux_bord'
    )
    type_tableau = models.CharField(max_length=20, choices=TYPE_CHOICES, default='INITIAL')
    initial_ref = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='amendements',
        null=True,
        blank=True
    )
    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tableaux_bord_crees'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tableau_bord'
        verbose_name = 'Tableau de bord'
        verbose_name_plural = 'Tableaux de bord'
        constraints = [
            models.UniqueConstraint(
                fields=['annee', 'processus'],
                condition=models.Q(type_tableau='INITIAL'),
                name='uniq_initial_par_annee_processus'
            ),
            models.UniqueConstraint(
                fields=['annee', 'processus'],
                condition=models.Q(type_tableau='AMENDEMENT_1'),
                name='uniq_amendement1_par_annee_processus'
            ),
            models.UniqueConstraint(
                fields=['annee', 'processus'],
                condition=models.Q(type_tableau='AMENDEMENT_2'),
                name='uniq_amendement2_par_annee_processus'
            ),
        ]
        ordering = ['-annee', 'processus__numero_processus', 'type_tableau']

    def __str__(self):
        return f"{self.processus.nom} - {self.annee} - {self.get_type_tableau_display()}"

    def clean(self):
        # Les amendements doivent référencer l'initial correspondant
        if self.type_tableau != 'INITIAL':
            initial = TableauBord.objects.filter(
                annee=self.annee,
                processus=self.processus,
                type_tableau='INITIAL'
            ).first()
            if not initial:
                raise ValidationError("Aucun tableau de bord initial n'existe pour ce processus et cette année.")
            if not self.initial_ref:
                self.initial_ref = initial
        else:
            self.initial_ref = None

        # Optionnel: empêcher Amendement 2 sans Amendement 1
        if self.type_tableau == 'AMENDEMENT_2':
            has_a1 = TableauBord.objects.filter(
                annee=self.annee,
                processus=self.processus,
                type_tableau='AMENDEMENT_1'
            ).exists()
            if not has_a1:
                raise ValidationError("Amendement 2 nécessite un Amendement 1 existant.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)