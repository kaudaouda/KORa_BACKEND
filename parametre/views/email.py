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



def email_settings_detail(request):
    """
    Récupérer les paramètres email globaux — réservé aux super-admins.
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        settings = EmailSettings.get_solo()
        serializer = EmailSettingsSerializer(settings)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération des paramètres email: %s", {str(e)})
        return Response({'error': 'Impossible de récupérer les paramètres email'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def email_settings_update(request):
    """
    Mettre à jour les paramètres email globaux — réservé aux super-admins.
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        settings = EmailSettings.get_solo()
        serializer = EmailSettingsSerializer(settings, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            # Log de l'activité
            ActivityLog.objects.create(
                user=request.user,
                action='update',
                entity_type='email_settings',
                entity_id=str(settings.uuid),
                entity_name='Paramètres email',
                description=f'Paramètres email mis à jour par {request.user.username}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response({
                'message': 'Paramètres email mis à jour avec succès',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error("Erreur lors de la mise à jour des paramètres email: %s", {str(e)})
        return Response({'error': 'Impossible de mettre à jour les paramètres email'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_email_configuration(request):
    """
    Tester la configuration email (version sécurisée) — réservé aux super-admins.
    Security by Design : Validation stricte, logging sécurisé, accès restreint.
    """
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from .utils.email_security import EmailValidator, EmailContentSanitizer, SecureEmailLogger
        
        email_settings = EmailSettings.get_solo()
        
        # Récupérer et valider l'email de test
        test_email = request.data.get('test_email', request.user.email)
        if not test_email:
            return Response({'error': 'Adresse email de test requise'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider l'email
        if not EmailValidator.is_valid_email(test_email):
            return Response({
                'error': 'Adresse email invalide',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que la configuration est complète
        if not email_settings.email_host_user or not email_settings.get_password():
            return Response({
                'error': 'Configuration email incomplète',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Test de connexion SMTP d'abord
        connection_ok, connection_message = email_settings.test_smtp_connection()
        if not connection_ok:
            SecureEmailLogger.log_security_event('smtp_connection_failed', {
                'user': request.user.username,
                'error': connection_message
            })
            return Response({
                'error': f'Échec de la connexion SMTP : {connection_message}',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Configuration temporaire
        original_config = {
            'EMAIL_HOST': getattr(settings, 'EMAIL_HOST', ''),
            'EMAIL_PORT': getattr(settings, 'EMAIL_PORT', 587),
            'EMAIL_HOST_USER': getattr(settings, 'EMAIL_HOST_USER', ''),
            'EMAIL_HOST_PASSWORD': getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
            'EMAIL_USE_TLS': getattr(settings, 'EMAIL_USE_TLS', True),
            'EMAIL_USE_SSL': getattr(settings, 'EMAIL_USE_SSL', False),
            'EMAIL_TIMEOUT': getattr(settings, 'EMAIL_TIMEOUT', 10),
        }
        
        # Appliquer la configuration depuis la base de données
        test_config = email_settings.get_email_config()
        for key, value in test_config.items():
            setattr(settings, key, value)
        
        try:
            # Préparer le contenu sécurisé
            subject = EmailContentSanitizer.sanitize_subject('Test de configuration email - KORA')
            message = EmailContentSanitizer.sanitize_html('Ceci est un email de test pour vérifier la configuration SMTP.')
            
            # Envoyer l'email
            send_mail(
                subject=subject,
                message=message,
                from_email=test_config['DEFAULT_FROM_EMAIL'],
                recipient_list=[test_email],
                fail_silently=False,
            )
            
            # Logger le succès
            SecureEmailLogger.log_email_sent(test_email, subject, True)
            
            # Créer un log d'activité
            ActivityLog.objects.create(
                user=request.user,
                action='test',
                entity_type='email_settings',
                entity_id=str(email_settings.uuid),
                entity_name='Configuration email',
                description=f'Test email réussi vers {SecureEmailLogger.mask_email(test_email)}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response({
                'message': f'Email de test envoyé avec succès à {test_email}',
                'status': 'success'
            }, status=status.HTTP_200_OK)
            
        except Exception as send_error:
            # Logger l'échec
            SecureEmailLogger.log_email_sent(test_email, 'Test email', False)
            
            return Response({
                'error': f'Erreur lors de l\'envoi : {str(send_error)}',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        finally:
            # Restaurer la configuration originale
            for key, value in original_config.items():
                setattr(settings, key, value)
        
    except Exception as e:
        logger.error("Erreur lors du test email: %s", {str(e)})
        return Response({
            'error': 'Erreur interne lors du test',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

