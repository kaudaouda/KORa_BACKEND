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
        blank=True,
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
    Tableau de bord par année et processus.
    num_amendement=0 → Tableau Initial, num_amendement=N → Amendement N (illimité).
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee = models.PositiveIntegerField(help_text="Année du tableau de bord (ex: 2025)")
    processus = models.ForeignKey(
        Processus,
        on_delete=models.CASCADE,
        related_name='tableaux_bord'
    )
    num_amendement = models.PositiveIntegerField(
        default=0,
        help_text="0 = Tableau Initial, 1 = Amendement 1, N = Amendement N"
    )
    initial_ref = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='amendements',
        null=True,
        blank=True
    )
    raison_amendement = models.TextField(
        null=True,
        blank=True,
        help_text="Raison de création de l'amendement"
    )
    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tableaux_bord_crees'
    )
    is_validated = models.BooleanField(
        default=False,
        help_text="Indique si le tableau de bord est validé pour la saisie des trimestres"
    )
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de validation du tableau"
    )
    valide_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tableaux_valides',
        help_text="Utilisateur qui a validé le tableau"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tableau_bord'
        verbose_name = 'Tableau de bord'
        verbose_name_plural = 'Tableaux de bord'
        constraints = [
            models.UniqueConstraint(
                fields=['annee', 'processus', 'num_amendement'],
                name='uniq_tableau_per_annee_processus_num_amendement'
            )
        ]
        ordering = ['-annee', 'processus__numero_processus', 'num_amendement']

    @property
    def is_initial(self):
        return self.num_amendement == 0

    @property
    def nom_version(self):
        if self.num_amendement == 0:
            return "Tableau Initial"
        return f"Amendement {self.num_amendement}"

    def __str__(self):
        return f"{self.processus.nom} - {self.annee} - {self.nom_version}"

    def clean(self):
        """
        Validation : un amendement doit avoir un initial_ref pointant vers num_amendement=0.
        Auto-assigne initial_ref si absent.
        """
        if self.num_amendement > 0:
            if not self.initial_ref:
                initial = TableauBord.objects.filter(
                    annee=self.annee,
                    processus=self.processus,
                    num_amendement=0
                ).first()
                if not initial:
                    raise ValidationError(
                        "Aucun tableau de bord initial n'existe pour ce processus et cette année."
                    )
                self.initial_ref = initial

            if self.initial_ref.num_amendement != 0:
                raise ValidationError({
                    'initial_ref': 'La référence doit pointer vers un tableau initial (num_amendement=0).'
                })

            # Le précédent amendement doit exister
            if self.num_amendement > 1:
                precedent_existe = TableauBord.objects.filter(
                    annee=self.annee,
                    processus=self.processus,
                    num_amendement=self.num_amendement - 1
                ).exists()
                if not precedent_existe:
                    raise ValidationError(
                        f"L'amendement {self.num_amendement - 1} doit exister avant de créer "
                        f"l'amendement {self.num_amendement}."
                    )
        else:
            self.initial_ref = None

    def has_amendements(self):
        """Vérifie si ce tableau a au moins un amendement suivant."""
        return TableauBord.objects.filter(
            annee=self.annee,
            processus=self.processus,
            num_amendement=self.num_amendement + 1
        ).exists()

    def save(self, *args, **kwargs):
        """
        Validation avant sauvegarde
        """
        self.full_clean()
        super().save(*args, **kwargs)