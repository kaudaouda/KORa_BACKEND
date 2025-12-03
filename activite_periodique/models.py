from django.db import models
from django.contrib.auth.models import User
import uuid
from parametre.models import Processus


class ActivitePeriodique(models.Model):
    """
    Modèle pour les Activités Périodiques (similaire à Pac)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cree_par = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='activites_periodiques_crees'
    )
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activites_periodiques_validees',
        help_text='Utilisateur qui a validé l\'activité périodique'
    )
    is_validated = models.BooleanField(
        default=False,
        help_text='Indique que tous les détails et périodicités sont renseignés.'
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date de validation des détails et périodicités'
    )
    processus = models.ForeignKey(
        Processus, 
        on_delete=models.CASCADE, 
        related_name='activites_periodiques'
    )
    annee = models.ForeignKey(
        'parametre.Annee',
        on_delete=models.SET_NULL,
        related_name='activites_periodiques',
        null=True,
        blank=True,
        help_text='Année associée à l\'activité périodique'
    )
    type_tableau = models.ForeignKey(
        'parametre.Versions',
        on_delete=models.SET_NULL,
        related_name='activites_periodiques',
        null=True,
        blank=True,
        help_text='Version associée à l\'activité périodique (Initial, Amendement, etc.)'
    )
    initial_ref = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='amendements',
        null=True,
        blank=True,
        help_text='Référence à l\'activité périodique initiale (pour les amendements)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'activite_periodique'
        verbose_name = 'Activité Périodique'
        verbose_name_plural = 'Activités Périodiques'
        constraints = [
            models.UniqueConstraint(
                fields=['processus', 'annee', 'type_tableau', 'cree_par'],
                name='unique_activite_periodique_per_processus_annee_type_tableau_user'
            )
        ]

    def __str__(self):
        return f"Activité Périodique {self.uuid}"


class DetailsAP(models.Model):
    """
    Modèle pour les détails d'une Activité Périodique
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_ap = models.CharField(
        max_length=50, 
        null=True, 
        blank=True, 
        help_text='Numéro du détail Activité Périodique'
    )
    activite_periodique = models.ForeignKey(
        ActivitePeriodique,
        on_delete=models.CASCADE,
        related_name='details',
        help_text='Activité Périodique associée'
    )
    activites_periodiques = models.TextField(
        null=True,
        blank=True,
        help_text='Description des activités périodiques'
    )
    frequence = models.ForeignKey(
        'parametre.Frequence',
        on_delete=models.SET_NULL,
        related_name='details_ap',
        null=True,
        blank=True,
        help_text='Fréquence associée (Trimestrielle, Semestrielle, Annuelle, Mensuelle, etc.)'
    )
    # Responsabilités - un seul responsable principal (compatibilité)
    responsabilite_direction = models.ForeignKey(
        'parametre.Direction',
        on_delete=models.CASCADE,
        related_name='details_ap_responsables',
        blank=True,
        null=True,
        help_text='Direction responsable'
    )
    responsabilite_sous_direction = models.ForeignKey(
        'parametre.SousDirection',
        on_delete=models.CASCADE,
        related_name='details_ap_responsables',
        blank=True,
        null=True,
        help_text='Sous-direction responsable'
    )
    responsabilite_service = models.ForeignKey(
        'parametre.Service',
        on_delete=models.CASCADE,
        related_name='details_ap_responsables',
        blank=True,
        null=True,
        help_text='Service responsable'
    )
    # ManyToMany pour permettre plusieurs responsables en parallèle
    responsables_directions = models.ManyToManyField(
        'parametre.Direction',
        related_name='details_ap_responsables_m2m',
        blank=True
    )
    responsables_sous_directions = models.ManyToManyField(
        'parametre.SousDirection',
        related_name='details_ap_responsables_sous_m2m',
        blank=True
    )
    responsables_services = models.ManyToManyField(
        'parametre.Service',
        related_name='details_ap_responsables_services_m2m',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'details_ap'
        verbose_name = 'Détail Activité Périodique'
        verbose_name_plural = 'Détails Activités Périodiques'

    def __str__(self):
        return f"Détail AP {self.numero_ap} - {self.uuid}"


class SuivisAP(models.Model):
    """
    Modèle pour les suivis des activités périodiques par mois
    Chaque suivi est associé à un détail AP, un mois et un état de mise en œuvre
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    details_ap = models.ForeignKey(
        DetailsAP,
        on_delete=models.CASCADE,
        related_name='suivis',
        help_text='Détail Activité Périodique associé'
    )
    mois = models.ForeignKey(
        'parametre.Mois',
        on_delete=models.CASCADE,
        related_name='suivis_ap',
        help_text='Mois de référence'
    )
    etat_mise_en_oeuvre = models.ForeignKey(
        'parametre.EtatMiseEnOeuvre',
        on_delete=models.SET_NULL,
        related_name='suivis_ap',
        null=True,
        blank=True,
        help_text='État de mise en œuvre pour ce mois (Réalisée, Non réalisée, etc.)'
    )
    livrable = models.TextField(
        blank=True,
        null=True,
        help_text='Livrable associé à ce suivi'
    )
    date_realisation = models.DateField(
        blank=True,
        null=True,
        help_text='Date de réalisation effective'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suivis_ap'
        verbose_name = 'Suivi AP'
        verbose_name_plural = 'Suivis AP'
        unique_together = ['details_ap', 'mois']  # Un seul suivi par mois par détail AP
        ordering = ['details_ap', 'mois__numero']

    def __str__(self):
        return f"{self.details_ap.numero_ap} - {self.mois.nom} ({self.etat_mise_en_oeuvre.nom if self.etat_mise_en_oeuvre else 'Non défini'})"
