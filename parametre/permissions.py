"""
Utilitaires pour vérifier les permissions utilisateur basées sur les rôles
Security by Design : Vérification côté backend pour éviter le bypass du frontend
"""
from django.contrib.auth.models import User
from .models import UserProcessusRole, Processus, Role


def is_super_admin(user):
    """
    Vérifie si un utilisateur est un super administrateur
    (processus "smi" ou "prs-smi" + rôle "admin")
    
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
    
    # Vérifier si l'utilisateur a le rôle "admin" pour le processus "smi" ou "prs-smi"
    # Utiliser Q objects pour faire un OR avec iexact (case-insensitive)
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
    
    # ========== SUPER ADMIN : Peut créer ==========
    if is_super_admin(user):
        return True
    # ========== FIN SUPER ADMIN ==========
    
    # Convertir processus_uuid en UUID si c'est un objet Processus
    if isinstance(processus_uuid, Processus):
        processus_uuid = processus_uuid.uuid
    
    # Vérifier si l'utilisateur a le rôle "valider" pour ce processus
    # Les utilisateurs avec "valider" peuvent créer des objectifs et amendements
    if user_has_permission(user, processus_uuid, 'valider'):
        return True
    
    # Les utilisateurs avec uniquement "ecrire" NE PEUVENT PAS créer
    # (ils peuvent seulement modifier les données existantes)
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
    
    # ========== SUPER ADMIN : Accès complet sans restriction ==========
    if is_super_admin(user):
        return True
    # ========== FIN SUPER ADMIN ==========
    
    # Convertir processus_uuid en UUID si c'est un objet Processus
    if isinstance(processus_uuid, Processus):
        processus_uuid = processus_uuid.uuid
    elif isinstance(processus_uuid, str):
        try:
            # S'assurer que c'est un UUID valide
            import uuid
            uuid.UUID(processus_uuid)
        except (ValueError, TypeError):
            return False
    
    # Vérifier si l'utilisateur a le rôle spécifié pour ce processus
    has_permission = UserProcessusRole.objects.filter(
        user=user,
        processus__uuid=processus_uuid,
        role__code=role_code,
        is_active=True
    ).exists()
    
    return has_permission


def user_can_create_for_processus(user, processus_uuid):
    """
    Vérifie si un utilisateur peut créer (rôle "écrire") pour un processus donné
    
    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus
    
    Returns:
        bool: True si l'utilisateur peut créer, False sinon
    """
    return user_has_permission(user, processus_uuid, 'ecrire')


def user_can_read_for_processus(user, processus_uuid):
    """
    Vérifie si un utilisateur peut lire (rôle "lire") pour un processus donné
    
    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus
    
    Returns:
        bool: True si l'utilisateur peut lire, False sinon
    """
    return user_has_permission(user, processus_uuid, 'lire')


def user_can_delete_for_processus(user, processus_uuid):
    """
    Vérifie si un utilisateur peut supprimer (rôle "supprimer") pour un processus donné
    
    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus
    
    Returns:
        bool: True si l'utilisateur peut supprimer, False sinon
    """
    return user_has_permission(user, processus_uuid, 'supprimer')


def user_can_validate_for_processus(user, processus_uuid):
    """
    Vérifie si un utilisateur peut valider (rôle "valider") pour un processus donné
    
    Args:
        user: L'utilisateur Django
        processus_uuid: UUID du processus
    
    Returns:
        bool: True si l'utilisateur peut valider, False sinon
    """
    return user_has_permission(user, processus_uuid, 'valider')


def get_user_processus_list(user):
    """
    Retourne la liste des UUIDs des processus où l'utilisateur a au moins un rôle actif
    
    Args:
        user: L'utilisateur Django
    
    Returns:
        list: Liste des UUIDs (strings) des processus accessibles par l'utilisateur
        Si l'utilisateur est super admin (is_staff ET is_superuser) OU is_super_admin, 
        retourne tous les processus actifs (None pour indiquer "tous")
    """
    if not user or not user.is_authenticated:
        return []
    
    # ========== SUPER ADMIN : Accès à tous les processus ==========
    # Security by Design : Les utilisateurs avec is_staff ET is_superuser ont accès à tous les processus
    if can_manage_users(user) or is_super_admin(user):
        # Retourner None pour indiquer "tous les processus" (sera géré dans les vues)
        # Cela permet de ne pas filtrer les données
        return None
    # ========== FIN SUPER ADMIN ==========
    
    # Récupérer tous les processus où l'utilisateur a au moins un rôle actif
    processus_uuids = UserProcessusRole.objects.filter(
        user=user,
        is_active=True
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
        Security by Design : Les utilisateurs avec is_staff ET is_superuser ont accès à tous les processus
    """
    if not user or not user.is_authenticated:
        return False
    
    # ========== SUPER ADMIN : Accès à tous les processus ==========
    # Security by Design : Les utilisateurs avec is_staff ET is_superuser ont accès à tous les processus
    if can_manage_users(user) or is_super_admin(user):
        return True
    # ========== FIN SUPER ADMIN ==========
    
    # Convertir processus_uuid en UUID si c'est un objet Processus
    if isinstance(processus_uuid, Processus):
        processus_uuid = processus_uuid.uuid
    
    # Vérifier si l'utilisateur a au moins un rôle actif pour ce processus
    return UserProcessusRole.objects.filter(
        user=user,
        processus__uuid=processus_uuid,
        is_active=True
    ).exists()


def user_has_write_permission_anywhere(user):
    """
    Vérifie si l'utilisateur a le rôle 'ecrire' pour au moins un processus.
    Utile pour les ressources globales (comme les documents) qui ne sont pas liées à un processus spécifique.
    
    Args:
        user: L'utilisateur à vérifier
        
    Returns:
        bool: True si l'utilisateur a le rôle 'ecrire' pour au moins un processus actif
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not user or not user.is_authenticated:
        return False
    
    # ========== SUPER ADMIN : Accès complet ==========
    if is_super_admin(user):
        return True
    # ========== FIN SUPER ADMIN ==========
    
    try:
        # Récupérer le rôle 'ecrire'
        try:
            role_ecrire = Role.objects.get(code='ecrire', is_active=True)
        except Role.DoesNotExist:
            logger.warning(f"[user_has_write_permission_anywhere] Rôle 'ecrire' non trouvé")
            return False
        
        # Vérifier si l'utilisateur a ce rôle pour au moins un processus actif
        has_permission = UserProcessusRole.objects.filter(
            user=user,
            role=role_ecrire,
            is_active=True
        ).exists()
        
        return has_permission
    except Exception as e:
        logger.error(f"[user_has_write_permission_anywhere] Erreur: {str(e)}")
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
        - Si has_permission est True, error_response est None
        - Si has_permission est False, error_response contient la réponse 403
    """
    from rest_framework.response import Response
    from rest_framework import status
    
    # ========== SUPER ADMIN : Accès complet sans restriction ==========
    if is_super_admin(user):
        return True, None
    # ========== FIN SUPER ADMIN ==========
    
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

