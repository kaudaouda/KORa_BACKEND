"""
Vues sécurisées pour la gestion des emails
À intégrer dans parametre/views.py

Security by Design :
- Rate limiting
- Validation stricte
- Audit trail complet
- Protection CSRF
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

from .models import EmailSettings, ReminderEmailLog, ActivityLog
from .serializers import EmailSettingsSerializer, EmailTestSerializer
from .utils.email_security import (
    EmailRateLimiter,
    EmailValidator,
    EmailContentSanitizer,
    SecureEmailLogger
)
from .views import get_client_ip  # Importer depuis le fichier original

logger = logging.getLogger(__name__)


class EmailTestThrottle(UserRateThrottle):
    """
    Rate limiting pour les tests d'email
    Security by Design : 1 test par minute par utilisateur
    """
    rate = '1/min'


# ==================== EMAIL SETTINGS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def email_settings_detail_secure(request):
    """
    Récupérer les paramètres email (version sécurisée)
    Security by Design : Mot de passe jamais renvoyé
    """
    try:
        settings_obj = EmailSettings.get_solo()
        serializer = EmailSettingsSerializer(settings_obj, context={'request': request})
        
        # Logger l'accès
        SecureEmailLogger.log_security_event('email_settings_accessed', {
            'user': request.user.username,
            'ip': get_client_ip(request)
        })
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des paramètres email: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les paramètres email'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])  # Admin uniquement
def email_settings_update_secure(request):
    """
    Mettre à jour les paramètres email (version sécurisée)
    Security by Design : Validation stricte, audit complet
    """
    try:
        settings_obj = EmailSettings.get_solo()
        serializer = EmailSettingsSerializer(
            settings_obj,
            data=request.data,
            partial=(request.method == 'PATCH'),
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Sauvegarder les anciennes valeurs pour l'audit
            old_values = {
                'email_host': settings_obj.email_host,
                'email_port': settings_obj.email_port,
                'email_host_user': settings_obj.email_host_user,
            }
            
            # Sauvegarder
            serializer.save()
            
            # Créer un log d'activité détaillé
            changes = []
            for key, old_value in old_values.items():
                new_value = getattr(settings_obj, key)
                if old_value != new_value:
                    # Masquer les emails dans les logs
                    if 'email' in key and old_value:
                        old_value = SecureEmailLogger.mask_email(old_value)
                    if 'email' in key and new_value:
                        new_value = SecureEmailLogger.mask_email(new_value)
                    changes.append(f"{key}: {old_value} -> {new_value}")
            
            description = f"Paramètres email mis à jour par {request.user.username}"
            if changes:
                description += f" - Changements: {', '.join(changes)}"
            
            ActivityLog.objects.create(
                user=request.user,
                action='update',
                entity_type='email_settings',
                entity_id=str(settings_obj.uuid),
                entity_name='Paramètres email',
                description=description,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Logger l'événement de sécurité
            SecureEmailLogger.log_security_event('email_settings_updated', {
                'user': request.user.username,
                'ip': get_client_ip(request),
                'changes_count': len(changes)
            })
            
            return Response({
                'message': 'Paramètres email mis à jour avec succès',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des paramètres email: {str(e)}")
        return Response({
            'error': 'Impossible de mettre à jour les paramètres email'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([EmailTestThrottle])
def test_email_configuration_secure(request):
    """
    Tester la configuration email (version sécurisée)
    Security by Design : Rate limiting, validation stricte, logging complet
    """
    try:
        # Vérifier le rate limiting manuel
        if not EmailRateLimiter.check_test_email_limit(request.user.id):
            SecureEmailLogger.log_security_event('rate_limit_exceeded', {
                'user': request.user.username,
                'ip': get_client_ip(request),
                'type': 'email_test'
            })
            return Response({
                'error': 'Trop de tentatives. Veuillez patienter avant de réessayer.',
                'status': 'rate_limited'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Valider les données de test
        test_serializer = EmailTestSerializer(data=request.data)
        if not test_serializer.is_valid():
            return Response(
                test_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        test_email = test_serializer.validated_data['test_email']
        
        # Vérifier que l'email est valide
        if not EmailValidator.is_valid_email(test_email):
            return Response({
                'error': 'Adresse email invalide',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Récupérer la configuration
        email_settings = EmailSettings.get_solo()
        
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
            subject = EmailContentSanitizer.sanitize_subject(
                'Test de configuration email - KORA'
            )
            message = EmailContentSanitizer.sanitize_html(
                'Ceci est un email de test pour vérifier la configuration SMTP.'
            )
            
            # Envoyer l'email
            send_mail(
                subject=subject,
                message=message,
                from_email=test_config['DEFAULT_FROM_EMAIL'],
                recipient_list=[test_email],
                fail_silently=False,
            )
            
            # Marquer le test comme réussi
            email_settings.mark_test_success()
            
            # Logger le succès
            SecureEmailLogger.log_email_sent(test_email, subject, True)
            
            # Log d'activité
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
            SecureEmailLogger.log_email_sent(test_email, subject, False)
            SecureEmailLogger.log_security_event('email_send_failed', {
                'user': request.user.username,
                'recipient': SecureEmailLogger.mask_email(test_email),
                'error': str(send_error)[:100]  # Limiter la taille de l'erreur
            })
            
            return Response({
                'error': f'Erreur lors de l\'envoi : {str(send_error)}',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        finally:
            # Restaurer la configuration originale
            for key, value in original_config.items():
                setattr(settings, key, value)
        
    except Exception as e:
        logger.error(f"Erreur lors du test email: {str(e)}")
        return Response({
            'error': 'Erreur interne lors du test',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def email_logs_list(request):
    """
    Liste des logs d'emails (Admin uniquement)
    Security by Design : Accès restreint, données maskées
    """
    try:
        logs = ReminderEmailLog.objects.all().order_by('-sent_at')[:100]
        
        # Masquer les emails pour la sécurité
        safe_logs = []
        for log in logs:
            safe_logs.append({
                'uuid': str(log.uuid),
                'recipient': SecureEmailLogger.mask_email(log.recipient),
                'subject': log.subject,
                'success': log.success,
                'sent_at': log.sent_at.isoformat(),
                'error_message': log.error_message[:100] if log.error_message else None
            })
        
        return Response({
            'logs': safe_logs,
            'total': len(safe_logs)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les logs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
