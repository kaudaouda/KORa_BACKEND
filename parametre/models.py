from django.db import models
import uuid
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class HasActiveStatus(models.Model):
    """
    Trait abstrait pour ajouter un champ is_active aux modèles
    """
    is_active = models.BooleanField(
        default=True,
        help_text="Indique si cet élément est actif et peut être utilisé"
    )
    
    class Meta:
        abstract = True


class Nature(HasActiveStatus):
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


class Categorie(HasActiveStatus):
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


class Source(HasActiveStatus):
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


class ActionType(HasActiveStatus):
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


class EtatMiseEnOeuvre(HasActiveStatus):
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


class Appreciation(HasActiveStatus):
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


class StatutActionCDR(HasActiveStatus):
    """
    Modèle pour les statuts d'action CDR (En cours, Terminé, Suspendu, Annulé)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'statut_action_cdr'
        verbose_name = "Statut d'action CDR"
        verbose_name_plural = "Statuts d'actions CDR"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Media(models.Model):
    """
    Modèle pour les médias (fichiers)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fichier = models.FileField(upload_to='', blank=True, null=True)
    url_fichier = models.URLField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True, help_text="Description du média/fichier")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'media'
        verbose_name = 'Média'
        verbose_name_plural = 'Médias'

    def __str__(self):
        return f"Média {self.uuid}"

    @property
    def fichier_url(self):
        if self.fichier:
            try:
                return self.fichier.url
            except ValueError:
                return None
        return None

    def get_url(self):
        if self.fichier_url:
            # Éviter la duplication de /medias/ si l'URL commence déjà par /medias/
            url = self.fichier_url
            if url.startswith('/medias/medias/'):
                return url.replace('/medias/medias/', '/medias/')
            return url
        return self.url_fichier


class Direction(HasActiveStatus):
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


class SousDirection(HasActiveStatus):
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


class Service(HasActiveStatus):
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


class Versions(HasActiveStatus):
    """
    Modèle pour les versions de tableau de bord (Initial, Amendement 1, Amendement 2)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Code de la version (ex: INITIAL, AMENDEMENT_1, AMENDEMENT_2)"
    )
    nom = models.CharField(
        max_length=100,
        help_text="Nom affiché de la version (ex: Tableau Initial, Amendement 1)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description de la version"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'type_tableau'
        verbose_name = 'Version'
        verbose_name_plural = 'Versions'
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def get_display_name(self):
        """Retourne le nom d'affichage"""
        return self.nom


