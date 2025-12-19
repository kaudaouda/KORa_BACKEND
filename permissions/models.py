"""
Modèles pour le système générique de gestion des permissions
Supporte plusieurs applications : CDR, Dashboard, PAC, etc.
"""
from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone


class PermissionAction(models.Model):
    """
    Catalogue des actions possibles sur les entités
    Générique pour toutes les applications (CDR, Dashboard, PAC, etc.)
    """
    id = models.AutoField(primary_key=True)
    app_name = models.CharField(
        max_length=50,
        help_text="Nom de l'application (ex: 'cdr', 'dashboard', 'pac')"
    )
    code = models.CharField(
        max_length=50,
        help_text="Code unique de l'action (ex: 'create_cdr', 'update_tableau')"
    )
    nom = models.CharField(
        max_length=100,
        help_text="Nom de l'action (ex: 'Créer CDR', 'Modifier Tableau')"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description de l'action"
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Catégorie (ex: 'main', 'details', 'evaluation', 'plan_action')"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indique si cette action est active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'permission_action'
        verbose_name = 'Action de Permission'
        verbose_name_plural = 'Actions de Permissions'
        unique_together = [('app_name', 'code')]
        indexes = [
            models.Index(fields=['app_name', 'code', 'is_active']),
            models.Index(fields=['app_name', 'category']),
        ]
        ordering = ['app_name', 'code']

    def __str__(self):
        return f"{self.app_name}.{self.code} - {self.nom}"


class RolePermissionMapping(models.Model):
    """
    Mapping entre les rôles et les permissions
    Définit quelles permissions chaque rôle accorde
    Générique pour toutes les applications
    """
    id = models.AutoField(primary_key=True)
    role = models.ForeignKey(
        'parametre.Role',
        on_delete=models.CASCADE,
        related_name='permission_mappings',
        help_text="Rôle concerné"
    )
    permission_action = models.ForeignKey(
        PermissionAction,
        on_delete=models.CASCADE,
        related_name='role_mappings',
        help_text="Action de permission concernée"
    )
    granted = models.BooleanField(
        default=True,
        help_text="Ce rôle accorde-t-il cette permission ?"
    )
    conditions = models.JSONField(
        null=True,
        blank=True,
        help_text="Conditions contextuelles (ex: can_edit_when_validated, can_edit_only_own)"
    )
    priority = models.IntegerField(
        default=0,
        help_text="Priorité si plusieurs mappings pour le même rôle"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indique si ce mapping est actif"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'role_permission_mapping'
        verbose_name = 'Mapping Rôle-Permission'
        verbose_name_plural = 'Mappings Rôle-Permission'
        unique_together = [('role', 'permission_action')]
        indexes = [
            models.Index(fields=['role', 'granted', 'is_active']),
            models.Index(fields=['permission_action', 'granted']),
        ]
        ordering = ['role', 'priority', 'permission_action']

    def __str__(self):
        status = "Accorde" if self.granted else "Refuse"
        return f"{self.role.nom} - {self.permission_action} ({status})"


class AppPermission(models.Model):
    """
    Permissions résolues et calculées pour un utilisateur
    Généré automatiquement depuis USERPROCESSUSROLE + ROLE_PERMISSION_MAPPING
    Générique pour toutes les applications
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='app_permissions',
        db_index=True,
        help_text="Utilisateur concerné"
    )
    processus = models.ForeignKey(
        'parametre.Processus',
        on_delete=models.CASCADE,
        related_name='app_permissions',
        db_index=True,
        help_text="Processus concerné"
    )
    app_name = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Nom de l'application (ex: 'cdr', 'dashboard', 'pac')"
    )
    permission_action = models.ForeignKey(
        PermissionAction,
        on_delete=models.CASCADE,
        related_name='app_permissions',
        help_text="Action de permission concernée"
    )

    # Permissions principales (Boolean)
    can_create = models.BooleanField(default=False)
    can_read = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_validate = models.BooleanField(default=False)
    can_create_amendement = models.BooleanField(default=False)

    # Permissions sous-entités (Boolean)
    can_manage_details = models.BooleanField(default=False)
    can_manage_evaluations = models.BooleanField(default=False)
    can_manage_plans_action = models.BooleanField(default=False)
    can_manage_suivis = models.BooleanField(default=False)

    # Conditions contextuelles (Boolean)
    can_edit_when_validated = models.BooleanField(
        default=False,
        help_text="Peut modifier même si l'entité est validée"
    )
    can_edit_only_own = models.BooleanField(
        default=False,
        help_text="Peut modifier seulement ses propres créations"
    )
    can_delete_only_own = models.BooleanField(
        default=False,
        help_text="Peut supprimer seulement ses propres créations"
    )
    can_validate_own = models.BooleanField(
        default=False,
        help_text="Peut valider ses propres créations"
    )

    # Validité temporelle
    date_debut = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Début de validité de la permission"
    )
    date_fin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fin de validité de la permission"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Indique si cette permission est active"
    )

    # Métadonnées
    source_type = models.CharField(
        max_length=50,
        default='role_mapping',
        help_text="Source: 'role_mapping' ou 'custom_override'"
    )
    source_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Référence à USERPROCESSUSROLE ou PERMISSION_OVERRIDE"
    )
    last_calculated_at = models.DateTimeField(
        auto_now=True,
        help_text="Quand cette permission a été calculée (pour nettoyage cache)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_permission'
        verbose_name = 'Permission Application'
        verbose_name_plural = 'Permissions Applications'
        unique_together = [('user', 'processus', 'app_name', 'permission_action')]
        indexes = [
            models.Index(fields=['user', 'processus', 'app_name', 'is_active']),
            models.Index(fields=['user', 'app_name', 'is_active']),
            models.Index(fields=['app_name', 'is_active']),
            models.Index(fields=['last_calculated_at']),
        ]
        ordering = ['user', 'app_name', 'processus', 'permission_action']

    def is_valid_now(self):
        """Vérifie si la permission est valide à l'instant T"""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.date_debut and now < self.date_debut:
            return False
        if self.date_fin and now > self.date_fin:
            return False
        return True

    def __str__(self):
        return f"{self.user.username} - {self.app_name} - {self.processus.nom} - {self.permission_action.code}"


class PermissionOverride(models.Model):
    """
    Permissions personnalisées qui overrident les permissions des rôles
    Générique pour toutes les applications
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='permission_overrides',
        db_index=True,
        help_text="Utilisateur concerné"
    )
    processus = models.ForeignKey(
        'parametre.Processus',
        on_delete=models.CASCADE,
        related_name='permission_overrides',
        db_index=True,
        help_text="Processus concerné"
    )
    app_name = models.CharField(
        max_length=50,
        help_text="Nom de l'application (ex: 'cdr', 'dashboard', 'pac')"
    )
    permission_action = models.ForeignKey(
        PermissionAction,
        on_delete=models.CASCADE,
        related_name='overrides',
        help_text="Action de permission concernée"
    )

    granted = models.BooleanField(
        help_text="Permission accordée (true) ou refusée (false)"
    )

    conditions = models.JSONField(
        null=True,
        blank=True,
        help_text="Conditions spécifiques pour cet override"
    )

    raison = models.TextField(
        help_text="Pourquoi cette permission personnalisée (audit)"
    )

    # Validité temporelle
    date_debut = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Début de validité"
    )
    date_fin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fin de validité"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Indique si cet override est actif"
    )

    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='overrides_crees',
        help_text="Qui a créé cette permission"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'permission_override'
        verbose_name = 'Permission Personnalisée'
        verbose_name_plural = 'Permissions Personnalisées'
        unique_together = [('user', 'processus', 'app_name', 'permission_action')]
        indexes = [
            models.Index(fields=['user', 'processus', 'app_name', 'is_active']),
            models.Index(fields=['cree_par', 'created_at']),
        ]
        ordering = ['user', 'app_name', 'processus', 'permission_action']

    def __str__(self):
        status = "Accordée" if self.granted else "Refusée"
        return f"{self.user.username} - {self.app_name} - {status} ({self.permission_action.code})"


class PermissionAudit(models.Model):
    """
    Traçabilité de toutes les vérifications de permissions
    Générique pour toutes les applications
    """
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='permission_audits',
        db_index=True,
        help_text="Utilisateur concerné"
    )
    app_name = models.CharField(
        max_length=50,
        help_text="Nom de l'application (ex: 'cdr', 'dashboard', 'pac')"
    )
    action = models.CharField(
        max_length=50,
        help_text="Code de l'action demandée (ex: 'create_cdr', 'update_tableau')"
    )
    processus = models.ForeignKey(
        'parametre.Processus',
        on_delete=models.CASCADE,
        related_name='permission_audits',
        help_text="Processus concerné"
    )
    entity_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID de l'entité concernée (CDR, Tableau, PAC, etc.)"
    )
    entity_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type d'entité (ex: 'cdr', 'tableau', 'pac')"
    )

    granted = models.BooleanField(
        db_index=True,
        help_text="Permission accordée (true) ou refusée (false)"
    )
    reason = models.TextField(
        null=True,
        blank=True,
        help_text="Raison du refus si applicable"
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP de la requête"
    )
    user_agent = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="User agent du navigateur"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Quand la vérification a eu lieu"
    )

    resolution_method = models.CharField(
        max_length=50,
        default='db',
        help_text="Méthode de résolution: 'cache', 'db', 'override', 'super_admin'"
    )
    execution_time_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Temps d'exécution en millisecondes"
    )
    cache_hit = models.BooleanField(
        default=False,
        help_text="Cache utilisé ou non"
    )

    class Meta:
        db_table = 'permission_audit'
        verbose_name = 'Audit de Permission'
        verbose_name_plural = 'Audits de Permissions'
        indexes = [
            models.Index(fields=['user', 'app_name', 'timestamp']),
            models.Index(fields=['app_name', 'action', 'granted']),
            models.Index(fields=['entity_type', 'entity_id', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        status = "Accordée" if self.granted else "Refusée"
        return f"{self.user.username} - {self.app_name}.{self.action} - {status} - {self.timestamp}"
