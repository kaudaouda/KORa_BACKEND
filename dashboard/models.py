from django.db import models
from django.contrib.auth.models import User
import uuid


class Objectives(models.Model):
    """
    Modèle pour les objectifs du tableau de bord
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(
        max_length=20, 
        unique=True,
        help_text="Numéro de l'objectif (ex: OB01)"
    )
    libelle = models.CharField(
        max_length=500,
        help_text="Libellé de l'objectif (ex: Assurer à 70% la mise en œuvre du plan annuel)"
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

    def __str__(self):
        return f"{self.number} - {self.libelle}"

    def save(self, *args, **kwargs):
        """
        Génère automatiquement le numéro si non fourni
        """
        if not self.number:
            self.number = self.generate_number()
        super().save(*args, **kwargs)

    def generate_number(self):
        """
        Génère un numéro d'objectif unique (OB01, OB02, etc.)
        """
        # Compter les objectifs existants
        count = Objectives.objects.count()
        number = f"OB{count + 1:02d}"

        # Vérifier l'unicité
        while Objectives.objects.filter(number=number).exists():
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