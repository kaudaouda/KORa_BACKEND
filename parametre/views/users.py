from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import json
import time
import hashlib
import logging
from datetime import timedelta
from django.http import StreamingHttpResponse
from django.db.models import Max, Subquery, OuterRef

from ..media_paths import validate_uploaded_file
from ..models import (
    Nature, Categorie, Source, ActionType, Statut,
    EtatMiseEnOeuvre, Appreciation, Media, Direction,
    SousDirection, Service, Processus, Preuve, ActivityLog, StatutActionCDR,
    NotificationSettings, DashboardNotificationSettings, EmailSettings, DysfonctionnementRecommandation, Frequence,
    FrequenceRisque, GraviteRisque, CriticiteRisque, Risque, Mois, TypeDocument,
    Role, UserProcessus, UserProcessusRole, Notification, NotificationPolicy,
    ReminderEmailLog, FailedLoginAttempt, LoginSecurityConfig, LoginBlock,
)
from ..utils.notification_policy import should_notify_pac
from ..serializers import (
    AppreciationSerializer, CategorieSerializer, DirectionSerializer,
    SousDirectionSerializer, ActionTypeSerializer, NotificationSettingsSerializer,
    DashboardNotificationSettingsSerializer, EmailSettingsSerializer, FrequenceSerializer,
    RisqueSerializer, StatutActionCDRSerializer,
    RoleSerializer, UserProcessusSerializer, UserProcessusRoleSerializer,
    UserSerializer, UserCreateSerializer, UserInviteSerializer,
    CriticiteRisqueSerializer, DysfonctionnementRecommandationSerializer,
    NatureSerializer, ProcessusSerializer, ServiceSerializer,
    MoisSerializer, FrequenceRisqueSerializer, GraviteRisqueSerializer,
    TypeDocumentSerializer,
)
from ..utils.email_security import EmailValidator, EmailContentSanitizer, EmailRateLimiter, SecureEmailLogger
from ..utils.email_config import load_email_settings_into_django
from permissions.permissions import (
    DashboardPreuveUpdatePermission,
    DashboardMediaUpdatePermission,
    DashboardMediaCreatePermission,
)

logger = logging.getLogger(__name__)