class Annee(HasActiveStatus):
    """
    Modèle pour les années - utilisé pour filtrer les PAC par année
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee = models.IntegerField(
        unique=True,
        help_text="Année (ex: 2024, 2025)"
    )
    libelle = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Libellé optionnel (ex: 'Année fiscale 2024')"
    )
    description = models.TextField(
        blank=True, 
        null=True,
        help_text="Description de l'année"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'annee'
        verbose_name = 'Année'
        verbose_name_plural = 'Années'
        ordering = ['-annee']  # Ordre décroissant pour avoir les années récentes en premier

    def __str__(self):
        if self.libelle:
            return f"{self.annee} - {self.libelle}"
        return str(self.annee)


class Processus(HasActiveStatus):
    """
    Modèle pour les processus (déplacé depuis l'app pac)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_processus = models.CharField(max_length=10, unique=True, blank=True)
    nom = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='processus_crees'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'processus'
        verbose_name = 'Processus'
        verbose_name_plural = 'Processus'

    def __str__(self):
        return f"{self.numero_processus} - {self.nom}"

    def save(self, *args, **kwargs):
        if not self.numero_processus:
            self.numero_processus = self.generate_numero_processus()
        super().save(*args, **kwargs)

    def generate_numero_processus(self):
        """
        Génère un numéro de processus unique (PRS01, PRS02, etc.)
        """
        # Compter les processus existants
        count = Processus.objects.count()
        numero = f"PRS{count + 1:02d}"

        # Vérifier l'unicité
        while Processus.objects.filter(numero_processus=numero).exists():
            count += 1
            numero = f"PRS{count + 1:02d}"

        return numero


class DysfonctionnementRecommandation(HasActiveStatus):
    """
    Modèle pour les dysfonctionnements et recommandations
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    cree_par = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dysfonctionnements_crees'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dysfonctionnement_recommandation'
        verbose_name = 'Dysfonctionnement/Recommandation'
        verbose_name_plural = 'Dysfonctionnements/Recommandations'

    def __str__(self):
        return self.nom


class Preuve(models.Model):
    """
    Modèle pour les preuves (Evidence) - Déplacé de pac vers parametre
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.TextField()
    medias = models.ManyToManyField(Media, related_name='preuves', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'preuve'
        verbose_name = 'Preuve'
        verbose_name_plural = 'Preuves'

    def __str__(self):
        return f"Preuve {self.uuid} - {self.description[:50]}..."


class ActivityLog(models.Model):
    """
    Modèle pour tracer les activités des utilisateurs
    """
    ACTION_CHOICES = [
        ('create', 'Création'),
        ('update', 'Modification'),
        ('delete', 'Suppression'),
        ('view', 'Consultation'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('login', 'Connexion'),
        ('logout', 'Déconnexion'),
    ]
    
    ENTITY_CHOICES = [
        ('pac', 'PAC'),
        ('traitement', 'Traitement'),
        ('suivi', 'Suivi'),
        ('processus', 'Processus'),
        ('user', 'Utilisateur'),
        ('media', 'Média'),
        ('preuve', 'Preuve'),
    ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=20, choices=ENTITY_CHOICES)
    entity_id = models.CharField(max_length=100, blank=True, null=True)
    entity_name = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_log'
        verbose_name = 'Log d\'activité'
        verbose_name_plural = 'Logs d\'activité'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['entity_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.entity_name or self.entity_type}"

    @property
    def time_ago(self):
        """
        Retourne le temps écoulé depuis la création en français
        """
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - self.created_at
        
        if diff.days > 0:
            if diff.days == 1:
                return "Il y a 1 jour"
            elif diff.days < 7:
                return f"Il y a {diff.days} jours"
            elif diff.days < 30:
                weeks = diff.days // 7
                return f"Il y a {weeks} semaine{'s' if weeks > 1 else ''}"
            else:
                months = diff.days // 30
                return f"Il y a {months} mois"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"Il y a {hours} heure{'s' if hours > 1 else ''}"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"Il y a {minutes} minute{'s' if minutes > 1 else ''}"
        else:
            return "À l'instant"

    @property
    def action_icon(self):
        """
        Retourne l'icône et la couleur selon le type d'action
        """
        icons = {
            'create': {'icon': 'C', 'color': 'blue'},
            'update': {'icon': 'M', 'color': 'green'},
            'delete': {'icon': 'S', 'color': 'red'},
            'view': {'icon': 'V', 'color': 'gray'},
            'export': {'icon': 'E', 'color': 'purple'},
            'import': {'icon': 'I', 'color': 'orange'},
            'login': {'icon': 'L', 'color': 'green'},
            'logout': {'icon': 'O', 'color': 'gray'},
        }
        return icons.get(self.action, {'icon': '?', 'color': 'gray'})

    @property
    def status_color(self):
        """
        Retourne la couleur du statut selon l'action
        """
        colors = {
            'create': 'green',
            'update': 'blue',
            'delete': 'red',
            'view': 'gray',
            'export': 'purple',
            'import': 'orange',
            'login': 'green',
            'logout': 'gray',
        }
        return colors.get(self.action, 'gray')


class NotificationSettings(models.Model):
    """
    Paramètres globaux de notification - Délai de réalisation uniquement
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Délai d'alerte pour les traitements uniquement
    traitement_delai_notice_days = models.PositiveIntegerField(
        default=7,
        help_text="Nombre de jours avant le délai pour envoyer la première notification"
    )
    
    # Fréquence des rappels après la notification initiale
    traitement_reminder_frequency_days = models.PositiveIntegerField(
        default=1,
        help_text="Fréquence des rappels après la notification initiale (en jours). 1 = chaque jour, 2 = tous les 2 jours, etc."
    )

    # Enforce singleton
    singleton_enforcer = models.BooleanField(default=True, unique=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_settings'
        verbose_name = 'Paramètre de notification'
        verbose_name_plural = 'Paramètres de notification'

    def __str__(self):
        return 'Paramètres de notification'

    @classmethod
    def get_solo(cls):
        """Retourne l'unique instance des paramètres (créée si absente)."""
        instance, _ = cls.objects.get_or_create(singleton_enforcer=True, defaults={})
        return instance


class DashboardNotificationSettings(models.Model):
    """
    Paramètres de notification pour les indicateurs des tableaux de bord
    Basés sur les fréquences (trimestre, semestre, annuelle)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Délai d'alerte avant la fin d'une période pour envoyer la première notification
    days_before_period_end = models.PositiveIntegerField(
        default=7,
        help_text="Nombre de jours avant la fin de la période pour envoyer la première notification"
    )
    
    # Délai après la fin d'une période pour envoyer une relance
    days_after_period_end = models.PositiveIntegerField(
        default=7,
        help_text="Nombre de jours après la fin de la période pour envoyer une relance si non complété"
    )
    
    # Fréquence de relance après expiration
    reminder_frequency_days = models.PositiveIntegerField(
        default=7,
        help_text="Fréquence des rappels après expiration (en jours). 1 = chaque jour, 7 = chaque semaine"
    )
    
    # Enforce singleton
    singleton_enforcer = models.BooleanField(default=True, unique=True, editable=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dashboard_notification_settings'
        verbose_name = 'Paramètre de notification tableau de bord'
        verbose_name_plural = 'Paramètres de notification tableaux de bord'

    def __str__(self):
        return 'Paramètres de notification tableau de bord'

    @classmethod
    def get_solo(cls):
        """Retourne l'unique instance des paramètres (créée si absente)."""
        instance, _ = cls.objects.get_or_create(singleton_enforcer=True, defaults={
            'days_before_period_end': 7,
            'days_after_period_end': 7,
            'reminder_frequency_days': 7
        })
        return instance




# ==================== LOG D'ENVOI DE RELANCES ====================
class EmailSettings(models.Model):
    """
    Paramètres de configuration email pour l'envoi de notifications
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Paramètres SMTP
    email_host = models.CharField(max_length=255, default='smtp.gmail.com', help_text='Serveur SMTP (ex: smtp.gmail.com)')
    email_port = models.PositiveIntegerField(default=587, help_text='Port SMTP (587 pour TLS, 465 pour SSL)')
    email_host_user = models.EmailField(help_text='Adresse email pour l\'authentification SMTP')
    email_host_password = models.CharField(max_length=255, help_text='Mot de passe pour l\'authentification SMTP')
    email_use_tls = models.BooleanField(default=True, help_text='Utiliser TLS (recommandé)')
    email_use_ssl = models.BooleanField(default=False, help_text='Utiliser SSL')
    
    # Paramètres d'envoi
    email_from_name = models.CharField(max_length=100, default='KORA', help_text='Nom affiché dans l\'expéditeur')
    email_timeout = models.PositiveIntegerField(default=30, help_text='Timeout en secondes pour l\'envoi')
    
    # Enforce singleton
    singleton_enforcer = models.BooleanField(default=True, unique=True, editable=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_settings'
        verbose_name = 'Paramètre email'
        verbose_name_plural = 'Paramètres email'

    def __str__(self):
        return f'Configuration email - {self.email_host_user}'

    @classmethod
    def get_solo(cls):
        """Retourne l'unique instance des paramètres email (créée si absente)."""
        instance, _ = cls.objects.get_or_create(singleton_enforcer=True, defaults={
            'email_host': 'smtp.gmail.com',
            'email_port': 587,
            'email_host_user': '',
            'email_host_password': '',
            'email_use_tls': True,
            'email_use_ssl': False,
            'email_from_name': 'KORA',
            'email_timeout': 30
        })
        return instance

    def get_email_config(self):
        """
        Retourne la configuration email au format Django
        """
        return {
            'EMAIL_HOST': self.email_host,
            'EMAIL_PORT': self.email_port,
            'EMAIL_HOST_USER': self.email_host_user,
            'EMAIL_HOST_PASSWORD': self.email_host_password,
            'EMAIL_USE_TLS': self.email_use_tls,
            'EMAIL_USE_SSL': self.email_use_ssl,
            'EMAIL_TIMEOUT': self.email_timeout,
            'DEFAULT_FROM_EMAIL': f'{self.email_from_name} <{self.email_host_user}>',
        }


class ReminderEmailLog(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    context_hash = models.CharField(max_length=64)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reminder_email_log'
        indexes = [
            models.Index(fields=['recipient', 'context_hash', 'sent_at'])
        ]
        verbose_name = 'Log email de relance'
        verbose_name_plural = 'Logs emails de relance'

    def __str__(self):
        return f"Relance {self.subject} -> {self.recipient} ({self.sent_at:%Y-%m-%d %H:%M})"


class Mois(models.Model):
    """
    Modèle de référence pour les mois de l'année
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.IntegerField(
        unique=True,
        help_text="Numéro du mois (1-12)"
    )
    nom = models.CharField(
        max_length=50,
        unique=True,
        help_text="Nom complet du mois (ex: Janvier, Février, etc.)"
    )
    abreviation = models.CharField(
        max_length=10,
        help_text="Abréviation du mois (première lettre: J, F, M, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mois'
        verbose_name = 'Mois'
        verbose_name_plural = 'Mois'
        ordering = ['numero']

    def __str__(self):
        return self.nom


class Frequence(models.Model):
    """
    Modèle pour les fréquences de mesure des indicateurs
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nom de la fréquence (ex: Trimestrielle, Semestrielle, Annuelle, Mensuelle, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'frequence'
        verbose_name = 'Fréquence'
        verbose_name_plural = 'Fréquences'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Periodicite(models.Model):
    """
    Modèle pour les périodicités de mesure des indicateurs
    """
    PERIODE_CHOICES = [
        # Trimestrielle (4 périodes)
        ('T1', '1er Trimestre'),
        ('T2', '2ème Trimestre'),
        ('T3', '3ème Trimestre'),
        ('T4', '4ème Trimestre'),
        # Semestrielle (2 périodes)
        ('S1', '1er Semestre'),
        ('S2', '2ème Semestre'),
        # Annuelle (1 période)
        ('A1', 'Année'),
    ]
    
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    indicateur_id = models.ForeignKey(
        'dashboard.Indicateur',
        on_delete=models.CASCADE,
        related_name='periodicites',
        help_text="Indicateur associé à cette périodicité"
    )
    periode = models.CharField(
        max_length=3,
        choices=PERIODE_CHOICES,
        default='A1',
        help_text="Période spécifique de la fréquence"
    )
    a_realiser = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Nombre d'actions à réaliser"
    )
    realiser = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Nombre d'actions réalisées"
    )
    taux = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Taux de réalisation en pourcentage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'periodicite'
        verbose_name = 'Périodicité'
        verbose_name_plural = 'Périodicités'
        ordering = ['indicateur_id', 'periode', 'created_at']
        unique_together = ['indicateur_id', 'periode']  # Un indicateur ne peut avoir qu'une seule entrée par période

    def __str__(self):
        periode_display = dict(self.PERIODE_CHOICES).get(self.periode, self.periode)
        return f"{self.indicateur_id.libelle[:30]}... - {periode_display} - {self.taux}% ({self.realiser}/{self.a_realiser})"

    def save(self, *args, **kwargs):
        """
        Calculer automatiquement le taux si les valeurs sont fournies
        """
        if self.a_realiser and self.a_realiser > 0:
            self.taux = (self.realiser / self.a_realiser) * 100
        else:
            self.taux = 0
        super().save(*args, **kwargs)

    @classmethod
    def get_periodes_for_frequence(cls, frequence_nom):
        """
        Retourne les périodes disponibles pour une fréquence donnée
        """
        # Périodes prédéfinies pour les fréquences courantes
        periodes_predefinies = {
            'Trimestrielle': [('T1', '1er Trimestre'), ('T2', '2ème Trimestre'), ('T3', '3ème Trimestre'), ('T4', '4ème Trimestre')],
            'Semestrielle': [('T2', '2ème Trimestre'), ('T4', '4ème Trimestre')],  # Seulement T2 et T4
            'Annuelle': [('T4', '4ème Trimestre')],  # Seulement T4
            'Mensuelle': [('M1', 'Janvier'), ('M2', 'Février'), ('M3', 'Mars'), ('M4', 'Avril'), ('M5', 'Mai'), ('M6', 'Juin'), ('M7', 'Juillet'), ('M8', 'Août'), ('M9', 'Septembre'), ('M10', 'Octobre'), ('M11', 'Novembre'), ('M12', 'Décembre')],
        }
        
        # Retourner les périodes prédéfinies si disponibles
        if frequence_nom in periodes_predefinies:
            return periodes_predefinies[frequence_nom]
        
        # Pour les fréquences personnalisées, retourner une période générique
        return [('P1', f'Période {frequence_nom}')]

    @classmethod
    def is_periode_allowed_for_frequence(cls, frequence_nom, periode):
        """
        Vérifie si une période est autorisée pour une fréquence donnée
        """
        allowed_periodes = cls.get_periodes_for_frequence(frequence_nom)
        return periode in [p[0] for p in allowed_periodes]

    @classmethod
    def get_periodes_choices_for_frequence(cls, frequence_nom):
        """
        Retourne les choix de périodes pour une fréquence donnée (pour les formulaires)
        """
        return cls.get_periodes_for_frequence(frequence_nom)


class Cible(models.Model):
    """
    Modèle pour les cibles des indicateurs
    """
    CONDITION_CHOICES = [
        ('≥', 'Supérieur ou égal à'),
        ('>', 'Supérieur à'),
        ('≤', 'Inférieur ou égal à'),
        ('<', 'Inférieur à'),
        ('=', 'Égal à'),
        ('≠', 'Différent de'),
    ]
    
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    valeur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valeur de la cible (ex: 70)"
    )
    condition = models.CharField(
        max_length=2,
        choices=CONDITION_CHOICES,
        help_text="Condition de comparaison (ex: ≥)"
    )
    indicateur_id = models.OneToOneField(
        'dashboard.Indicateur',
        on_delete=models.CASCADE,
        related_name='cible',
        help_text="Indicateur associé à cette cible"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cible'
        verbose_name = 'Cible'
        verbose_name_plural = 'Cibles'
        ordering = ['indicateur_id', 'created_at']

    def __str__(self):
        condition_display = dict(self.CONDITION_CHOICES).get(self.condition, self.condition)
        return f"{self.indicateur_id} - {condition_display} {self.valeur}"

    def is_objectif_atteint(self, valeur_reelle):
        """
        Vérifier si l'objectif est atteint avec une valeur réelle donnée
        """
        if self.condition == '≥':
            return valeur_reelle >= self.valeur
        elif self.condition == '>':
            return valeur_reelle > self.valeur
        elif self.condition == '≤':
            return valeur_reelle <= self.valeur
        elif self.condition == '<':
            return valeur_reelle < self.valeur
        elif self.condition == '=':
            return valeur_reelle == self.valeur
        elif self.condition == '≠':
            return valeur_reelle != self.valeur
        else:
            return False


# ==================== MODÈLES POUR LA CARTOGRAPHIE DES RISQUES ====================

class FrequenceRisque(HasActiveStatus):
    """
    Modèle pour les fréquences d'évaluation des risques
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(
        max_length=100,
        unique=True,
        help_text="Libellé de la fréquence (ex: Rare, Occasionnel, Fréquent, Très fréquent)"
    )
    valeur = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Valeur numérique de la fréquence pour le calcul de la criticité (ex: 1, 2, 3, 4, 5)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'frequence_risque'
        verbose_name = 'Fréquence Risque'
        verbose_name_plural = 'Fréquences Risque'
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class GraviteRisque(HasActiveStatus):
    """
    Modèle pour les niveaux de gravité des risques
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(
        max_length=100,
        unique=True,
        help_text="Libellé de la gravité (ex: Négligeable, Mineur, Modéré, Majeur, Critique)"
    )
    code = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Code lettre de la gravité pour le calcul de la criticité (ex: A, B, C, D, E)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gravite_risque'
        verbose_name = 'Gravité Risque'
        verbose_name_plural = 'Gravités Risque'
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class CriticiteRisque(HasActiveStatus):
    """
    Modèle pour les niveaux de criticité des risques
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(
        max_length=100,
        unique=True,
        help_text="Libellé de la criticité (ex: Faible, Moyenne, Élevée, Très élevée)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'criticite_risque'
        verbose_name = 'Criticité Risque'
        verbose_name_plural = 'Criticités Risque'
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class Risque(HasActiveStatus):
    """
    Modèle pour les types de risques
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(
        max_length=200,
        unique=True,
        help_text="Libellé du type de risque"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description du type de risque"
    )
    niveaux_risque = models.JSONField(
        default=list,
        blank=True,
        help_text="Liste des niveaux de risque associés (ex: ['5A', '5B', '5C', '4A', '4B', '3A'])"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'risque'
        verbose_name = 'Risque'
        verbose_name_plural = 'Risques'
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class VersionEvaluationCDR(HasActiveStatus):
    """
    Modèle pour les versions d'évaluation CDR (Evaluation Initiale, Réévaluation 1, Réévaluation 2, etc.)
    Permet de gérer plusieurs évaluations d'un même risque dans le temps
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nom de la version (ex: Évaluation Initiale, Réévaluation 1)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description de cette version d'évaluation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'version_evaluation_cdr'
        verbose_name = 'Version Évaluation CDR'
        verbose_name_plural = 'Versions Évaluation CDR'
        ordering = ['created_at', 'nom']

    def __str__(self):
        return self.nom

    def get_display_name(self):
        """Retourne le nom d'affichage"""
        return self.nom

# MoisAP déplacé dans activite_periodique pour résoudre les dépendances circulaires