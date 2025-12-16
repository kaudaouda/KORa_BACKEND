"""
Utilitaires pour vérifier les permissions utilisateur basées sur les rôles
Security by Design : Vérification côté backend pour éviter le bypass du frontend
"""
from django.contrib.auth.models import User
from .models import UserProcessusRole, Processus, Role


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
    """
    if not user or not user.is_authenticated:
        return []
    
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
    """
    if not user or not user.is_authenticated:
        return False
    
    # Convertir processus_uuid en UUID si c'est un objet Processus
    if isinstance(processus_uuid, Processus):
        processus_uuid = processus_uuid.uuid
    
    # Vérifier si l'utilisateur a au moins un rôle actif pour ce processus
    return UserProcessusRole.objects.filter(
        user=user,
        processus__uuid=processus_uuid,
        is_active=True
    ).exists()


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