from .utils import (
    ServerSentEventRenderer, get_client_ip, _parse_user_agent,
    log_activity, get_model_list_data,
)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roles_list(request):
    """Liste des rôles actifs"""
    try:
        roles = Role.objects.filter(is_active=True).order_by('nom')
        serializer = RoleSerializer(roles, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des rôles: %s", e)
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des rôles',
            'error': "Une erreur inattendue s'est produite. Veuillez réessayer."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roles_all_list(request):
    """
    Liste de tous les rôles (y compris les désactivés)
    Security by Design : Accessible uniquement aux utilisateurs avec is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent voir tous les rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        roles = Role.objects.all().order_by('nom')
        serializer = RoleSerializer(roles, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération de tous les rôles: %s", e)
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de tous les rôles',
            'error': "Une erreur inattendue s'est produite. Veuillez réessayer."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def role_create(request):
    """
    Créer un nouveau rôle (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent créer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        serializer = RoleSerializer(data=request.data)
        if serializer.is_valid():
            role = serializer.save()
            log_activity(
                user=request.user,
                action='create',
                entity_type='role',
                entity_id=str(role.uuid),
                entity_name=role.nom,
                description=f"Création du rôle {role.nom}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création du rôle: %s", str(e))
        return Response({'error': 'Impossible de créer le rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def role_update(request, uuid):
    """
    Mettre à jour un rôle (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent modifier des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        role = Role.objects.get(uuid=uuid)
        serializer = RoleSerializer(role, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            log_activity(
                user=request.user,
                action='update',
                entity_type='role',
                entity_id=str(role.uuid),
                entity_name=role.nom,
                description=f"Modification du rôle {role.nom}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Role.DoesNotExist:
        return Response({'error': 'Rôle non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour du rôle: %s", str(e))
        return Response({'error': 'Impossible de mettre à jour le rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def role_delete(request, uuid):
    """
    Supprimer un rôle (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent supprimer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        role = Role.objects.get(uuid=uuid)
        role_nom = role.nom
        role_code = role.code
        
        # Vérifier si le rôle est utilisé dans des attributions
        from parametre.models import UserProcessusRole
        user_roles_count = UserProcessusRole.objects.filter(role=role).count()
        
        if user_roles_count > 0:
            return Response({
                'error': f'Impossible de supprimer le rôle "{role_nom}". Il est actuellement attribué à {user_roles_count} utilisateur(s). Veuillez d\'abord retirer toutes les attributions de ce rôle.',
                'code': 'ROLE_IN_USE',
                'user_roles_count': user_roles_count
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Supprimer automatiquement les mappings de permissions associés au rôle
        from permissions.models import RolePermissionMapping
        from permissions.services.permission_service import PermissionService
        permission_mappings = RolePermissionMapping.objects.filter(role=role)
        permission_mappings_count = permission_mappings.count()
        
        if permission_mappings_count > 0:
            # Supprimer les mappings de permissions
            permission_mappings.delete()
            
            # Invalider le cache des permissions pour tous les utilisateurs qui avaient ce rôle
            # Récupérer tous les utilisateurs qui ont ce rôle
            user_processus_roles = UserProcessusRole.objects.filter(role=role).select_related('user', 'processus')
            affected_users = set()
            for upr in user_processus_roles:
                # processus peut être None pour les rôles globaux (is_global=True)
                if upr.processus:
                    affected_users.add((upr.user.id, str(upr.processus.uuid)))
                else:
                    affected_users.add((upr.user.id, None))
            
            # Invalider le cache pour chaque utilisateur/processus
            for user_id, processus_uuid in affected_users:
                try:
                    PermissionService.invalidate_user_cache(user_id, processus_uuid=processus_uuid)
                except Exception as e:
                    logger.warning("Erreur lors de l'invalidation du cache pour user_id=%s, processus=%s: %s", user_id, processus_uuid, e)
            
            logger.info("Suppression de %s mapping(s) de permissions pour le rôle %s", permission_mappings_count, role_nom)
        
        # Supprimer le rôle (Django supprimera automatiquement les mappings restants via CASCADE)
        role.delete()
        
        # Construire le message de succès
        description_parts = [f"Suppression du rôle {role_nom} ({role_code})"]
        if permission_mappings_count > 0:
            description_parts.append(f"et de {permission_mappings_count} mapping(s) de permissions associé(s)")
        
        log_activity(
            user=request.user,
            action='delete',
            entity_type='role',
            entity_id=str(uuid),
            entity_name=role_nom,
            description=" ".join(description_parts),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Construire le message de réponse
        message = f'Rôle "{role_nom}" supprimé avec succès'
        if permission_mappings_count > 0:
            message += f' ({permission_mappings_count} mapping(s) de permissions supprimé(s) automatiquement)'
        
        return Response({
            'success': True,
            'message': message,
            'permission_mappings_deleted': permission_mappings_count
        }, status=status.HTTP_200_OK)
    except Role.DoesNotExist:
        return Response({'error': 'Rôle non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la suppression du rôle: %s", str(e))
        return Response({'error': 'Impossible de supprimer le rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UserProcessus CRUD
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_processus_list(request):
    """
    Liste des attributions processus-utilisateur.
    - Utilisateurs avec is_staff ET is_superuser (can_manage_users=True) : peuvent voir toutes les attributions, avec filtres optionnels.
    - Autres utilisateurs : ne voient que leurs propres attributions, sans filtres arbitraires.
    Security by Design : évite qu'un utilisateur normal liste les attributions d'autres utilisateurs.
    """
    try:
        from parametre.permissions import can_manage_users

        user_id = request.GET.get('user_id')
        processus_id = request.GET.get('processus_id')

        # Utilisateur avec droits de gestion : accès complet avec filtres
        if can_manage_users(request.user):
            queryset = UserProcessus.objects.select_related(
                'user', 'processus', 'attribue_par'
            ).filter(is_active=True)

            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if processus_id:
                queryset = queryset.filter(processus_id=processus_id)
        else:
            # Utilisateur normal : uniquement ses propres attributions actives
            queryset = UserProcessus.objects.select_related(
                'user', 'processus', 'attribue_par'
            ).filter(is_active=True, user=request.user)

        serializer = UserProcessusSerializer(queryset.order_by('-date_attribution'), many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des attributions processus: %s", e)
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des attributions processus',
            'error': "Une erreur inattendue s'est produite. Veuillez réessayer."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_processus_create(request):
    """
    Créer une nouvelle attribution processus-utilisateur.
    Security by Design : réservé aux super administrateurs (can_manage_users).
    """
    try:
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response(
                {
                    'error': 'Accès refusé. Seuls les super administrateurs peuvent attribuer des processus.',
                    'code': 'PERMISSION_DENIED',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data['attribue_par'] = request.user.id
        
        serializer = UserProcessusSerializer(data=data)
        if serializer.is_valid():
            user_processus = serializer.save()
            log_activity(
                user=request.user,
                action='create',
                entity_type='user_processus',
                entity_id=str(user_processus.uuid),
                entity_name=f"{user_processus.user.username} - {user_processus.processus.nom}",
                description=f"Attribution du processus {user_processus.processus.nom} à {user_processus.user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(UserProcessusSerializer(user_processus).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création de l'attribution processus: %s", str(e))
        return Response({'error': 'Impossible de créer l\'attribution processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def user_processus_update(request, uuid):
    """
    Mettre à jour une attribution processus-utilisateur.
    Security by Design : réservé aux super administrateurs (can_manage_users).
    """
    try:
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response(
                {
                    'error': 'Accès refusé. Seuls les super administrateurs peuvent modifier des attributions processus.',
                    'code': 'PERMISSION_DENIED',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_processus = UserProcessus.objects.get(uuid=uuid)
        serializer = UserProcessusSerializer(user_processus, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            log_activity(
                user=request.user,
                action='update',
                entity_type='user_processus',
                entity_id=str(user_processus.uuid),
                entity_name=f"{user_processus.user.username} - {user_processus.processus.nom}",
                description=f"Modification de l'attribution processus {user_processus.processus.nom} pour {user_processus.user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except UserProcessus.DoesNotExist:
        return Response({'error': 'Attribution processus non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour de l'attribution processus: %s", str(e))
        return Response({'error': 'Impossible de mettre à jour l\'attribution processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def user_processus_delete(request, uuid):
    """
    Supprimer une attribution processus-utilisateur.
    Security by Design : réservé aux super administrateurs (can_manage_users).
    """
    try:
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response(
                {
                    'error': 'Accès refusé. Seuls les super administrateurs peuvent supprimer des attributions processus.',
                    'code': 'PERMISSION_DENIED',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_processus = UserProcessus.objects.get(uuid=uuid)
        user_processus.delete()
        log_activity(
            user=request.user,
            action='delete',
            entity_type='user_processus',
            entity_id=str(user_processus.uuid),
            entity_name=f"{user_processus.user.username} - {user_processus.processus.nom}",
            description=f"Suppression de l'attribution processus {user_processus.processus.nom} pour {user_processus.user.username}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return Response({'message': 'Attribution processus supprimée avec succès'}, status=status.HTTP_200_OK)
    except UserProcessus.DoesNotExist:
        return Response({'error': 'Attribution processus non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la suppression de l'attribution processus: %s", str(e))
        return Response({'error': 'Impossible de supprimer l\'attribution processus'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UserProcessusRole CRUD
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_processus_role_list(request):
    """
    Liste des rôles attribués aux utilisateurs pour les processus
    - Utilisateurs avec is_staff ET is_superuser : voient tous les rôles
    - Autres utilisateurs : voient uniquement leurs propres rôles
    Security by Design : Vérifie can_manage_users pour voir tous les rôles
    """
    try:
        from parametre.permissions import can_manage_users
        
        # ========== FILTRAGE PAR UTILISATEUR (Security by Design) ==========
        if can_manage_users(request.user):
            # Utilisateur avec is_staff ET is_superuser : voir tous les rôles
            queryset = UserProcessusRole.objects.select_related('user', 'processus', 'role', 'attribue_par').filter(is_active=True)
        else:
            # Utilisateur normal : voir uniquement ses propres rôles
            queryset = UserProcessusRole.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('user', 'processus', 'role', 'attribue_par')
        # ========== FIN FILTRAGE ==========
        
        # Filtres additionnels (seulement pour utilisateurs avec is_staff ET is_superuser)
        if can_manage_users(request.user):
            user_id = request.GET.get('user_id')
            processus_id = request.GET.get('processus_id')
            role_id = request.GET.get('role_id')
            
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if processus_id:
                queryset = queryset.filter(processus_id=processus_id)
            if role_id:
                queryset = queryset.filter(role_id=role_id)
        
        serializer = UserProcessusRoleSerializer(queryset.order_by('-date_attribution'), many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des rôles utilisateur-processus: %s", e)
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des rôles utilisateur-processus',
            'error': "Une erreur inattendue s'est produite. Veuillez réessayer."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_processus_role_create(request):
    """
    Créer une nouvelle attribution de rôle utilisateur-processus (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les super administrateurs peuvent attribuer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        data = request.data.copy()
        data['attribue_par'] = request.user.id
        
        # Vérifier si l'attribution existe déjà (contrainte UNIQUE)
        from parametre.models import UserProcessusRole
        user_id = data.get('user')
        processus_id = data.get('processus')
        role_id = data.get('role')
        
        is_global = data.get('is_global', False)
        if is_global and user_id and role_id:
            # Duplicate check for global roles
            existing = UserProcessusRole.objects.filter(
                user_id=user_id,
                role_id=role_id,
                is_global=True,
                is_active=True
            ).first()
            if existing:
                return Response({
                    'error': 'Ce rôle global est déjà attribué à cet utilisateur.',
                    'code': 'ALREADY_EXISTS',
                    'existing_uuid': str(existing.uuid)
                }, status=status.HTTP_400_BAD_REQUEST)

        if user_id and processus_id and role_id:
            existing = UserProcessusRole.objects.filter(
                user_id=user_id,
                processus_id=processus_id,
                role_id=role_id,
                is_active=True
            ).first()

            if existing:
                # Retourner une réponse 400 avec un message clair au lieu d'une erreur 500
                return Response({
                    'error': 'Ce rôle est déjà attribué à cet utilisateur pour ce processus.',
                    'code': 'ALREADY_EXISTS',
                    'existing_uuid': str(existing.uuid)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = UserProcessusRoleSerializer(data=data)
        if serializer.is_valid():
            user_processus_role = serializer.save()
            log_activity(
                user=request.user,
                action='create',
                entity_type='user_processus_role',
                entity_id=str(user_processus_role.uuid),
                entity_name=(
                    f"{user_processus_role.user.username} - "
                    f"{'[GLOBAL]' if user_processus_role.is_global else user_processus_role.processus.nom} - "
                    f"{user_processus_role.role.nom}"
                ),
                description=(
                    f"Attribution du rôle {user_processus_role.role.nom} pour "
                    f"{user_processus_role.user.username} "
                    + (
                        "sur tous les processus (rôle global)"
                        if user_processus_role.is_global
                        else f"sur le processus {user_processus_role.processus.nom}"
                    )
                ),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(UserProcessusRoleSerializer(user_processus_role).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création de l'attribution de rôle: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        
        # Vérifier si c'est une erreur de contrainte UNIQUE
        error_str = str(e)
        if 'UNIQUE constraint' in error_str or 'unique constraint' in error_str.lower():
            return Response({
                'error': 'Ce rôle est déjà attribué à cet utilisateur pour ce processus.',
                'code': 'ALREADY_EXISTS'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'error': 'Impossible de créer l\'attribution de rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def user_processus_role_update(request, uuid):
    """
    Mettre à jour une attribution de rôle utilisateur-processus (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent modifier des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        user_processus_role = UserProcessusRole.objects.get(uuid=uuid)
        serializer = UserProcessusRoleSerializer(user_processus_role, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            log_activity(
                user=request.user,
                action='update',
                entity_type='user_processus_role',
                entity_id=str(user_processus_role.uuid),
                entity_name=(
                    f"{user_processus_role.user.username} - "
                    f"{'[GLOBAL]' if user_processus_role.is_global else user_processus_role.processus.nom} - "
                    f"{user_processus_role.role.nom}"
                ),
                description=(
                    f"Modification de l'attribution du rôle {user_processus_role.role.nom} pour "
                    f"{user_processus_role.user.username} "
                    + (
                        "sur tous les processus (rôle global)"
                        if user_processus_role.is_global
                        else f"sur le processus {user_processus_role.processus.nom}"
                    )
                ),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except UserProcessusRole.DoesNotExist:
        return Response({'error': 'Attribution de rôle non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour de l'attribution de rôle: %s", str(e))
        return Response({'error': 'Impossible de mettre à jour l\'attribution de rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def user_processus_role_delete(request, uuid):
    """
    Supprimer une attribution de rôle utilisateur-processus (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent supprimer des rôles.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        user_processus_role = UserProcessusRole.objects.get(uuid=uuid)
        user_processus_role.delete()
        log_activity(
            user=request.user,
            action='delete',
            entity_type='user_processus_role',
            entity_id=str(user_processus_role.uuid),
            entity_name=(
                f"{user_processus_role.user.username} - "
                f"{'[GLOBAL]' if user_processus_role.is_global else user_processus_role.processus.nom} - "
                f"{user_processus_role.role.nom}"
            ),
            description=(
                f"Suppression de l'attribution du rôle {user_processus_role.role.nom} pour "
                f"{user_processus_role.user.username} "
                + (
                    "sur tous les processus (rôle global)"
                    if user_processus_role.is_global
                    else f"sur le processus {user_processus_role.processus.nom}"
                )
            ),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return Response({'message': 'Attribution de rôle supprimée avec succès'}, status=status.HTTP_200_OK)
    except UserProcessusRole.DoesNotExist:
        return Response({'error': 'Attribution de rôle non trouvée'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur lors de la suppression de l'attribution de rôle: %s", str(e))
        return Response({'error': 'Impossible de supprimer l\'attribution de rôle'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== GESTION DES UTILISATEURS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_list(request):
    """
    Liste tous les utilisateurs (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent voir la liste des utilisateurs.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        from django.contrib.auth.models import User
        
        # Filtres optionnels
        search = request.GET.get('search', '')
        is_active = request.GET.get('is_active')
        
        _last_login_qs = ActivityLog.objects.filter(user=OuterRef('pk'), action='login').order_by('-created_at')
        _last_logout_qs = ActivityLog.objects.filter(user=OuterRef('pk'), action='logout').order_by('-created_at')

        queryset = User.objects.annotate(
            last_login_activity=Subquery(_last_login_qs.values('created_at')[:1]),
            last_login_device=Subquery(_last_login_qs.values('device_type')[:1]),
            last_login_browser=Subquery(_last_login_qs.values('browser')[:1]),
            last_login_os=Subquery(_last_login_qs.values('os_name')[:1]),
            last_logout=Subquery(_last_logout_qs.values('created_at')[:1]),
        ).order_by('-date_joined')

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        serializer = UserSerializer(queryset, many=True)
        data = [
            {
                **dict(d),
                'last_login':         u.last_login_activity.isoformat() if u.last_login_activity else None,
                'last_login_device':  u.last_login_device,
                'last_login_browser': u.last_login_browser,
                'last_login_os':      u.last_login_os,
                'last_logout':        u.last_logout.isoformat()          if u.last_logout          else None,
            }
            for d, u in zip(serializer.data, queryset)
        ]
        return Response({
            'success': True,
            'data': data,
            'count': queryset.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des utilisateurs: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des utilisateurs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_user_detail(request, user_id):
    """
    Détail complet d'un utilisateur pour l'interface d'administration.
    Security by Design : is_staff + is_superuser requis.
    """
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django.contrib.auth.models import User
    from parametre.models import (
        ActivityLog, FailedLoginAttempt, LoginBlock,
        UserProcessus, UserProcessusRole, ReminderEmailLog,
    )

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    # ── Infos de base ─────────────────────────────────────────────────────────
    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    user_data = {
        'id':           user.id,
        'username':     user.username,
        'email':        user.email,
        'first_name':   user.first_name,
        'last_name':    user.last_name,
        'full_name':    full_name,
        'is_active':    user.is_active,
        'is_staff':     user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined':  user.date_joined,
        'last_login':   user.last_login,
    }

    # ── Dernière session (depuis ActivityLog) ─────────────────────────────────
    last_login_log = (
        ActivityLog.objects
        .filter(user=user, action='login')
        .order_by('-created_at')
        .values('ip_address', 'device_type', 'browser', 'os_name', 'created_at')
        .first()
    )

    # ── Statistiques ──────────────────────────────────────────────────────────
    total_logins  = ActivityLog.objects.filter(user=user, action='login').count()
    total_actions = ActivityLog.objects.filter(user=user).count()
    last_activity = (
        ActivityLog.objects.filter(user=user)
        .order_by('-created_at')
        .values_list('created_at', flat=True)
        .first()
    )
    failed_logins_count = FailedLoginAttempt.objects.filter(
        Q(user=user) | Q(email_attempted=user.email)
    ).count()

    stats = {
        'total_logins':       total_logins,
        'total_actions':      total_actions,
        'failed_logins_count': failed_logins_count,
        'last_activity_at':   last_activity,
    }

    # ── Sécurité ─────────────────────────────────────────────────────────────
    from django.utils import timezone
    active_block = (
        LoginBlock.objects
        .filter(block_type='email', value=user.email, blocked_until__gt=timezone.now())
        .values('block_type', 'blocked_until', 'attempts_count', 'is_manual', 'created_at')
        .first()
    )
    failed_attempts = list(
        FailedLoginAttempt.objects
        .filter(Q(user=user) | Q(email_attempted=user.email))
        .order_by('-created_at')
        .values('email_attempted', 'ip_address', 'reason', 'device_type', 'browser', 'os_name', 'created_at')
        [:20]
    )

    security = {
        'active_block':    active_block,
        'failed_attempts': failed_attempts,
    }

    # ── Processus & Rôles ─────────────────────────────────────────────────────
    up_qs = (
        UserProcessus.objects
        .filter(user=user, is_active=True)
        .select_related('processus', 'attribue_par')
        .prefetch_related('processus__user_processus_roles')
    )
    processus_roles = []
    for up in up_qs:
        roles_for_proc = list(
            UserProcessusRole.objects
            .filter(user=user, processus=up.processus, is_active=True, is_global=False)
            .select_related('role')
            .values('uuid', 'role__code', 'role__nom', 'date_attribution')
        )
        processus_roles.append({
            'uuid':              str(up.uuid),
            'processus_uuid':    str(up.processus.uuid),
            'processus_nom':     up.processus.nom,
            'processus_numero':  up.processus.numero_processus,
            'date_attribution':  up.date_attribution,
            'attribue_par':      up.attribue_par.username if up.attribue_par else None,
            'roles':             [
                {
                    'uuid':             str(r['uuid']),
                    'role_code':        r['role__code'],
                    'role_nom':         r['role__nom'],
                    'date_attribution': r['date_attribution'],
                }
                for r in roles_for_proc
            ],
        })

    global_roles = list(
        UserProcessusRole.objects
        .filter(user=user, is_global=True, is_active=True)
        .select_related('role', 'attribue_par')
        .values('uuid', 'role__code', 'role__nom', 'date_attribution', 'attribue_par__username')
    )
    global_roles_data = [
        {
            'uuid':             str(r['uuid']),
            'role_code':        r['role__code'],
            'role_nom':         r['role__nom'],
            'date_attribution': r['date_attribution'],
            'attribue_par':     r['attribue_par__username'],
        }
        for r in global_roles
    ]

    # ── Activité récente ──────────────────────────────────────────────────────
    recent_activity = list(
        ActivityLog.objects
        .filter(user=user)
        .order_by('-created_at')
        .values(
            'uuid', 'action', 'entity_type', 'entity_name',
            'description', 'ip_address', 'device_type', 'browser', 'created_at',
        )
        [:30]
    )

    # ── Emails envoyés ────────────────────────────────────────────────────────
    email_logs = list(
        ReminderEmailLog.objects
        .filter(Q(user=user) | Q(recipient=user.email))
        .order_by('-sent_at')
        .values('uuid', 'recipient', 'subject', 'sent_at', 'success', 'error_message')
        [:20]
    )

    # ── Historique CRUD (create / update / delete uniquement) ─────────────────
    crud_activity = list(
        ActivityLog.objects
        .filter(user=user, action__in=['create', 'update', 'delete'])
        .order_by('-created_at')
        .values(
            'uuid', 'action', 'entity_type', 'entity_name',
            'description', 'ip_address', 'browser', 'created_at',
        )
        [:100]
    )

    return Response({
        'user':           user_data,
        'last_session':   last_login_log,
        'stats':          stats,
        'security':       security,
        'processus_roles': processus_roles,
        'global_roles':   global_roles_data,
        'recent_activity': recent_activity,
        'crud_activity':  crud_activity,
        'email_logs':     email_logs,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_user_toggle_active(request, user_id):
    """
    Active ou désactive un utilisateur.
    Security by Design :
      - is_staff + is_superuser requis
      - Impossible de se désactiver soi-même
      - Impossible de désactiver un autre superuser
    """
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django.contrib.auth.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if user.pk == request.user.pk:
        return Response({'error': 'Vous ne pouvez pas modifier votre propre statut.'}, status=status.HTTP_403_FORBIDDEN)

    if user.is_superuser and not user.is_active is False:
        return Response({'error': 'Impossible de désactiver un super-administrateur.'}, status=status.HTTP_403_FORBIDDEN)

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    action_label = 'activé' if user.is_active else 'désactivé'
    ActivityLog.objects.create(
        user=request.user,
        action='update',
        entity_type='user',
        entity_id=str(user.pk),
        entity_name=user.username,
        description=f'Compte de {user.username} {action_label} par {request.user.username}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    logger.info('[USER] %s %s par %s', user.username, action_label, request.user.username)

    return Response({
        'id':        user.pk,
        'username':  user.username,
        'is_active': user.is_active,
        'message':   f'Compte {action_label} avec succès.',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def users_create(request):
    """
    Créer un nouvel utilisateur (is_staff ET is_superuser uniquement)
    Security by Design : Vérifie que l'utilisateur a is_staff ET is_superuser
    """
    try:
        # ========== VÉRIFICATION DE SÉCURITÉ (Security by Design) ==========
        from parametre.permissions import can_manage_users
        if not can_manage_users(request.user):
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent créer des utilisateurs.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Log de l'activité
            log_activity(
                user=request.user,
                action='create',
                entity_type='user',
                entity_id=str(user.id),
                entity_name=f"{user.username} ({user.email})",
                description=f"Création de l'utilisateur {user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Retourner l'utilisateur créé avec le serializer de lecture
            response_serializer = UserSerializer(user)
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Utilisateur créé avec succès'
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'error': 'Données invalides',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création de l'utilisateur: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'utilisateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def users_invite(request):
    """
    Invite un nouvel utilisateur (is_staff ET is_superuser uniquement).
    Security by Design :
    - Vérifie les permissions via can_manage_users
    - Ne manipule jamais de mot de passe côté admin
    - Envoie un lien signé et limité dans le temps pour que l'utilisateur définisse son mot de passe
    """
    try:
        logger.info("=" * 60)
        logger.info("DEBUT users_invite")
        logger.info("Utilisateur qui invite: %s (is_staff=%s, is_superuser=%s)", request.user.username, request.user.is_staff, request.user.is_superuser)
        logger.info("IP: %s", get_client_ip(request))
        
        # ========== VÉRIFICATION DE SÉCURITÉ ==========
        from parametre.permissions import can_manage_users
        can_manage = can_manage_users(request.user)
        logger.info("can_manage_users: %s", can_manage)
        
        if not can_manage:
            logger.warning("Accès refusé pour %s", request.user.username)
            return Response({
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent inviter des utilisateurs.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Rate limiting basique pour éviter le spam d'invitations
        user_limit_ok = EmailRateLimiter.check_user_limit(request.user.id)
        global_limit_ok = EmailRateLimiter.check_global_limit()
        logger.info("Rate limiting - user_limit: %s, global_limit: %s", user_limit_ok, global_limit_ok)
        
        if not user_limit_ok or not global_limit_ok:
            SecureEmailLogger.log_security_event('invite_rate_limit_exceeded', {
                'user': request.user.username,
                'ip': get_client_ip(request),
                'type': 'user_invite'
            })
            logger.warning("Rate limit dépassé pour %s", request.user.username)
            return Response({
                'success': False,
                'error': "Trop de tentatives d'invitation, veuillez réessayer plus tard."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Logger les données reçues pour le débogage
        logger.info("Données brutes reçues (request.data): %s", request.data)
        logger.info("Type de request.data: %s", type(request.data))
        logger.info("Clés présentes: %s", (list(request.data.keys()) if isinstance(request.data, dict) else 'N/A'))
        
        # Vérifier si l'email existe déjà AVANT la validation du serializer
        email_received = request.data.get('email', '')
        logger.info("Email reçu: %s", email_received)
        
        if email_received:
            from django.contrib.auth.models import User
            email_exists = User.objects.filter(email=email_received).exists()
            logger.info("Email existe déjà dans la DB: %s", email_exists)
            if email_exists:
                existing_user = User.objects.filter(email=email_received).first()
                logger.info("Utilisateur existant trouvé: username=%s, id=%s, is_active=%s", existing_user.username, existing_user.id, existing_user.is_active)
        
        serializer = UserInviteSerializer(data=request.data)
        logger.info("Serializer créé, validation en cours...")
        
        if not serializer.is_valid():
            logger.error("ERREUR: Serializer invalide")
            logger.error("Erreurs de validation détaillées: %s", serializer.errors)
            logger.error("Données qui ont causé l'erreur: %s", request.data)
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info("Serializer valide, création de l'utilisateur...")

        user = serializer.save()
        logger.info("Utilisateur créé avec succès: username=%s, email=%s, id=%s, is_active=%s", user.username, user.email, user.id, user.is_active)

        # Générer un token d'invitation basé sur le système de reset password
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        logger.info("Token d'invitation généré pour uid=%s", uid)

        frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')
        raw_invite_url = f"{frontend_base}/set-password?uid={uid}&token={token}"
        invite_url = EmailContentSanitizer.sanitize_url(raw_invite_url)

        # Calculer la date d'expiration pour l'affichage dans l'email
        from datetime import datetime, timedelta
        invitation_timeout = getattr(settings, 'INVITATION_TOKEN_TIMEOUT', 604800)  # 7 jours par défaut
        expiration_date = datetime.now() + timedelta(seconds=invitation_timeout)
        expiration_str = expiration_date.strftime("%d/%m/%Y à %H:%M")

        # Vérifier l'email du destinataire
        if not EmailValidator.is_valid_email(user.email):
            return Response({
                'success': False,
                'error': "Adresse email du destinataire invalide."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Préparer le contexte pour le template
        context = {
            'user_first_name': user.first_name,
            'user_username': user.username,
            'user_email': user.email,
            'invite_url': invite_url,
            'expiration_date': expiration_str,
        }

        # Rendre les templates HTML et texte
        html_body = render_to_string('emails/user_invitation_email.html', context)
        text_body = render_to_string('emails/user_invitation_email.txt', context)
        
        subject = EmailContentSanitizer.sanitize_subject("KORA – Activation de votre compte")

        # Charger la configuration SMTP depuis EmailSettings
        config_ok = load_email_settings_into_django()
        if not config_ok:
            logger.warning("Configuration EmailSettings incomplète, utilisation de la configuration actuelle des settings.")

        # Envoyer l'email via la configuration courante
        logger.info("Envoi de l'email d'invitation à %s...", user.email)
        logger.info("URL d'invitation: %s", invite_url)
        
        try:
            send_mail(
                subject=subject,
                message=text_body,
                html_message=html_body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', user.email),
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info("Email envoyé avec succès à %s", user.email)
        except Exception as email_error:
            logger.error("ERREUR lors de l'envoi de l'email: %s", str(email_error))
            # Ne pas échouer complètement si l'email échoue, mais logger l'erreur
            SecureEmailLogger.log_email_sent(user.email, subject, False)

        SecureEmailLogger.log_email_sent(user.email, subject, True)

        # Log de l'activité
        log_activity(
            user=request.user,
            action='create',
            entity_type='user',
            entity_id=str(user.id),
            entity_name=f"{user.username} ({user.email})",
            description=f"Invitation de l'utilisateur {user.username}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        logger.info("Invitation terminée avec succès pour %s", user.email)
        logger.info("=" * 60)
        
        return Response({
            'success': True,
            'message': "Invitation envoyée avec succès. L'utilisateur recevra un email pour définir son mot de passe."
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        import traceback
        # Security by Design — Minimal Disclosure : str(e) jamais exposé au client
        logger.error("ERREUR EXCEPTION dans users_invite: %s\n%s", str(e), traceback.format_exc())
        SecureEmailLogger.log_email_sent(
            getattr(request, 'user', None) and getattr(request.user, 'email', ''),
            "KORA – Invitation utilisateur",
            False,
        )
        return Response({
            'success': False,
            'error': "Erreur lors de l'invitation de l'utilisateur. Veuillez réessayer.",
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_get_user_processus(request):
    """Vue pour l'admin Django : retourne les processus d'un utilisateur"""
    from django.contrib.auth.models import User
    from django.http import JsonResponse
    from parametre.permissions import can_manage_users

    # Security by Design : Complete Mediation — toute demande vérifiée,
    # même les endpoints "internes". Refus silencieux pour ne pas confirmer
    # l'existence de données.
    if not can_manage_users(request.user):
        return JsonResponse({'processus': []}, safe=False)

    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'processus': []}, safe=False)

    try:
        user = User.objects.get(id=user_id)
        processus_list = UserProcessus.objects.filter(
            user=user,
            is_active=True
        ).select_related('processus')

        processus_data = []
        for up in processus_list:
            processus_data.append({
                'uuid': str(up.processus.uuid),
                'nom': up.processus.nom,
                'numero_processus': up.processus.numero_processus
            })

        return JsonResponse({'processus': processus_data}, safe=False)
    except User.DoesNotExist:
        return JsonResponse({'processus': []}, safe=False)
    except Exception as e:
        logger.error("Erreur lors de la récupération des processus utilisateur: %s", e)
        return JsonResponse({'error': 'Impossible de récupérer les processus'}, status=500)

