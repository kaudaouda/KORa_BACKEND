from django.db import models
import uuid
from django.contrib.auth.models import User


class Nature(models.Model):
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


class Categorie(models.Model):
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


class Source(models.Model):
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


class ActionType(models.Model):
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


class EtatMiseEnOeuvre(models.Model):
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


class Appreciation(models.Model):
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


class Media(models.Model):
    """
    Modèle pour les médias (fichiers)
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fichier = models.FileField(upload_to='', blank=True, null=True)
    url_fichier = models.URLField(max_length=500, blank=True, null=True)
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


class Direction(models.Model):
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


class SousDirection(models.Model):
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


class Service(models.Model):
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


class Processus(models.Model):
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