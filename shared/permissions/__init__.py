"""
Utilitaires pour vérifier les permissions utilisateur basées sur les rôles
Security by Design : Vérification côté backend pour éviter le bypass du frontend
"""
from django.contrib.auth.models import User
from parametre.models import UserProcessusRole, Processus, Role


def is_supervisor_smi(user):
    """
    Vérifie si un utilisateur est Superviseur SMI (rôle global transverse).
    Un superviseur SMI a UserProcessusRole(is_global=True, role__code='superviseur_smi').
    Ce rôle donne accès complet à tous les processus (lecture, écriture, validation, suppression).

    Args:
        user: L'utilisateur Django

    Returns:
        bool: True si l'utilisateur est superviseur SMI actif, False sinon
    """
    if not user or not user.is_authenticated:
        return False
    return UserProcessusRole.objects.filter(
        user=user,
        is_global=True,
        role__code='superviseur_smi',
        is_active=True
    ).exists()


def is_super_admin(user):
    """
    Vérifie si un utilisateur est un super administrateur
    Un super admin est :
    1. Un utilisateur avec is_staff ET is_superuser (accès complet par défaut)
    2. OU un utilisateur qui a le rôle "admin" pour le processus "smi" ou "prs-smi"

    Les super administrateurs ont accès complet à tous les processus :
    - Peuvent lire, écrire, valider, supprimer pour tous les processus
    - Voient tous les processus
    - Aucune restriction

    Args:
        user: L'utilisateur Django

    Returns:
        bool: True si l'utilisateur est super admin, False sinon
    """
    if not user or not user.is_authenticated:
        return False

    # Security by Design : is_staff ET is_superuser = toutes les permissions
    if user.is_staff and user.is_superuser:
        return True

    # Vérifier si l'utilisateur a le rôle "admin" pour le processus "smi" ou "prs-smi"
    from django.db.models import Q
    return UserProcessusRole.objects.filter(
        Q(processus__nom__iexact='smi') | Q(processus__nom__iexact='prs-smi'),
        user=user,
        role__code='admin',
        is_active=True
    ).exists()


def can_manage_users(user):
    """
    Vérifie si un utilisateur peut accéder à la gestion des utilisateurs
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser

    Args:
        user: L'utilisateur Django

    Returns:
        bool: True si l'utilisateur peut gérer les utilisateurs, False sinon
    """
    if not user or not user.is_authenticated:
        return False

    # Security by Design : Vérifier que l'utilisateur a is_staff ET is_superuser
    return bool(user.is_staff and user.is_superuser)


def user_can_create_objectives_amendements(user, processus_uuid):
    """
    Vérifie si un utilisateur peut créer des objectifs et des amendements pour un processus

    Règles :
    - Super admin : peut créer
    - Utilisateurs avec le rôle "valider" : peuvent créer
    - Utilisateurs avec uniquement le rôle "ecrire" : NE PEUVENT PAS créer
      (ils peuvent seulement modifier les données existantes après validation)

    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus

    Returns:
        bool: True si l'utilisateur peut créer, False sinon
    """
    if not user or not user.is_authenticated:
        return False

    # ========== SUPER ADMIN / SUPERVISEUR SMI : Peut créer ==========
    if is_super_admin(user) or is_supervisor_smi(user):
        return True
    # ========== FIN BYPASS ==========

    # Convertir processus_uuid en UUID si c'est un objet Processus
    if isinstance(processus_uuid, Processus):
        processus_uuid = processus_uuid.uuid

    # Vérifier si l'utilisateur a le rôle "valider" pour ce processus
    if user_has_permission(user, processus_uuid, 'valider'):
        return True

    return False


def user_has_permission(user, processus_uuid, role_code):
    """
    Vérifie si un utilisateur a un rôle spécifique pour un processus donné

    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus (peut être un UUID string ou un objet Processus)
        role_code: Code du rôle à vérifier (ex: 'ecrire', 'lire', 'supprimer', 'valider')

    Returns:
        bool: True si l'utilisateur a le rôle, False sinon
    """
    if not user or not user.is_authenticated:
        return False

    # ========== SUPER ADMIN / SUPERVISEUR SMI : Accès complet ==========
    if is_super_admin(user) or is_supervisor_smi(user):
        return True
    # ========== FIN BYPASS ==========

    # Convertir processus_uuid en UUID si c'est un objet Processus
    if isinstance(processus_uuid, Processus):
        processus_uuid = processus_uuid.uuid
    elif isinstance(processus_uuid, str):
        try:
            import uuid
            uuid.UUID(processus_uuid)
        except (ValueError, TypeError):
            return False

    return UserProcessusRole.objects.filter(
        user=user,
        processus__uuid=processus_uuid,
        role__code=role_code,
        is_active=True
    ).exists()


