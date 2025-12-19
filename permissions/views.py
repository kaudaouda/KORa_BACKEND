"""
Vues API pour le système générique de permissions
Permet de consulter et gérer les permissions via l'API
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
import logging

from permissions.models import (
    PermissionAction,
    RolePermissionMapping,
    AppPermission,
    PermissionOverride,
    PermissionAudit
)
from permissions.serializers import (
    PermissionActionSerializer,
    PermissionActionListSerializer,
    RolePermissionMappingSerializer,
    RolePermissionMappingCreateSerializer,
    AppPermissionSerializer,
    PermissionOverrideSerializer,
    PermissionOverrideCreateSerializer,
    PermissionAuditSerializer,
    UserPermissionsSummarySerializer
)
from permissions.services.permission_service import PermissionService
from parametre.models import Role, Processus, UserProcessusRole
from parametre.permissions import is_super_admin

logger = logging.getLogger(__name__)


# ==================== PERMISSION ACTIONS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permission_actions_list(request):
    """
    Liste toutes les PermissionAction
    Filtrable par app_name et category
    """
    try:
        app_name = request.query_params.get('app_name')
        category = request.query_params.get('category')
        is_active = request.query_params.get('is_active', 'true').lower() == 'true'
        
        queryset = PermissionAction.objects.filter(is_active=is_active)
        
        if app_name:
            queryset = queryset.filter(app_name=app_name)
        
        if category:
            queryset = queryset.filter(category=category)
        
        queryset = queryset.order_by('app_name', 'code')
        
        serializer = PermissionActionListSerializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': queryset.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans permission_actions_list: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des actions'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permission_action_detail(request, action_id):
    """Détails d'une PermissionAction"""
    try:
        action = PermissionAction.objects.get(id=action_id)
        serializer = PermissionActionSerializer(action)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except PermissionAction.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Action non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur dans permission_action_detail: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ROLE PERMISSION MAPPINGS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def role_permission_mappings_list(request):
    """
    Liste les RolePermissionMapping
    Filtrable par role, app_name, granted
    """
    try:
        # Seuls les super admins peuvent voir tous les mappings
        if not is_super_admin(request.user):
            return Response({
                'success': False,
                'error': 'Accès refusé. Seuls les super administrateurs peuvent consulter les mappings.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        role_id = request.query_params.get('role')
        app_name = request.query_params.get('app_name')
        granted = request.query_params.get('granted')
        
        queryset = RolePermissionMapping.objects.filter(is_active=True).select_related(
            'role', 'permission_action'
        )
        
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        
        if app_name:
            queryset = queryset.filter(permission_action__app_name=app_name)
        
        if granted is not None:
            queryset = queryset.filter(granted=granted.lower() == 'true')
        
        queryset = queryset.order_by('role', 'priority', 'permission_action')
        
        serializer = RolePermissionMappingSerializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': queryset.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans role_permission_mappings_list: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des mappings'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def role_permission_mapping_create(request):
    """Créer ou mettre à jour un RolePermissionMapping (super admin uniquement)"""
    try:
        if not is_super_admin(request.user):
            return Response({
                'success': False,
                'error': 'Accès refusé. Seuls les super administrateurs peuvent créer des mappings.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Logger les données reçues pour debug
        logger.info(f"Données reçues pour création mapping: {request.data}")
        logger.info(f"Type de granted reçu: {type(request.data.get('granted'))}, valeur: {request.data.get('granted')}")
        
        serializer = RolePermissionMappingCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Utiliser update_or_create pour gérer la contrainte unique_together
            # Le serializer retourne déjà les objets Role et PermissionAction après validation
            role_obj = serializer.validated_data['role']
            permission_action_obj = serializer.validated_data['permission_action']
            
            # Récupérer les valeurs avec vérification explicite pour éviter les problèmes avec False
            # Le serializer a déjà géré la valeur par défaut dans validate()
            granted = serializer.validated_data.get('granted', True)
            
            logger.info(f"Données validées - granted: {granted} (type: {type(granted)})")
            
            mapping, created = RolePermissionMapping.objects.update_or_create(
                role=role_obj,
                permission_action=permission_action_obj,
                defaults={
                    'granted': granted,
                    'conditions': serializer.validated_data.get('conditions'),
                    'priority': serializer.validated_data.get('priority', 0),
                    'is_active': serializer.validated_data.get('is_active', True),
                }
            )
            
            # Le signal post_save dans middleware.py invalidera automatiquement le cache
            # pour tous les utilisateurs ayant ce rôle. Pas besoin d'invalider ici.
            
            response_serializer = RolePermissionMappingSerializer(mapping)
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Mapping créé avec succès' if created else 'Mapping mis à jour avec succès'
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        else:
            logger.error(f"Erreur de validation serializer: {serializer.errors}")
            logger.error(f"Données reçues: {request.data}")
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur dans role_permission_mapping_create: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': f'Erreur lors de la création/mise à jour du mapping: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== USER PERMISSIONS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_permissions(request, user_id=None):
    """
    Récupère les permissions d'un utilisateur pour une application
    Si user_id n'est pas fourni, retourne les permissions de l'utilisateur connecté
    """
    try:
        # Déterminer l'utilisateur cible
        if user_id:
            from django.contrib.auth.models import User
            target_user = User.objects.get(id=user_id)
            # Seuls les super admins peuvent voir les permissions d'autres utilisateurs
            if not is_super_admin(request.user) and request.user.id != user_id:
                return Response({
                    'success': False,
                    'error': 'Accès refusé. Vous ne pouvez voir que vos propres permissions.'
                }, status=status.HTTP_403_FORBIDDEN)
        else:
            target_user = request.user
        
        app_name = request.query_params.get('app_name')
        processus_uuid = request.query_params.get('processus_uuid')
        
        if not app_name:
            return Response({
                'success': False,
                'error': 'Le paramètre app_name est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Récupérer les permissions via PermissionService
        permissions = PermissionService.get_user_permissions(
            user=target_user,
            app_name=app_name,
            processus_uuid=processus_uuid
        )
        
        return Response({
            'success': True,
            'data': permissions,
            'user_id': target_user.id,
            'username': target_user.username,
            'app_name': app_name
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans user_permissions: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des permissions'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_permissions_summary(request, user_id=None):
    """
    Résumé des permissions d'un utilisateur pour toutes les apps
    """
    try:
        if user_id:
            from django.contrib.auth.models import User
            target_user = User.objects.get(id=user_id)
            if not is_super_admin(request.user) and request.user.id != user_id:
                return Response({
                    'success': False,
                    'error': 'Accès refusé'
                }, status=status.HTTP_403_FORBIDDEN)
        else:
            target_user = request.user
        
        # Récupérer les processus de l'utilisateur
        user_processus = UserProcessusRole.objects.filter(
            user=target_user,
            is_active=True
        ).select_related('processus').values_list('processus', flat=True).distinct()
        
        processus_list = Processus.objects.filter(id__in=user_processus)
        
        # Apps disponibles
        apps = ['cdr', 'dashboard', 'pac']
        
        summary = []
        
        for app_name in apps:
            for processus in processus_list:
                permissions = PermissionService.get_user_permissions(
                    user=target_user,
                    app_name=app_name,
                    processus_uuid=str(processus.uuid)
                )
                
                if str(processus.uuid) in permissions:
                    perms = permissions[str(processus.uuid)]
                    granted_count = sum(1 for p in perms.values() if p.get('granted', False))
                    denied_count = len(perms) - granted_count
                    
                    summary.append({
                        'user_id': target_user.id,
                        'username': target_user.username,
                        'app_name': app_name,
                        'processus_uuid': str(processus.uuid),
                        'processus_nom': processus.nom,
                        'permissions': perms,
                        'total_permissions': len(perms),
                        'granted_permissions': granted_count,
                        'denied_permissions': denied_count
                    })
        
        serializer = UserPermissionsSummarySerializer(summary, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': len(summary)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans user_permissions_summary: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération du résumé'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== PERMISSION OVERRIDES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permission_overrides_list(request):
    """
    Liste les PermissionOverride
    Seuls les super admins peuvent voir tous les overrides
    """
    try:
        if not is_super_admin(request.user):
            # Les utilisateurs ne peuvent voir que leurs propres overrides
            queryset = PermissionOverride.objects.filter(
                user=request.user,
                is_active=True
            )
        else:
            queryset = PermissionOverride.objects.filter(is_active=True)
        
        user_id = request.query_params.get('user_id')
        app_name = request.query_params.get('app_name')
        processus_uuid = request.query_params.get('processus_uuid')
        
        if user_id and is_super_admin(request.user):
            queryset = queryset.filter(user_id=user_id)
        
        if app_name:
            queryset = queryset.filter(app_name=app_name)
        
        if processus_uuid:
            queryset = queryset.filter(processus__uuid=processus_uuid)
        
        queryset = queryset.select_related('user', 'processus', 'permission_action', 'cree_par')
        queryset = queryset.order_by('-created_at')
        
        serializer = PermissionOverrideSerializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': queryset.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans permission_overrides_list: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des overrides'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def permission_override_create(request):
    """Créer un PermissionOverride (super admin uniquement)"""
    try:
        if not is_super_admin(request.user):
            return Response({
                'success': False,
                'error': 'Accès refusé. Seuls les super administrateurs peuvent créer des overrides.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        # Ajouter automatiquement le créateur
        if 'cree_par' not in data:
            data['cree_par'] = request.user.id
        
        serializer = PermissionOverrideCreateSerializer(data=data)
        if serializer.is_valid():
            override = serializer.save()
            response_serializer = PermissionOverrideSerializer(override)
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Override créé avec succès'
            }, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Erreur de validation serializer: {serializer.errors}")
            logger.error(f"Données reçues: {request.data}")
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur dans permission_override_create: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'override'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def permission_override_delete(request, override_uuid):
    """Supprimer un PermissionOverride (super admin uniquement)"""
    try:
        if not is_super_admin(request.user):
            return Response({
                'success': False,
                'error': 'Accès refusé. Seuls les super administrateurs peuvent supprimer des overrides.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            override = PermissionOverride.objects.get(uuid=override_uuid)
            override.delete()
            return Response({
                'success': True,
                'message': 'Override supprimé avec succès'
            }, status=status.HTTP_200_OK)
        except PermissionOverride.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Override non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur dans permission_override_delete: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'override'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== PERMISSION AUDIT ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permission_audit_list(request):
    """
    Liste les PermissionAudit (logs de vérifications)
    Seuls les super admins peuvent voir tous les audits
    """
    try:
        if not is_super_admin(request.user):
            # Les utilisateurs ne peuvent voir que leurs propres audits
            queryset = PermissionAudit.objects.filter(user=request.user)
        else:
            queryset = PermissionAudit.objects.all()
        
        user_id = request.query_params.get('user_id')
        app_name = request.query_params.get('app_name')
        action_code = request.query_params.get('action_code')
        granted = request.query_params.get('granted')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if user_id and is_super_admin(request.user):
            queryset = queryset.filter(user_id=user_id)
        
        if app_name:
            queryset = queryset.filter(app_name=app_name)
        
        if action_code:
            queryset = queryset.filter(action_code=action_code)
        
        if granted is not None:
            queryset = queryset.filter(granted=granted.lower() == 'true')
        
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        queryset = queryset.select_related('user', 'processus')
        queryset = queryset.order_by('-timestamp')[:100]  # Limiter à 100 derniers
        
        serializer = PermissionAuditSerializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': queryset.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans permission_audit_list: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des audits'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== UTILITAIRES ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_permission(request):
    """
    Vérifie si l'utilisateur connecté peut effectuer une action
    """
    try:
        app_name = request.data.get('app_name')
        processus_uuid = request.data.get('processus_uuid')
        action = request.data.get('action')
        
        if not all([app_name, processus_uuid, action]):
            return Response({
                'success': False,
                'error': 'app_name, processus_uuid et action sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        can_perform, reason = PermissionService.can_perform_action(
            user=request.user,
            app_name=app_name,
            processus_uuid=processus_uuid,
            action=action
        )
        
        return Response({
            'success': True,
            'data': {
                'can_perform': can_perform,
                'reason': reason,
                'app_name': app_name,
                'action': action,
                'processus_uuid': processus_uuid
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans check_permission: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la vérification de la permission'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invalidate_cache(request):
    """
    Invalide le cache des permissions d'un utilisateur (super admin uniquement)
    """
    try:
        if not is_super_admin(request.user):
            return Response({
                'success': False,
                'error': 'Accès refusé. Seuls les super administrateurs peuvent invalider le cache.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        user_id = request.data.get('user_id')
        app_name = request.data.get('app_name')  # Optionnel
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        PermissionService.invalidate_user_cache(user_id, app_name=app_name)
        
        return Response({
            'success': True,
            'message': f'Cache invalidé pour user_id={user_id}, app_name={app_name or "toutes"}'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur dans invalidate_cache: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de l\'invalidation du cache'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
