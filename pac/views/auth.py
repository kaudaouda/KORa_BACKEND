"""
Vues API pour l'application PAC
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from shared.throttles import KoraSensitiveThrottle
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime, timedelta
from ..models import Pac, TraitementPac, PacSuivi, DetailsPac
from parametre.models import Processus, Media, Preuve, Notification, FailedLoginAttempt, LoginSecurityConfig, LoginBlock
from parametre.views import log_pac_creation, log_pac_update, log_traitement_creation, log_suivi_creation, log_user_login, log_user_logout, get_client_ip, log_activity
from parametre.utils.email_security import EmailValidator, EmailContentSanitizer, EmailRateLimiter, SecureEmailLogger
from parametre.utils.email_config import load_email_settings_into_django
from parametre.permissions import (
    check_permission_or_403,
    user_can_create_objectives_amendements,
    user_can_create_for_processus,
    get_user_processus_list,
    user_has_access_to_processus,
)
# Import des classes de permissions génériques PAC
from permissions.permissions import (
    PacListPermission,
    PacDetailPermission,
    PACCreatePermission,
    PACUpdatePermission,
    PACDeletePermission,
    PACValidatePermission,
    PACUnvalidatePermission,
    PACReadPermission,
    PACAmendementCreatePermission,
    PACDetailCreatePermission,
    PACDetailUpdatePermission,
    PACDetailDeletePermission,
    PACTraitementCreatePermission,
    PACTraitementUpdatePermission,
    PACTraitementDeletePermission,
    PACSuiviCreatePermission,
    PACSuiviUpdatePermission,
    PACSuiviDeletePermission,
)
from ..serializers import (
    UserSerializer, ProcessusSerializer, ProcessusCreateSerializer,
    PacSerializer, PacCreateSerializer, PacUpdateSerializer, PacCompletSerializer,
    TraitementPacSerializer, TraitementPacCreateSerializer, TraitementPacUpdateSerializer, 
    PacSuiviSerializer, PacSuiviCreateSerializer, PacSuiviUpdateSerializer,
    DetailsPacSerializer, DetailsPacCreateSerializer, DetailsPacUpdateSerializer
)
from shared.authentication import AuthService
from shared.services.recaptcha_service import recaptcha_service, RecaptchaValidationError
import json
import logging

logger = logging.getLogger(__name__)


from .utils import AllowAnyWithJWT, _get_next_num_amendement_for_pac


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Inscription d'un nouvel utilisateur avec validation reCAPTCHA"""
    try:
        # Accepter les données JSON ou form-encoded
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.data
        
        # Validation reCAPTCHA (si configuré)
        if recaptcha_service.is_enabled():
            recaptcha_token = data.get('recaptcha_token')
            if not recaptcha_token:
                return Response({
                    'error': 'Vérification de sécurité requise',
                    'recaptcha_required': True
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                remote_ip = request.META.get('REMOTE_ADDR')
                is_valid, recaptcha_data = recaptcha_service.verify_token(
                    recaptcha_token, 
                    remote_ip
                )
                
                if not is_valid:
                    logger.warning("reCAPTCHA validation échouée pour l'inscription: %s", recaptcha_data)
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info("reCAPTCHA validé pour l'inscription: score=%s", recaptcha_data.get('score'))
                
            except RecaptchaValidationError as e:
                logger.error("Erreur reCAPTCHA lors de l'inscription: %s", str(e))
                return Response({
                    'error': 'Problème de vérification de sécurité',
                    'recaptcha_error': str(e),
                    'recaptcha_required': True
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('prenom', '')
        last_name = data.get('nom', '')

        # Validation des données
        if not email or not password:
            return Response({
                'error': 'Email et password sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Générer un nom d'utilisateur unique à partir de l'email
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        
        # S'assurer que le nom d'utilisateur est unique
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        if User.objects.filter(email=email).exists():
            return Response({
                'error': 'Cet email est déjà utilisé'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Valider le mot de passe
        try:
            validate_password(password)
        except ValidationError as e:
            return Response({
                'error': 'Mot de passe invalide',
                'details': list(e.messages),
                'requirements': [
                    'Au moins 8 caractères',
                    'Ne pas être trop commun',
                    'Ne pas être entièrement numérique',
                    'Contenir au moins une lettre'
                ]
            }, status=status.HTTP_400_BAD_REQUEST)

        # Créer l'utilisateur
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Générer les tokens
        access_token, refresh_token = AuthService.create_tokens(user)

        # Créer la réponse
        response = Response({
            'message': 'Utilisateur créé avec succès',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

        # Définir les cookies
        return AuthService.set_auth_cookies(response, access_token, refresh_token)

    except json.JSONDecodeError:
        return Response({
            'error': 'Format de données invalide',
            'code': 'INVALID_JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la création de l'utilisateur: %s", str(e))
        return Response({
            'error': 'Impossible de créer le compte. Réessayez plus tard.',
            'code': 'REGISTER_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([KoraSensitiveThrottle])
def login(request):
    """Connexion d'un utilisateur avec validation reCAPTCHA"""
    try:
        # Accepter les données JSON ou form-encoded
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.data
        
        # Validation reCAPTCHA (si configuré)
        if recaptcha_service.is_enabled():
            recaptcha_token = data.get('recaptcha_token')
            if not recaptcha_token:
                return Response({
                    'error': 'Vérification de sécurité requise',
                    'recaptcha_required': True
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                remote_ip = request.META.get('REMOTE_ADDR')
                is_valid, recaptcha_data = recaptcha_service.verify_token(
                    recaptcha_token, 
                    remote_ip
                )
                
                if not is_valid:
                    logger.warning("reCAPTCHA validation échouée pour la connexion: %s", recaptcha_data)
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info("reCAPTCHA validé pour la connexion: score=%s", recaptcha_data.get('score'))
                
            except RecaptchaValidationError as e:
                logger.error("Erreur reCAPTCHA lors de la connexion: %s", str(e))
                return Response({
                    'error': 'Problème de vérification de sécurité',
                    'recaptcha_error': str(e),
                    'recaptcha_required': True
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return Response({
                'error': 'Email et password sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ── Récupération IP / UA ──────────────────────────────────────────────
        ip     = get_client_ip(request)
        ua_str = request.META.get('HTTP_USER_AGENT')

        # ── Vérification des blocages actifs ──────────────────────────────────
        from django.utils import timezone as tz
        cfg = LoginSecurityConfig.get_config()
        if cfg.enabled:
            now = tz.now()
            whitelist = cfg.get_whitelist()
            if ip not in whitelist:
                if LoginBlock.objects.filter(block_type='ip', value=ip, blocked_until__gt=now).exists():
                    return Response(
                        {'error': 'Accès temporairement bloqué. Réessayez plus tard.', 'code': 'IP_BLOCKED'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
            if LoginBlock.objects.filter(block_type='email', value=email, blocked_until__gt=now).exists():
                return Response(
                    {'error': 'Ce compte est temporairement verrouillé. Réessayez plus tard.', 'code': 'EMAIL_BLOCKED'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        # ── Authentification ──────────────────────────────────────────────────
        found_user = None
        reason = None

        try:
            found_user = User.objects.get(email=email)
            authed = authenticate(username=found_user.username, password=password)
            if authed is None:
                reason = 'wrong_password'
            elif not authed.is_active:
                reason = 'inactive_account'
        except User.DoesNotExist:
            reason = 'user_not_found'

        if reason:
            from parametre.views import _parse_user_agent
            device_type, browser, os_name = _parse_user_agent(ua_str)
            FailedLoginAttempt.objects.create(
                email_attempted=email,
                ip_address=ip,
                user_agent=ua_str,
                device_type=device_type,
                browser=browser,
                os_name=os_name,
                user=found_user if reason != 'user_not_found' else None,
                reason=reason,
            )

            # ── Créer/mettre à jour les blocs si seuils dépassés ─────────────
            if cfg.enabled and ip not in whitelist:
                window_start = tz.now() - timedelta(minutes=cfg.window_minutes)

                ip_count = FailedLoginAttempt.objects.filter(
                    ip_address=ip, created_at__gte=window_start
                ).count()
                if ip_count >= cfg.ip_max_attempts:
                    LoginBlock.objects.update_or_create(
                        block_type='ip', value=ip,
                        defaults={
                            'blocked_until':  tz.now() + timedelta(minutes=cfg.ip_block_duration_minutes),
                            'attempts_count': ip_count,
                            'is_manual':      False,
                        }
                    )
                    logger.warning("[SECURITY] IP bloquée: %s (%s échecs)", ip, ip_count)

                email_count = FailedLoginAttempt.objects.filter(
                    email_attempted=email, created_at__gte=window_start
                ).count()
                if email_count >= cfg.email_max_attempts:
                    LoginBlock.objects.update_or_create(
                        block_type='email', value=email,
                        defaults={
                            'blocked_until':  tz.now() + timedelta(minutes=cfg.email_block_duration_minutes),
                            'attempts_count': email_count,
                            'is_manual':      False,
                        }
                    )
                    logger.warning("[SECURITY] Email bloqué: %s (%s échecs)", email, email_count)

            if reason == 'inactive_account':
                return Response({'error': 'Compte utilisateur désactivé'}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({'error': 'Identifiants invalides'}, status=status.HTTP_401_UNAUTHORIZED)

        user = authed

        # Générer les tokens
        access_token, refresh_token = AuthService.create_tokens(user)

        # Log de l'activité de connexion
        log_user_login(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        # Créer la réponse (Security by Design: tokens uniquement dans cookies httpOnly, pas en JSON)
        response = Response({
            'message': 'Connexion réussie',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

        # Définir les cookies (httponly=True = protection XSS)
        return AuthService.set_auth_cookies(response, access_token, refresh_token)

    except json.JSONDecodeError:
        return Response({
            'error': 'Format de données invalide',
            'code': 'INVALID_JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur lors de la connexion: %s", str(e))
        return Response({
            'error': 'Impossible de se connecter. Réessayez plus tard.',
            'code': 'LOGIN_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    """Déconnexion d'un utilisateur — blackliste le refresh token côté serveur"""
    try:
        # Security by Design : invalider le refresh token côté serveur
        # même si le cookie est supprimé, le token ne peut plus être réutilisé
        refresh_token_value = request.COOKIES.get('refresh_token')
        if refresh_token_value:
            try:
                token = RefreshToken(refresh_token_value)
                token.blacklist()
            except (InvalidToken, TokenError):
                # Token déjà invalide ou expiré — pas bloquant
                pass

        # Logger la déconnexion avant d'effacer les cookies
        if request.user.is_authenticated:
            log_user_logout(
                user=request.user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT'),
            )

        response = Response({
            'message': 'Déconnexion réussie'
        }, status=status.HTTP_200_OK)

        return AuthService.clear_auth_cookies(response)

    except Exception as e:
        logger.error("Erreur lors de la déconnexion: %s", str(e))
        return Response({
            'error': 'Problème lors de la déconnexion',
            'code': 'LOGOUT_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """Rafraîchir le token d'accès"""
    try:
        if request.user.is_anonymous and not request.COOKIES.get('refresh_token'):
            logger.info("refresh_token: aucun refresh token trouvé, retour 200")
            response = Response({
                'authenticated': False,
            }, status=status.HTTP_200_OK)
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response

        refresh_token_value = request.COOKIES.get('refresh_token')

        if not refresh_token_value:
            return Response({
                'error': 'Token de rafraîchissement manquant',
                'code': 'REFRESH_TOKEN_MISSING'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_token_value)
            new_access_token = refresh.access_token

            # Créer la réponse (Security by Design: token uniquement dans cookie httpOnly)
            response = Response({
                'message': 'Token rafraîchi avec succès'
            }, status=status.HTTP_200_OK)

            # Mettre à jour le cookie access_token
            response.set_cookie(
                'access_token',
                str(new_access_token),
                max_age=30 * 60,  # 30 minutes — aligné sur ACCESS_TOKEN_LIFETIME
                httponly=True,
                secure=False,  # True en production avec HTTPS
                samesite='Lax',
                path='/'
            )

            return response

        except (InvalidToken, TokenError) as e:
            logger.warning("Refresh token invalide: %s", str(e))
            return Response({
                'error': 'Refresh token invalide',
                'details': str(e),
                'code': 'REFRESH_TOKEN_INVALID'
            }, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.error("Erreur lors du rafraîchissement du token: %s", str(e))
        return Response({
            'error': 'Session expirée, veuillez vous reconnecter',
            'code': 'REFRESH_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAnyWithJWT])
def user_profile(request):
    """Récupérer le profil de l'utilisateur connecté"""
    try:
        if request.user.is_anonymous:
            logger.info("user_profile: utilisateur anonyme - retour profil vide")
            response = Response({
                'authenticated': False,
            }, status=status.HTTP_200_OK)
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response

        logger.debug("user_profile appelé pour user: %s", request.user)
        serializer = UserSerializer(request.user)
        return Response({
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur lors de la récupération du profil: %s", str(e))
        return Response({
            'error': 'Impossible de récupérer le profil',
            'code': 'PROFILE_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Mettre à jour le profil de l'utilisateur connecté"""
    try:
        data = request.data
        user = request.user
        
        # Mettre à jour les champs autorisés
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        
        # Sécurité : Bloquer la modification de l'email côté backend
        if 'email' in data:
            return Response({
                'error': 'La modification de l\'email n\'est pas autorisée. Contactez l\'administrateur.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        user.save()
        
        serializer = UserSerializer(user)
        return Response({
            'message': 'Profil mis à jour avec succès',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la mise à jour du profil: %s", str(e))
        return Response({
            'error': 'Impossible de mettre à jour le profil',
            'code': 'UPDATE_PROFILE_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def admin_update_profile(request):
    """Mettre à jour le profil utilisateur (admin seulement)"""
    try:
        # Vérifier que l'utilisateur est admin
        if not request.user.is_staff:
            return Response({
                'error': 'Accès refusé. Seuls les administrateurs peuvent modifier l\'email.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        user_id = data.get('user_id')
        
        if not user_id:
            return Response({
                'error': 'ID utilisateur requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'error': 'Utilisateur non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Mettre à jour tous les champs autorisés
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            # Vérifier que l'email n'est pas déjà utilisé par un autre utilisateur
            if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response({
                    'error': 'Cet email est déjà utilisé par un autre utilisateur'
                }, status=status.HTTP_400_BAD_REQUEST)
            user.email = data['email']
        
        user.save()
        
        serializer = UserSerializer(user)
        return Response({
            'message': 'Profil utilisateur mis à jour avec succès',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la mise à jour du profil par admin: %s", str(e))
        return Response({
            'error': 'Impossible de mettre à jour le profil',
            'code': 'ADMIN_UPDATE_PROFILE_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Changer le mot de passe de l'utilisateur connecté"""
    try:
        data = request.data
        user = request.user
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        # Validation des données
        if not all([current_password, new_password, confirm_password]):
            return Response({
                'error': 'Tous les champs sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier le mot de passe actuel
        if not user.check_password(current_password):
            return Response({
                'error': 'Mot de passe actuel incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que les nouveaux mots de passe correspondent
        if new_password != confirm_password:
            return Response({
                'error': 'Les nouveaux mots de passe ne correspondent pas'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider le nouveau mot de passe
        try:
            validate_password(new_password)
        except ValidationError as e:
            return Response({
                'error': 'Mot de passe invalide',
                'details': list(e.messages),
                'requirements': [
                    'Au moins 8 caractères',
                    'Ne pas être trop commun',
                    'Ne pas être entièrement numérique',
                    'Contenir au moins une lettre'
                ]
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Changer le mot de passe
        user.set_password(new_password)
        user.save()
        
        return Response({
            'message': 'Mot de passe changé avec succès'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors du changement de mot de passe: %s", str(e))
        return Response({
            'error': 'Impossible de changer le mot de passe',
            'code': 'CHANGE_PASSWORD_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([KoraSensitiveThrottle])
def check_invitation(request):
    """
    Vérifie l'état d'un lien d'invitation sans nécessiter de mot de passe.
    Security by Design :
    - Vérifie la validité du token
    - Vérifie si le compte est déjà activé (mot de passe défini)
    - Permet au frontend de rediriger automatiquement si le lien a déjà été utilisé
    """
    try:
        logger.info("=" * 60)
        logger.info("DEBUT check_invitation")
        logger.info("IP: %s", get_client_ip(request))
        
        # Récupérer les paramètres depuis la query string
        uidb64 = request.GET.get('uid')
        token = request.GET.get('token')
        
        logger.info("uidb64: %s", uidb64)
        logger.info("token: %s...", token[:20] if token else None)
        
        # Validation des paramètres requis
        if not uidb64 or not token:
            logger.warning("Paramètres manquants pour check_invitation")
            return Response({
                'valid': False,
                'error': 'Paramètres manquants',
                'code': 'MISSING_PARAMS'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Décoder l'uid et récupérer l'utilisateur
        try:
            decoded_bytes = urlsafe_base64_decode(uidb64)
            uid = force_str(decoded_bytes)
            user = User.objects.get(pk=uid)
            logger.info("Utilisateur trouvé: id=%s", user.id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
            logger.warning("Erreur lors du décodage ou utilisateur non trouvé: %s", type(e).__name__)
            return Response({
                'valid': False,
                'error': 'Lien d\'invitation invalide',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)

        # IMPORTANT : Vérifier d'abord si le compte a déjà un mot de passe défini
        # Car quand le mot de passe est défini, le token devient invalide automatiquement
        # Il faut donc vérifier has_usable_password() AVANT de vérifier le token
        has_usable = user.has_usable_password()

        if has_usable:
            logger.info("Lien d'invitation déjà utilisé pour id=%s", user.id)
            return Response({
                'valid': True,
                'already_used': True,
                'message': 'Ce lien d\'invitation a déjà été utilisé. Votre compte est déjà activé.',
                'code': 'INVITATION_ALREADY_USED',
            }, status=status.HTTP_200_OK)

        # Vérifier le token d'invitation seulement si le mot de passe n'est pas encore défini
        token_valid = default_token_generator.check_token(user, token)

        if not token_valid:
            logger.warning("Token d'invitation invalide ou expiré pour id=%s", user.id)
            return Response({
                'valid': False,
                'error': 'Lien d\'invitation invalide ou expiré',
                'code': 'INVALID_TOKEN'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Le lien est valide et n'a pas encore été utilisé
        logger.info("Lien d'invitation valide pour id=%s", user.id)
        return Response({
            'valid': True,
            'already_used': False,
            'message': 'Lien d\'invitation valide',
            'code': 'INVITATION_VALID',
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur inattendue dans check_invitation: %s", e, exc_info=True)
        return Response({
            'valid': False,
            'error': 'Erreur lors de la vérification du lien.',
            'code': 'CHECK_INVITATION_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([KoraSensitiveThrottle])
def complete_invitation(request):
    """
    Finalise l'invitation d'un utilisateur en lui permettant de définir son mot de passe.
    Security by Design :
    - Rate limiting pour prévenir les attaques par force brute
    - Vérifie le token d'invitation signé (uid + token)
    - Valide la force du mot de passe avec les validateurs Django
    - Active le compte et connecte automatiquement l'utilisateur
    """
    try:
        logger.info("=" * 60)
        logger.info("DEBUT complete_invitation")
        logger.info("Content-Type: %s", request.content_type)
        logger.info("Method: %s", request.method)
        logger.info("IP: %s", get_client_ip(request))
        
        # ========== RATE LIMITING (Security by Design) ==========
        # Protection contre les attaques par force brute sur les tokens
        from django.core.cache import cache
        
        client_ip = get_client_ip(request)
        rate_limit_key = f'invitation_complete_rate_limit_{client_ip}'
        attempts = cache.get(rate_limit_key, 0)
        max_attempts = 3  # Maximum 3 tentatives par IP par 30 minutes
        rate_limit_window = 1800  # 30 minutes

        if attempts >= max_attempts:
            logger.warning("Rate limit dépassé pour complete_invitation")
            return Response({
                'error': 'Trop de tentatives. Veuillez réessayer dans 30 minutes.',
                'code': 'RATE_LIMIT_EXCEEDED'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Incrémenter le compteur
        cache.set(rate_limit_key, attempts + 1, rate_limit_window)
        # ========== FIN RATE LIMITING ==========
        
        logger.info("request.data type: %s", type(request.data))
        logger.info("request.data: %s", request.data)

        # IMPORTANT : ne plus toucher à request.body ici, DRF l'a déjà consommé
        # On se fie uniquement à request.data, qui contient déjà les données parsées
        data = request.data
        
        # ========== VALIDATION reCAPTCHA (Security by Design) ==========
        # Protection contre les bots et les attaques automatisées
        if recaptcha_service.is_enabled():
            recaptcha_token = data.get('recaptcha_token')
            if not recaptcha_token:
                logger.warning("reCAPTCHA token manquant pour complete_invitation depuis IP: %s", client_ip)
                return Response({
                    'error': 'Vérification de sécurité requise',
                    'recaptcha_required': True,
                    'code': 'RECAPTCHA_REQUIRED'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                remote_ip = get_client_ip(request)
                is_valid, recaptcha_data = recaptcha_service.verify_token(
                    recaptcha_token, 
                    remote_ip
                )
                
                if not is_valid:
                    logger.warning("reCAPTCHA validation échouée pour complete_invitation: %s", recaptcha_data)
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True,
                        'code': 'RECAPTCHA_FAILED'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info("reCAPTCHA validé pour complete_invitation: score=%s", recaptcha_data.get('score'))
                
            except RecaptchaValidationError as e:
                logger.error("Erreur reCAPTCHA lors de la finalisation de l'invitation: %s", str(e))
                return Response({
                    'error': 'Problème de vérification de sécurité',
                    'recaptcha_error': str(e),
                    'recaptcha_required': True,
                    'code': 'RECAPTCHA_ERROR'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # ========== FIN VALIDATION reCAPTCHA ==========
        
        uidb64 = data.get('uid')
        token = data.get('token')
        password = data.get('password')
        password_confirm = data.get('password_confirm')

        # Validation des données requises
        missing_fields = []
        if not uidb64:
            missing_fields.append('uid')
        if not token:
            missing_fields.append('token')
        if not password:
            missing_fields.append('password')
        if not password_confirm:
            missing_fields.append('password_confirm')

        if missing_fields:
            return Response({
                'error': f'Champs requis manquants: {", ".join(missing_fields)}',
                'code': 'MISSING_FIELDS',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier que les mots de passe correspondent
        if password != password_confirm:
            return Response({
                'error': 'Les mots de passe ne correspondent pas.',
                'code': 'PASSWORD_MISMATCH'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Décoder l'uid et récupérer l'utilisateur
        try:
            decoded_bytes = urlsafe_base64_decode(uidb64)
            uid = force_str(decoded_bytes)
            user = User.objects.get(pk=uid)
            logger.info("Utilisateur trouvé: id=%s", user.id)
        except TypeError as e:
            logger.error("TypeError lors du décodage: %s", str(e))
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (TypeError)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            logger.error("ValueError lors du décodage: %s", str(e))
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (ValueError)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except OverflowError as e:
            logger.error("OverflowError lors du décodage: %s", str(e))
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (OverflowError)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            logger.error("Utilisateur non trouvé avec uid: %s", uid)
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (User not found)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Exception inattendue lors du décodage: %s: %s", type(e).__name__, str(e))
            import traceback
            logger.error("Traceback: %s", traceback.format_exc())
            return Response({
                'error': f'Erreur lors du décodage du lien: {str(e)}',
                'code': 'DECODE_ERROR'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier le token d'invitation
        logger.info("Vérification du token d'invitation...")
        token_valid = default_token_generator.check_token(user, token)
        logger.info("Token valide: %s", token_valid)
        
        if not token_valid:
            logger.warning("Token d'invitation invalide ou expiré pour l'utilisateur %s", user.username)
            # Vérifier si c'est une expiration ou une invalidation
            from django.conf import settings
            invitation_timeout = getattr(settings, 'INVITATION_TOKEN_TIMEOUT', 604800)  # 7 jours par défaut
            
            # Vérifier si l'utilisateur a été créé récemment (pour déterminer si c'est une expiration)
            # Note: default_token_generator.check_token() vérifie automatiquement l'expiration
            # Si le token est invalide, c'est soit qu'il a expiré, soit qu'il est invalide
            # On ne peut pas distinguer facilement, donc on affiche un message générique
            error_message = f'Le lien d\'invitation est invalide ou a expiré. Les liens d\'invitation sont valides pendant {invitation_timeout // 86400} jours. Veuillez demander une nouvelle invitation à votre administrateur.'
            
            return Response({
                'error': error_message,
                'code': 'INVALID_TOKEN'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'utilisateur n'a pas déjà un mot de passe défini (sécurité supplémentaire)
        has_usable = user.has_usable_password()
        logger.info("Utilisateur a un mot de passe utilisable: %s", has_usable)
        
        if has_usable:
            logger.warning("Tentative d'utilisation d'un lien d'invitation déjà utilisé pour: %s", user.username)
            
            # Logger cette tentative pour audit de sécurité
            try:
                log_activity(
                    user=user,
                    action='view',  # Action 'view' pour une tentative d'accès
                    entity_type='user',
                    entity_id=str(user.id),
                    entity_name=user.username,
                    description=f"Tentative d'utilisation d'un lien d'invitation déjà utilisé pour le compte {user.username}",
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except Exception as log_error:
                logger.warning("ERREUR lors du log d'audit (non bloquant): %s", str(log_error))
            
            return Response({
                'error': 'Ce lien d\'invitation a déjà été utilisé. Votre compte est déjà activé. Si vous avez oublié votre mot de passe, utilisez la fonctionnalité de réinitialisation de mot de passe.',
                'code': 'INVITATION_ALREADY_USED'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider la force du mot de passe
        logger.info("Validation de la force du mot de passe...")
        try:
            validate_password(password, user=user)
            logger.info("Mot de passe validé avec succès")
        except ValidationError as e:
            logger.error("Mot de passe invalide: %s", list(e.messages))
            return Response({
                'error': 'Mot de passe invalide',
                'details': list(e.messages),
                'requirements': [
                    'Au moins 8 caractères',
                    'Ne pas être trop commun',
                    'Ne pas être entièrement numérique',
                    'Contenir au moins une lettre'
                ],
                'code': 'WEAK_PASSWORD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Définir le mot de passe et activer le compte
        logger.info("Définition du mot de passe et activation du compte...")
        user.set_password(password)
        user.is_active = True
        user.save()
        logger.info("Compte activé et mot de passe défini pour %s", user.username)
        
        # Logger l'utilisation réussie de l'invitation dans ActivityLog
        try:
            log_activity(
                user=user,
                action='update',  # Action 'update' car on met à jour le compte (activation + mot de passe)
                entity_type='user',
                entity_id=str(user.id),
                entity_name=user.username,
                description=f"Lien d'invitation utilisé avec succès pour activer le compte de {user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            logger.info("Log d'activité enregistré pour l'activation du compte de %s", user.username)
        except Exception as log_error:
            logger.warning("ERREUR lors du log d'activité (non bloquant): %s", str(log_error))
            import traceback
            logger.warning("Traceback log activité: %s", traceback.format_exc())
            # Ne pas bloquer si le log échoue
        
        # Générer les tokens JWT et connecter automatiquement l'utilisateur
        logger.info("Génération des tokens JWT...")
        try:
            access_token, refresh_token = AuthService.create_tokens(user)
            logger.info("Tokens JWT générés avec succès")
        except Exception as token_error:
            logger.error("ERREUR lors de la génération des tokens: %s", str(token_error))
            import traceback
            logger.error("Traceback tokens: %s", traceback.format_exc())
            raise
        
        # Créer la réponse avec les tokens dans les cookies
        logger.info("Création de la réponse...")
        try:
            user_data = UserSerializer(user).data
            logger.info("Données utilisateur sérialisées: %s", list(user_data.keys()))
        except Exception as serializer_error:
            logger.error("ERREUR lors de la sérialisation de l'utilisateur: %s", str(serializer_error))
            import traceback
            logger.error("Traceback serializer: %s", traceback.format_exc())
            raise
        
        response = Response({
            'message': 'Mot de passe défini avec succès. Vous êtes maintenant connecté.',
            'user': user_data,
            'success': True
        }, status=status.HTTP_200_OK)
        
        # Définir les cookies d'authentification
        try:
            AuthService.set_auth_cookies(response, access_token, refresh_token)
            logger.info("Cookies d'authentification définis")
        except Exception as cookie_error:
            logger.error("ERREUR lors de la définition des cookies: %s", str(cookie_error))
            import traceback
            logger.error("Traceback cookies: %s", traceback.format_exc())
            raise
        
        # Logger la connexion automatique après finalisation de l'invitation
        logger.info("Log de la connexion...")
        try:
            log_user_login(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception as log_error:
            logger.warning("ERREUR lors du log de connexion (non bloquant): %s", str(log_error))
            import traceback
            logger.warning("Traceback log: %s", traceback.format_exc())
            # Ne pas bloquer si le log échoue
        
        logger.info("Invitation finalisée avec succès pour %s", user.username)
        logger.info("=" * 60)
        
        return response
        
    except json.JSONDecodeError as e:
        logger.error("Erreur de parsing JSON: %s", str(e))
        return Response({
            'error': 'Format de données invalide',
            'code': 'INVALID_JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("=" * 60)
        logger.error("ERREUR EXCEPTION dans complete_invitation: %s", str(e))
        logger.error("Type d'erreur: %s", type(e).__name__)
        import traceback
        logger.error("Traceback complet:\n%s", traceback.format_exc())
        logger.error("=" * 60)
        return Response({
            'error': f'Erreur lors de la finalisation de l\'invitation: {str(e)}',
            'code': 'COMPLETE_INVITATION_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([KoraSensitiveThrottle])
def password_reset_request(request):
    """
    Demande de réinitialisation de mot de passe par un administrateur.
    Security by Design :
    - Accessible uniquement aux administrateurs (is_staff ET is_superuser)
    - Rate limiting pour éviter le spam
    - Envoie un email avec un lien sécurisé pour réinitialiser le mot de passe
    - Ne révèle pas si l'email existe ou non (sécurité)
    """
    try:
        logger.info("=" * 60)
        logger.info("DEBUT password_reset_request")
        logger.info("Utilisateur qui demande: %s (is_staff=%s, is_superuser=%s)", request.user.username, request.user.is_staff, request.user.is_superuser)
        logger.info("IP: %s", get_client_ip(request))
        
        # ========== VÉRIFICATION DE SÉCURITÉ ==========
        from parametre.permissions import can_manage_users
        can_manage = can_manage_users(request.user)
        logger.info("can_manage_users: %s", can_manage)
        
        if not can_manage:
            logger.warning("Accès refusé pour %s", request.user.username)
            return Response({
                'success': False,
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent demander une réinitialisation de mot de passe.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Rate limiting pour éviter le spam
        user_limit_ok = EmailRateLimiter.check_user_limit(request.user.id)
        global_limit_ok = EmailRateLimiter.check_global_limit()
        logger.info("Rate limiting - user_limit: %s, global_limit: %s", user_limit_ok, global_limit_ok)
        
        if not user_limit_ok or not global_limit_ok:
            SecureEmailLogger.log_security_event('password_reset_rate_limit_exceeded', {
                'user': request.user.username,
                'ip': get_client_ip(request),
                'type': 'password_reset_request'
            })
            logger.warning("Rate limit dépassé pour %s", request.user.username)
            return Response({
                'success': False,
                'error': "Trop de tentatives de réinitialisation, veuillez réessayer plus tard."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Récupérer l'email depuis les données
        email = request.data.get('email', '').strip()
        logger.info("Email reçu pour réinitialisation: %s", email)
        
        if not email:
            return Response({
                'success': False,
                'error': 'L\'email est requis',
                'code': 'EMAIL_REQUIRED'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider le format de l'email
        if not EmailValidator.is_valid_email(email):
            return Response({
                'success': False,
                'error': 'Format d\'email invalide',
                'code': 'INVALID_EMAIL'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Chercher l'utilisateur par email
        try:
            user = User.objects.get(email=email)
            logger.info("Utilisateur trouvé: id=%s", user.id)
        except User.DoesNotExist:
            # Security by Design : Ne pas révéler si l'email existe ou non
            # Retourner un succès générique pour éviter l'énumération d'emails
            logger.info("Email non trouvé pour réinitialisation (réponse générique envoyée)")
            return Response({
                'success': True,
                'message': 'Si cet email existe dans notre système, un lien de réinitialisation a été envoyé.'
            }, status=status.HTTP_200_OK)
        
        # Vérifier que l'utilisateur a un mot de passe utilisable (sinon c'est une invitation, pas une réinitialisation)
        if not user.has_usable_password():
            logger.warning("Tentative de réinitialisation pour un utilisateur sans mot de passe: %s", user.username)
            return Response({
                'success': False,
                'error': 'Cet utilisateur n\'a pas encore défini de mot de passe. Utilisez la fonctionnalité d\'invitation.',
                'code': 'NO_PASSWORD_SET'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Générer un token de réinitialisation
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        logger.info("Token de réinitialisation généré: uid=%s, token=%s...", uid, token[:20])
        
        frontend_base = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        raw_reset_url = f"{frontend_base}/reset-password?uid={uid}&token={token}"
        reset_url = EmailContentSanitizer.sanitize_url(raw_reset_url)
        
        # Calculer la date d'expiration (4h par défaut via settings.PASSWORD_RESET_TIMEOUT)
        password_reset_timeout = getattr(settings, 'PASSWORD_RESET_TIMEOUT', 14400)
        expiration_date = datetime.now() + timedelta(seconds=password_reset_timeout)
        expiration_str = expiration_date.strftime("%d/%m/%Y à %H:%M")
        
        # Préparer le contexte pour le template
        context = {
            'user_first_name': user.first_name,
            'user_username': user.username,
            'user_email': user.email,
            'reset_url': reset_url,
            'expiration_date': expiration_str,
        }
        
        # Rendre les templates HTML et texte
        html_body = render_to_string('emails/password_reset_email.html', context)
        text_body = render_to_string('emails/password_reset_email.txt', context)
        
        subject = EmailContentSanitizer.sanitize_subject("KORA – Réinitialisation de votre mot de passe")
        
        # Charger la configuration SMTP depuis EmailSettings (source unique)
        config_ok = load_email_settings_into_django()
        if not config_ok:
            logger.warning("Configuration EmailSettings incomplète, utilisation de la configuration actuelle des settings.")

        # Envoyer l'email
        logger.info("Envoi de l'email de réinitialisation à %s...", user.email)
        logger.info("URL de réinitialisation: %s", reset_url)
        
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
            SecureEmailLogger.log_email_sent(user.email, subject, False)
            return Response({
                'success': False,
                'error': 'Erreur lors de l\'envoi de l\'email de réinitialisation',
                'code': 'EMAIL_SEND_FAILED'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        SecureEmailLogger.log_email_sent(user.email, subject, True)
        
        # Log de l'activité
        log_activity(
            user=request.user,
            action='update',
            entity_type='user',
            entity_id=str(user.id),
            entity_name=f"{user.username} ({user.email})",
            description=f"Demande de réinitialisation de mot de passe pour {user.username}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        logger.info("Demande de réinitialisation terminée avec succès pour %s", user.email)
        logger.info("=" * 60)
        
        return Response({
            'success': True,
            'message': f"Email de réinitialisation envoyé avec succès à {user.email}."
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error("ERREUR EXCEPTION dans password_reset_request: %s", str(e))
        logger.error("Type d'erreur: %s", type(e).__name__)
        import traceback
        logger.error("Traceback complet:\n%s", traceback.format_exc())
        logger.error("=" * 60)
        return Response({
            'success': False,
            'error': f"Erreur lors de la demande de réinitialisation: {str(e)}",
            'code': 'PASSWORD_RESET_REQUEST_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([KoraSensitiveThrottle])
def password_reset_confirm(request):
    """
    Finalise la réinitialisation du mot de passe.
    Security by Design :
    - Rate limiting pour prévenir les attaques par force brute
    - Vérifie le token de réinitialisation signé (uid + token)
    - Valide la force du mot de passe avec les validateurs Django
    - Connecte automatiquement l'utilisateur après réinitialisation
    """
    try:
        logger.info("=" * 60)
        logger.info("DEBUT password_reset_confirm")
        logger.info("Content-Type: %s", request.content_type)
        logger.info("Method: %s", request.method)
        logger.info("IP: %s", get_client_ip(request))
        
        # ========== RATE LIMITING (Security by Design) ==========
        from django.core.cache import cache
        
        client_ip = get_client_ip(request)
        rate_limit_key = f'password_reset_confirm_rate_limit_{client_ip}'
        attempts = cache.get(rate_limit_key, 0)
        max_attempts = 5  # Maximum 5 tentatives par IP par heure
        rate_limit_window = 3600  # 1 heure
        
        if attempts >= max_attempts:
            logger.warning("Rate limit dépassé pour password_reset_confirm depuis IP: %s", client_ip)
            return Response({
                'error': 'Trop de tentatives. Veuillez réessayer dans 1 heure.',
                'code': 'RATE_LIMIT_EXCEEDED'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Incrémenter le compteur
        cache.set(rate_limit_key, attempts + 1, rate_limit_window)
        # ========== FIN RATE LIMITING ==========
        
        logger.info("request.data type: %s", type(request.data))
        logger.info("request.data: %s", request.data)
        
        data = request.data
        
        # ========== VALIDATION reCAPTCHA (Security by Design) ==========
        if recaptcha_service.is_enabled():
            recaptcha_token = data.get('recaptcha_token')
            if not recaptcha_token:
                logger.warning("reCAPTCHA token manquant pour password_reset_confirm depuis IP: %s", client_ip)
                return Response({
                    'error': 'Vérification de sécurité requise',
                    'recaptcha_required': True,
                    'code': 'RECAPTCHA_REQUIRED'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                remote_ip = get_client_ip(request)
                is_valid, recaptcha_data = recaptcha_service.verify_token(
                    recaptcha_token, 
                    remote_ip
                )
                
                if not is_valid:
                    logger.warning("reCAPTCHA validation échouée pour password_reset_confirm: %s", recaptcha_data)
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True,
                        'code': 'RECAPTCHA_FAILED'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info("reCAPTCHA validé pour password_reset_confirm: score=%s", recaptcha_data.get('score'))
                
            except RecaptchaValidationError as e:
                logger.error("Erreur reCAPTCHA lors de la réinitialisation: %s", str(e))
                return Response({
                    'error': 'Problème de vérification de sécurité',
                    'recaptcha_error': str(e),
                    'recaptcha_required': True,
                    'code': 'RECAPTCHA_ERROR'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # ========== FIN VALIDATION reCAPTCHA ==========
        
        uidb64 = data.get('uid')
        token = data.get('token')
        password = data.get('password')
        password_confirm = data.get('password_confirm')

        # Validation des données requises
        missing_fields = []
        if not uidb64:
            missing_fields.append('uid')
        if not token:
            missing_fields.append('token')
        if not password:
            missing_fields.append('password')
        if not password_confirm:
            missing_fields.append('password_confirm')

        if missing_fields:
            return Response({
                'error': f'Champs requis manquants: {", ".join(missing_fields)}',
                'code': 'MISSING_FIELDS',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier que les mots de passe correspondent
        if password != password_confirm:
            return Response({
                'error': 'Les mots de passe ne correspondent pas.',
                'code': 'PASSWORD_MISMATCH'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Décoder l'uid et récupérer l'utilisateur
        try:
            decoded_bytes = urlsafe_base64_decode(uidb64)
            uid = force_str(decoded_bytes)
            user = User.objects.get(pk=uid)
            logger.info("Utilisateur trouvé: id=%s", user.id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
            logger.error("Erreur lors du décodage ou utilisateur non trouvé: %s: %s", type(e).__name__, str(e))
            return Response({
                'error': 'Lien de réinitialisation invalide ou expiré',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier le token de réinitialisation
        logger.info("Vérification du token de réinitialisation...")
        token_valid = default_token_generator.check_token(user, token)
        logger.info("Token valide: %s", token_valid)
        
        if not token_valid:
            logger.warning("Token de réinitialisation invalide ou expiré pour l'utilisateur %s", user.username)
            password_reset_timeout = getattr(settings, 'PASSWORD_RESET_TIMEOUT', 604800)  # 7 jours par défaut
            error_message = f'Le lien de réinitialisation est invalide ou a expiré. Les liens sont valides pendant {password_reset_timeout // 86400} jours. Veuillez demander une nouvelle réinitialisation.'
            
            return Response({
                'error': error_message,
                'code': 'INVALID_TOKEN'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'utilisateur a un mot de passe utilisable (doit être True pour une réinitialisation)
        has_usable = user.has_usable_password()
        logger.info("Utilisateur a un mot de passe utilisable: %s", has_usable)
        
        if not has_usable:
            logger.warning("Tentative de réinitialisation pour un utilisateur sans mot de passe: %s", user.username)
            return Response({
                'error': 'Cet utilisateur n\'a pas encore défini de mot de passe. Utilisez la fonctionnalité d\'invitation.',
                'code': 'NO_PASSWORD_SET'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider la force du mot de passe
        logger.info("Validation de la force du mot de passe...")
        try:
            validate_password(password, user=user)
            logger.info("Mot de passe validé avec succès")
        except ValidationError as e:
            logger.error("Mot de passe invalide: %s", list(e.messages))
            
            # Traduire les messages d'erreur Django en français
            translated_messages = []
            for msg in e.messages:
                if 'too common' in msg.lower():
                    translated_messages.append('Ce mot de passe est trop commun. Veuillez utiliser un mot de passe plus unique.')
                elif 'too short' in msg.lower():
                    translated_messages.append('Le mot de passe est trop court. Il doit contenir au moins 8 caractères.')
                elif 'too similar' in msg.lower():
                    translated_messages.append('Le mot de passe est trop similaire à vos informations personnelles.')
                elif 'entirely numeric' in msg.lower():
                    translated_messages.append('Le mot de passe ne peut pas être entièrement numérique.')
                else:
                    # Garder le message original si on ne le reconnaît pas
                    translated_messages.append(msg)
            
            return Response({
                'error': 'Mot de passe invalide',
                'details': translated_messages,
                'requirements': [
                    'Au moins 8 caractères',
                    'Ne pas être trop commun',
                    'Ne pas être entièrement numérique',
                    'Contenir au moins une lettre'
                ],
                'code': 'WEAK_PASSWORD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Définir le nouveau mot de passe
        logger.info("Définition du nouveau mot de passe...")
        user.set_password(password)
        user.save()
        logger.info("Mot de passe réinitialisé pour %s", user.username)
        
        # Générer les tokens JWT et connecter automatiquement l'utilisateur
        logger.info("Génération des tokens JWT...")
        try:
            access_token, refresh_token = AuthService.create_tokens(user)
            logger.info("Tokens JWT générés avec succès")
        except Exception as token_error:
            logger.error("ERREUR lors de la génération des tokens: %s", str(token_error))
            import traceback
            logger.error("Traceback tokens: %s", traceback.format_exc())
            raise
        
        # Créer la réponse avec les tokens dans les cookies
        logger.info("Création de la réponse...")
        try:
            user_data = UserSerializer(user).data
            logger.info("Données utilisateur sérialisées: %s", list(user_data.keys()))
        except Exception as serializer_error:
            logger.error("ERREUR lors de la sérialisation de l'utilisateur: %s", str(serializer_error))
            import traceback
            logger.error("Traceback serializer: %s", traceback.format_exc())
            raise
        
        response = Response({
            'message': 'Mot de passe réinitialisé avec succès. Vous êtes maintenant connecté.',
            'user': user_data,
            'success': True
        }, status=status.HTTP_200_OK)
        
        # Définir les cookies d'authentification
        try:
            AuthService.set_auth_cookies(response, access_token, refresh_token)
            logger.info("Cookies d'authentification définis")
        except Exception as cookie_error:
            logger.error("ERREUR lors de la définition des cookies: %s", str(cookie_error))
            import traceback
            logger.error("Traceback cookies: %s", traceback.format_exc())
            raise
        
        # Logger la connexion automatique après réinitialisation
        logger.info("Log de la connexion...")
        try:
            log_user_login(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception as log_error:
            logger.warning("ERREUR lors du log de connexion (non bloquant): %s", str(log_error))
            import traceback
            logger.warning("Traceback log: %s", traceback.format_exc())
        
        # Logger l'activité de réinitialisation
        try:
            log_activity(
                user=user,
                action='update',
                entity_type='user',
                entity_id=str(user.id),
                entity_name=user.username,
                description=f"Mot de passe réinitialisé avec succès pour {user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            logger.info("Log d'activité enregistré pour la réinitialisation du mot de passe de %s", user.username)
        except Exception as log_error:
            logger.warning("ERREUR lors du log d'activité (non bloquant): %s", str(log_error))
        
        logger.info("Réinitialisation finalisée avec succès pour %s", user.username)
        logger.info("=" * 60)
        
        return response
        
    except json.JSONDecodeError as e:
        logger.error("Erreur de parsing JSON: %s", str(e))
        return Response({
            'error': 'Format de données invalide',
            'code': 'INVALID_JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("=" * 60)
        logger.error("ERREUR EXCEPTION dans password_reset_confirm: %s", str(e))
        logger.error("Type d'erreur: %s", type(e).__name__)
        import traceback
        logger.error("Traceback complet:\n%s", traceback.format_exc())
        logger.error("=" * 60)
        return Response({
            'error': f'Erreur lors de la réinitialisation du mot de passe: {str(e)}',
            'code': 'PASSWORD_RESET_CONFIRM_FAILED'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def recaptcha_config(request):
    """Obtenir la configuration reCAPTCHA pour le frontend"""
    try:
        from django.conf import settings
        
        # Nettoyer les cookies si l'utilisateur n'est pas authentifié mais les tokens existent
        if request.user.is_anonymous and request.COOKIES.get('access_token'):
            logger.warning("recaptcha_config: utilisateur anonyme avec access_token -> nettoyage cookies")
            response = Response({
                'enabled': recaptcha_service.is_enabled(),
                'site_key': getattr(settings, 'RECAPTCHA_SITE_KEY', None),
                'min_score': recaptcha_service.get_min_score(),
            }, status=status.HTTP_200_OK)
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response

        config = {
            'enabled': recaptcha_service.is_enabled(),
            'site_key': getattr(settings, 'RECAPTCHA_SITE_KEY', None),
            'min_score': recaptcha_service.get_min_score(),
        }
        
        logger.debug("recaptcha_config: %s", config)
        return Response(config, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération de la config reCAPTCHA: %s", str(e))
        return Response({
            'error': 'Configuration de sécurité indisponible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