def user_can_create_for_processus(user, processus_uuid):
    """Vérifie si un utilisateur peut créer (rôle "écrire") pour un processus donné."""
    return user_has_permission(user, processus_uuid, 'ecrire')


def user_can_read_for_processus(user, processus_uuid):
    """Vérifie si un utilisateur peut lire (rôle "lire") pour un processus donné."""
    return user_has_permission(user, processus_uuid, 'lire')


def user_can_delete_for_processus(user, processus_uuid):
    """Vérifie si un utilisateur peut supprimer (rôle "supprimer") pour un processus donné."""
    return user_has_permission(user, processus_uuid, 'supprimer')


def user_can_validate_for_processus(user, processus_uuid):
    """Vérifie si un utilisateur peut valider (rôle "valider") pour un processus donné."""
    return user_has_permission(user, processus_uuid, 'valider')


def get_user_processus_list(user):
    """
    Retourne la liste des UUIDs des processus où l'utilisateur a au moins un rôle actif.

    Returns:
        None  → l'utilisateur a accès à TOUS les processus (super admin ou superviseur SMI)
        list  → liste des UUIDs (strings) des processus accessibles
        []    → aucun accès
    """
    if not user or not user.is_authenticated:
        return []

    # ========== SUPER ADMIN / SUPERVISEUR SMI : Tous les processus ==========
    if can_manage_users(user) or is_super_admin(user) or is_supervisor_smi(user):
        return None
    # ========== FIN BYPASS ==========

    processus_uuids = UserProcessusRole.objects.filter(
        user=user,
        is_active=True,
        processus__isnull=False
    ).values_list('processus__uuid', flat=True).distinct()

    return list(processus_uuids)


def user_has_access_to_processus(user, processus_uuid):
    """
    Vérifie si un utilisateur a accès à un processus (au moins un rôle actif)

    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus

    Returns:
        bool: True si l'utilisateur a accès au processus, False sinon
    """
    if not user or not user.is_authenticated:
        return False

    # ========== SUPER ADMIN / SUPERVISEUR SMI : Accès à tous les processus ==========
    if can_manage_users(user) or is_super_admin(user) or is_supervisor_smi(user):
        return True
    # ========== FIN BYPASS ==========

    if isinstance(processus_uuid, Processus):
        processus_uuid = processus_uuid.uuid

    return UserProcessusRole.objects.filter(
        user=user,
        processus__uuid=processus_uuid,
        is_active=True
    ).exists()


def user_has_write_permission_anywhere(user):
    """
    Vérifie si l'utilisateur a le rôle 'ecrire' pour au moins un processus.
    Utile pour les ressources globales (comme les documents) non liées à un processus spécifique.
    """
    import logging
    logger = logging.getLogger(__name__)

    if not user or not user.is_authenticated:
        return False

    # ========== SUPER ADMIN / SUPERVISEUR SMI : Accès complet ==========
    if is_super_admin(user) or is_supervisor_smi(user):
        return True
    # ========== FIN BYPASS ==========

    try:
        try:
            role_ecrire = Role.objects.get(code='ecrire', is_active=True)
        except Role.DoesNotExist:
            logger.warning("[user_has_write_permission_anywhere] Rôle 'ecrire' non trouvé")
            return False

        return UserProcessusRole.objects.filter(
            user=user,
            role=role_ecrire,
            is_active=True
        ).exists()
    except Exception as e:
        logger.error("[user_has_write_permission_anywhere] Erreur: %s", e)
        return False


def check_permission_or_403(user, processus_uuid, role_code, error_message=None):
    """
    Vérifie une permission et retourne une réponse 403 si l'utilisateur n'a pas la permission

    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus
        role_code: Code du rôle à vérifier
        error_message: Message d'erreur personnalisé (optionnel)

    Returns:
        tuple: (has_permission: bool, error_response: Response | None)
    """
    from rest_framework.response import Response
    from rest_framework import status

    # ========== SUPER ADMIN / SUPERVISEUR SMI : Accès complet ==========
    if can_manage_users(user) or is_super_admin(user) or is_supervisor_smi(user):
        return True, None
    # ========== FIN BYPASS ==========

    if not user_has_permission(user, processus_uuid, role_code):
        default_message = f"Vous n'avez pas les permissions nécessaires ({role_code}) pour ce processus."
        message = error_message or default_message

        return False, Response({
            'success': False,
            'error': message,
            'permission_required': role_code,
            'processus_uuid': str(processus_uuid)
        }, status=status.HTTP_403_FORBIDDEN)

    return True, None
