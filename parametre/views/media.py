from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
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



def media_create(request):
    """
    Créer un nouveau média (upload de fichier)
    """
    try:
        fichier = request.FILES.get('fichier')
        url_fichier = request.data.get('url_fichier')
        description = request.data.get('description', '')
        # Sous-dossier de rangement (par app). Valeurs autorisées dans
        # parametre.media_paths.ALLOWED_APP_FOLDERS. Fallback: 'shared'.
        app_folder = request.data.get('app') or request.data.get('app_folder')

        if not fichier and not url_fichier:
            return Response({
                'error': 'Fichier ou URL fichier requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        if url_fichier:
            from urllib.parse import urlparse
            import ipaddress
            try:
                parsed = urlparse(url_fichier)
                if parsed.scheme not in ('http', 'https'):
                    return Response({'error': 'URL invalide : seuls http et https sont autorisés.'}, status=status.HTTP_400_BAD_REQUEST)
                hostname = parsed.hostname or ''
                if not hostname:
                    return Response({'error': 'URL invalide.'}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    addr = ipaddress.ip_address(hostname)
                    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                        return Response({'error': 'URL pointant vers une adresse privée non autorisée.'}, status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    if hostname.lower() in {'localhost', '::1', '0.0.0.0'}:
                        return Response({'error': 'URL non autorisée.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                return Response({'error': 'URL invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        if fichier:
            error = validate_uploaded_file(fichier)
            if error:
                return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        # Créer le média (sans le fichier d'abord pour pouvoir poser
        # _app_folder avant que upload_to ne soit appelé par .save()).
        media = Media(
            url_fichier=url_fichier if url_fichier else None,
            description=description if description else None,
        )
        media._app_folder = app_folder
        if fichier:
            media.fichier = fichier
        media.save()

        # Retourner les données du média créé
        return Response({
            'uuid': str(media.uuid),
            'fichier_url': media.get_url(),
            'url_fichier': media.url_fichier,
            'description': media.description,
            'created_at': media.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error("Erreur lors de la création du média: %s", str(e))
        return Response({
            'error': f'Impossible de créer le média: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, DashboardMediaUpdatePermission])
def media_update_description(request, uuid):
    """Mettre à jour la description d'un média"""
    try:
        try:
            media = Media.objects.get(uuid=uuid)
        except Media.DoesNotExist:
            return Response({'error': 'Média non trouvé'}, status=status.HTTP_404_NOT_FOUND)

        description = request.data.get('description', '')
        media.description = description
        media.save()

        return Response({
            'success': True,
            'message': 'Description mise à jour avec succès',
            'media': {
                'uuid': str(media.uuid),
                'fichier_url': media.get_url(),
                'url_fichier': media.url_fichier,
                'description': media.description,
                'created_at': media.created_at.isoformat()
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la mise à jour de la description: %s", str(e))
        return Response({'error': 'Impossible de mettre à jour la description'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, DashboardMediaCreatePermission])
def media_list(request):
    """Lister les médias existants"""
    try:
        medias = Media.objects.all().order_by('-created_at')
        data = []
        for m in medias:
            data.append({
                'uuid': str(m.uuid),
                'fichier_url': m.get_url(),
                'url_fichier': m.url_fichier,
                'description': m.description,
                'created_at': m.created_at.isoformat()
            })
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la liste des médias: %s", str(e))
        return Response({'error': 'Impossible de lister les médias'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardMediaCreatePermission])
def preuve_create_with_medias(request):
    """Créer une preuve et y associer une liste de médias (uuids)."""
    try:
        titre = request.data.get('titre')
        media_uuids = request.data.get('medias', [])
        if not titre:
            return Response({'error': 'titre est requis'}, status=status.HTTP_400_BAD_REQUEST)
        preuve = Preuve.objects.create(titre=titre)
        if isinstance(media_uuids, list) and len(media_uuids) > 0:
            medias = list(Media.objects.filter(uuid__in=media_uuids))
            preuve.medias.add(*medias)
        return Response({
            'uuid': str(preuve.uuid),
            'titre': preuve.titre,
            'medias': [str(m.uuid) for m in preuve.medias.all()],
            'created_at': preuve.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error("Erreur lors de la création de la preuve: %s", str(e))
        return Response({'error': 'Impossible de créer la preuve'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardPreuveUpdatePermission])
def preuve_add_medias(request, uuid):
    """Ajouter des médias à une preuve existante"""
    try:
        try:
            preuve = Preuve.objects.prefetch_related('medias').get(uuid=uuid)
        except Preuve.DoesNotExist:
            return Response({'error': 'Preuve non trouvée'}, status=status.HTTP_404_NOT_FOUND)
        
        media_uuids = request.data.get('medias', [])
        if not isinstance(media_uuids, list) or len(media_uuids) == 0:
            return Response({'error': 'medias (liste d\'UUIDs) est requis'}, status=status.HTTP_400_BAD_REQUEST)
        
        medias = list(Media.objects.filter(uuid__in=media_uuids))
        if len(medias) != len(media_uuids):
            return Response({'error': 'Certains médias n\'ont pas été trouvés'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Ajouter les médias à la preuve (ManyToMany.add ignore les doublons)
        preuve.medias.add(*medias)
        
        # Recharger la preuve depuis la DB avec prefetch pour avoir les médias à jour
        # IMPORTANT: refresh_from_db() ne rafraîchit pas les relations ManyToMany
        preuve = Preuve.objects.prefetch_related('medias').get(uuid=uuid)
        
        return Response({
            'uuid': str(preuve.uuid),
            'titre': preuve.titre,
            'medias': [str(m.uuid) for m in preuve.medias.all()],
            'created_at': preuve.created_at.isoformat()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("[PREUVE_ADD_MEDIAS] Erreur lors de l'ajout de médias à la preuve: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({'error': 'Impossible d\'ajouter les médias à la preuve'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardPreuveUpdatePermission])
def preuve_remove_media(request, uuid, media_uuid):
    """Supprimer un média d'une preuve"""
    try:
        try:
            preuve = Preuve.objects.get(uuid=uuid)
        except Preuve.DoesNotExist:
            return Response({'error': 'Preuve non trouvée'}, status=status.HTTP_404_NOT_FOUND)

        try:
            media = Media.objects.get(uuid=media_uuid)
        except Media.DoesNotExist:
            return Response({'error': 'Média non trouvé'}, status=status.HTTP_404_NOT_FOUND)

        # Vérifier que le média appartient bien à cette preuve
        if media not in preuve.medias.all():
            return Response({'error': 'Ce média n\'appartient pas à cette preuve'}, status=status.HTTP_400_BAD_REQUEST)

        # Retirer le média de la preuve
        preuve.medias.remove(media)

        # Supprimer le média de la base de données (si souhaité)
        # Attention : cela supprimera aussi le fichier physique
        media.delete()

        return Response({
            'success': True,
            'message': 'Média supprimé avec succès',
            'preuve': {
                'uuid': str(preuve.uuid),
                'titre': preuve.titre,
                'medias': [str(m.uuid) for m in preuve.medias.all()]
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la suppression du média: %s", str(e))
        return Response({'error': 'Impossible de supprimer le média'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def preuves_list(request):
    """Lister les preuves avec leurs médias"""
    try:
        preuves = Preuve.objects.prefetch_related('medias').order_by('-created_at')
        data = []
        for p in preuves:
            data.append({
                'uuid': str(p.uuid),
                'titre': p.titre,
                'medias': [
                    {
                        'uuid': str(m.uuid),
                        'fichier_url': m.get_url(),
                        'url_fichier': m.url_fichier,
                        'created_at': m.created_at.isoformat()
                    }
                    for m in p.medias.all()
                ],
                'created_at': p.created_at.isoformat()
            })
        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la liste des preuves: %s", str(e))
        return Response({'error': 'Impossible de lister les preuves'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

