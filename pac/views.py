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
from .models import Pac, TraitementPac, PacSuivi, DetailsPac
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
from .serializers import (
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


class AllowAnyWithJWT(BasePermission):
    """
    Security by Design : permission dédiée aux endpoints de vérification de session.

    Permet aux requêtes anonymes d'atteindre la vue (pas de 401 bloquant)
    TOUT EN laissant le middleware JWT authentifier les requêtes portant un token valide.
    La vue est responsable de retourner des données différentes selon request.user.is_anonymous.

    Différence avec AllowAny :
    - AllowAny : usage générique, sans intention documentée.
    - AllowAnyWithJWT : intention explicite — endpoint public uniquement pour lire le statut auth.
      N'expose aucune donnée sensible pour les utilisateurs anonymes.
    """
    def has_permission(self, request, view):
        return True


# ==================== UTILITAIRES NUM AMENDEMENT ====================

def _get_next_num_amendement_for_pac(user, annee_uuid, processus_uuid):
    """
    Retourne le prochain num_amendement (entier) pour (annee, processus).
    0 = Initial (si aucun PAC n'existe encore), sinon max existant + 1.
    Unicité globale: on vérifie tous les PACs sans filtrer par utilisateur.
    """
    try:
        from django.db.models import Max
        logger.info(f"[_get_next_num_amendement_for_pac] annee_uuid={annee_uuid}, processus_uuid={processus_uuid}")
        result = Pac.objects.filter(
            annee_id=annee_uuid,
            processus_id=processus_uuid
        ).aggregate(max_num=Max('num_amendement'))
        max_num = result['max_num']
        next_num = 0 if max_num is None else max_num + 1
        logger.info(f"[_get_next_num_amendement_for_pac] next_num={next_num}")
        return next_num
    except Exception as e:
        logger.error(f"[_get_next_num_amendement_for_pac] Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise



# ==================== AUTHENTIFICATION ====================

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
                    logger.warning(f"reCAPTCHA validation échouée pour l'inscription: {recaptcha_data}")
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info(f"reCAPTCHA validé pour l'inscription: score={recaptcha_data.get('score')}")
                
            except RecaptchaValidationError as e:
                logger.error(f"Erreur reCAPTCHA lors de l'inscription: {str(e)}")
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
        logger.error(f"Erreur lors de la création de l'utilisateur: {str(e)}")
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
                    logger.warning(f"reCAPTCHA validation échouée pour la connexion: {recaptcha_data}")
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info(f"reCAPTCHA validé pour la connexion: score={recaptcha_data.get('score')}")
                
            except RecaptchaValidationError as e:
                logger.error(f"Erreur reCAPTCHA lors de la connexion: {str(e)}")
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
                    logger.warning(f"[SECURITY] IP bloquée: {ip} ({ip_count} échecs)")

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
                    logger.warning(f"[SECURITY] Email bloqué: {email} ({email_count} échecs)")

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
        logger.error(f"Erreur lors de la connexion: {str(e)}")
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
        logger.error(f"Erreur lors de la déconnexion: {str(e)}")
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
            logger.warning(f"Refresh token invalide: {str(e)}")
            return Response({
                'error': 'Refresh token invalide',
                'details': str(e),
                'code': 'REFRESH_TOKEN_INVALID'
            }, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.error(f"Erreur lors du rafraîchissement du token: {str(e)}")
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

        logger.debug(f"user_profile appelé pour user: {request.user}")
        serializer = UserSerializer(request.user)
        return Response({
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du profil: {str(e)}")
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
        logger.error(f"Erreur lors de la mise à jour du profil: {str(e)}")
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
        logger.error(f"Erreur lors de la mise à jour du profil par admin: {str(e)}")
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
        logger.error(f"Erreur lors du changement de mot de passe: {str(e)}")
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
        logger.info(f"IP: {get_client_ip(request)}")
        
        # Récupérer les paramètres depuis la query string
        uidb64 = request.GET.get('uid')
        token = request.GET.get('token')
        
        logger.info(f"uidb64: {uidb64}")
        logger.info(f"token: {token[:20] if token else None}...")
        
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
            logger.info(f"Utilisateur trouvé: username={user.username}, email={user.email}, id={user.id}, is_active={user.is_active}, has_usable_password={user.has_usable_password()}")
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
            logger.warning(f"Erreur lors du décodage ou utilisateur non trouvé: {str(e)}")
            return Response({
                'valid': False,
                'error': 'Lien d\'invitation invalide',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # IMPORTANT : Vérifier d'abord si le compte a déjà un mot de passe défini
        # Car quand le mot de passe est défini, le token devient invalide automatiquement
        # Il faut donc vérifier has_usable_password() AVANT de vérifier le token
        has_usable = user.has_usable_password()
        logger.info(f"Utilisateur a un mot de passe utilisable: {has_usable}")
        
        if has_usable:
            logger.info(f"Lien d'invitation déjà utilisé pour {user.username} (mot de passe déjà défini)")
            return Response({
                'valid': True,
                'already_used': True,
                'message': 'Ce lien d\'invitation a déjà été utilisé. Votre compte est déjà activé.',
                'code': 'INVITATION_ALREADY_USED',
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'is_active': user.is_active
                }
            }, status=status.HTTP_200_OK)
        
        # Vérifier le token d'invitation seulement si le mot de passe n'est pas encore défini
        token_valid = default_token_generator.check_token(user, token)
        logger.info(f"Token valide: {token_valid}")
        
        if not token_valid:
            logger.warning(f"Token d'invitation invalide ou expiré pour l'utilisateur {user.username}")
            return Response({
                'valid': False,
                'error': 'Lien d\'invitation invalide ou expiré',
                'code': 'INVALID_TOKEN'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Le lien est valide et n'a pas encore été utilisé
        logger.info(f"Lien d'invitation valide et disponible pour {user.username}")
        return Response({
            'valid': True,
            'already_used': False,
            'message': 'Lien d\'invitation valide',
            'code': 'INVITATION_VALID',
            'user': {
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"ERREUR EXCEPTION dans check_invitation: {str(e)}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback complet:\n{traceback.format_exc()}")
        logger.error("=" * 60)
        return Response({
            'valid': False,
            'error': f'Erreur lors de la vérification du lien: {str(e)}',
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
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Method: {request.method}")
        logger.info(f"IP: {get_client_ip(request)}")
        
        # ========== RATE LIMITING (Security by Design) ==========
        # Protection contre les attaques par force brute sur les tokens
        from django.core.cache import cache
        
        client_ip = get_client_ip(request)
        rate_limit_key = f'invitation_complete_rate_limit_{client_ip}'
        attempts = cache.get(rate_limit_key, 0)
        max_attempts = 5  # Maximum 5 tentatives par IP par heure
        rate_limit_window = 3600  # 1 heure
        
        if attempts >= max_attempts:
            logger.warning(f"Rate limit dépassé pour complete_invitation depuis IP: {client_ip}")
            return Response({
                'error': 'Trop de tentatives. Veuillez réessayer dans 1 heure.',
                'code': 'RATE_LIMIT_EXCEEDED'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Incrémenter le compteur
        cache.set(rate_limit_key, attempts + 1, rate_limit_window)
        # ========== FIN RATE LIMITING ==========
        
        logger.info(f"request.data type: {type(request.data)}")
        logger.info(f"request.data: {request.data}")

        # IMPORTANT : ne plus toucher à request.body ici, DRF l'a déjà consommé
        # On se fie uniquement à request.data, qui contient déjà les données parsées
        data = request.data
        
        # ========== VALIDATION reCAPTCHA (Security by Design) ==========
        # Protection contre les bots et les attaques automatisées
        if recaptcha_service.is_enabled():
            recaptcha_token = data.get('recaptcha_token')
            if not recaptcha_token:
                logger.warning(f"reCAPTCHA token manquant pour complete_invitation depuis IP: {client_ip}")
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
                    logger.warning(f"reCAPTCHA validation échouée pour complete_invitation: {recaptcha_data}")
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True,
                        'code': 'RECAPTCHA_FAILED'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info(f"reCAPTCHA validé pour complete_invitation: score={recaptcha_data.get('score')}")
                
            except RecaptchaValidationError as e:
                logger.error(f"Erreur reCAPTCHA lors de la finalisation de l'invitation: {str(e)}")
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
        
        logger.info(f"uidb64: {uidb64}")
        logger.info(f"token: {token[:20] if token else None}...")
        logger.info(f"password présent: {bool(password)}")
        logger.info(f"password_confirm présent: {bool(password_confirm)}")
        
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
            logger.error(f"Champs manquants: {missing_fields}")
            return Response({
                'error': f'Champs requis manquants: {", ".join(missing_fields)}',
                'code': 'MISSING_FIELDS',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que les mots de passe correspondent
        if password != password_confirm:
            logger.error(f"Les mots de passe ne correspondent pas")
            return Response({
                'error': 'Les mots de passe ne correspondent pas.',
                'code': 'PASSWORD_MISMATCH'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info("Mots de passe correspondent, décodage de l'uid...")
        
        # Décoder l'uid et récupérer l'utilisateur
        try:
            decoded_bytes = urlsafe_base64_decode(uidb64)
            logger.info(f"uidb64 décodé en bytes: {decoded_bytes}")
            uid = force_str(decoded_bytes)
            logger.info(f"uid décodé (string): {uid}")
            user = User.objects.get(pk=uid)
            logger.info(f"Utilisateur trouvé: username={user.username}, email={user.email}, id={user.id}, is_active={user.is_active}, has_usable_password={user.has_usable_password()}")
        except TypeError as e:
            logger.error(f"TypeError lors du décodage: {str(e)}")
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (TypeError)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            logger.error(f"ValueError lors du décodage: {str(e)}")
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (ValueError)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except OverflowError as e:
            logger.error(f"OverflowError lors du décodage: {str(e)}")
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (OverflowError)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            logger.error(f"Utilisateur non trouvé avec uid: {uid}")
            return Response({
                'error': 'Lien d\'invitation invalide ou expiré (User not found)',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Exception inattendue lors du décodage: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                'error': f'Erreur lors du décodage du lien: {str(e)}',
                'code': 'DECODE_ERROR'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier le token d'invitation
        logger.info("Vérification du token d'invitation...")
        token_valid = default_token_generator.check_token(user, token)
        logger.info(f"Token valide: {token_valid}")
        
        if not token_valid:
            logger.warning(f"Token d'invitation invalide ou expiré pour l'utilisateur {user.username}")
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
        logger.info(f"Utilisateur a un mot de passe utilisable: {has_usable}")
        
        if has_usable:
            logger.warning(f"Tentative d'utilisation d'un lien d'invitation déjà utilisé pour: {user.username}")
            
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
                logger.warning(f"ERREUR lors du log d'audit (non bloquant): {str(log_error)}")
            
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
            logger.error(f"Mot de passe invalide: {list(e.messages)}")
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
        logger.info(f"Compte activé et mot de passe défini pour {user.username}")
        
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
            logger.info(f"Log d'activité enregistré pour l'activation du compte de {user.username}")
        except Exception as log_error:
            logger.warning(f"ERREUR lors du log d'activité (non bloquant): {str(log_error)}")
            import traceback
            logger.warning(f"Traceback log activité: {traceback.format_exc()}")
            # Ne pas bloquer si le log échoue
        
        # Générer les tokens JWT et connecter automatiquement l'utilisateur
        logger.info("Génération des tokens JWT...")
        try:
            access_token, refresh_token = AuthService.create_tokens(user)
            logger.info("Tokens JWT générés avec succès")
        except Exception as token_error:
            logger.error(f"ERREUR lors de la génération des tokens: {str(token_error)}")
            import traceback
            logger.error(f"Traceback tokens: {traceback.format_exc()}")
            raise
        
        # Créer la réponse avec les tokens dans les cookies
        logger.info("Création de la réponse...")
        try:
            user_data = UserSerializer(user).data
            logger.info(f"Données utilisateur sérialisées: {list(user_data.keys())}")
        except Exception as serializer_error:
            logger.error(f"ERREUR lors de la sérialisation de l'utilisateur: {str(serializer_error)}")
            import traceback
            logger.error(f"Traceback serializer: {traceback.format_exc()}")
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
            logger.error(f"ERREUR lors de la définition des cookies: {str(cookie_error)}")
            import traceback
            logger.error(f"Traceback cookies: {traceback.format_exc()}")
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
            logger.warning(f"ERREUR lors du log de connexion (non bloquant): {str(log_error)}")
            import traceback
            logger.warning(f"Traceback log: {traceback.format_exc()}")
            # Ne pas bloquer si le log échoue
        
        logger.info(f"Invitation finalisée avec succès pour {user.username}")
        logger.info("=" * 60)
        
        return response
        
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de parsing JSON: {str(e)}")
        return Response({
            'error': 'Format de données invalide',
            'code': 'INVALID_JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"ERREUR EXCEPTION dans complete_invitation: {str(e)}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback complet:\n{traceback.format_exc()}")
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
        logger.info(f"Utilisateur qui demande: {request.user.username} (is_staff={request.user.is_staff}, is_superuser={request.user.is_superuser})")
        logger.info(f"IP: {get_client_ip(request)}")
        
        # ========== VÉRIFICATION DE SÉCURITÉ ==========
        from parametre.permissions import can_manage_users
        can_manage = can_manage_users(request.user)
        logger.info(f"can_manage_users: {can_manage}")
        
        if not can_manage:
            logger.warning(f"Accès refusé pour {request.user.username}")
            return Response({
                'success': False,
                'error': 'Accès refusé. Seuls les utilisateurs avec "Staff status" et "Superuser status" peuvent demander une réinitialisation de mot de passe.',
                'code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Rate limiting pour éviter le spam
        user_limit_ok = EmailRateLimiter.check_user_limit(request.user.id)
        global_limit_ok = EmailRateLimiter.check_global_limit()
        logger.info(f"Rate limiting - user_limit: {user_limit_ok}, global_limit: {global_limit_ok}")
        
        if not user_limit_ok or not global_limit_ok:
            SecureEmailLogger.log_security_event('password_reset_rate_limit_exceeded', {
                'user': request.user.username,
                'ip': get_client_ip(request),
                'type': 'password_reset_request'
            })
            logger.warning(f"Rate limit dépassé pour {request.user.username}")
            return Response({
                'success': False,
                'error': "Trop de tentatives de réinitialisation, veuillez réessayer plus tard."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Récupérer l'email depuis les données
        email = request.data.get('email', '').strip()
        logger.info(f"Email reçu pour réinitialisation: {email}")
        
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
            logger.info(f"Utilisateur trouvé: username={user.username}, email={user.email}, id={user.id}, is_active={user.is_active}")
        except User.DoesNotExist:
            # Security by Design : Ne pas révéler si l'email existe ou non
            # Retourner un succès générique pour éviter l'énumération d'emails
            logger.warning(f"Email non trouvé pour réinitialisation: {email}")
            return Response({
                'success': True,
                'message': 'Si cet email existe dans notre système, un lien de réinitialisation a été envoyé.'
            }, status=status.HTTP_200_OK)
        
        # Vérifier que l'utilisateur a un mot de passe utilisable (sinon c'est une invitation, pas une réinitialisation)
        if not user.has_usable_password():
            logger.warning(f"Tentative de réinitialisation pour un utilisateur sans mot de passe: {user.username}")
            return Response({
                'success': False,
                'error': 'Cet utilisateur n\'a pas encore défini de mot de passe. Utilisez la fonctionnalité d\'invitation.',
                'code': 'NO_PASSWORD_SET'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Générer un token de réinitialisation
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        logger.info(f"Token de réinitialisation généré: uid={uid}, token={token[:20]}...")
        
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
        logger.info(f"Envoi de l'email de réinitialisation à {user.email}...")
        logger.info(f"URL de réinitialisation: {reset_url}")
        
        try:
            send_mail(
                subject=subject,
                message=text_body,
                html_message=html_body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', user.email),
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email envoyé avec succès à {user.email}")
        except Exception as email_error:
            logger.error(f"ERREUR lors de l'envoi de l'email: {str(email_error)}")
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
        
        logger.info(f"Demande de réinitialisation terminée avec succès pour {user.email}")
        logger.info("=" * 60)
        
        return Response({
            'success': True,
            'message': f"Email de réinitialisation envoyé avec succès à {user.email}."
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"ERREUR EXCEPTION dans password_reset_request: {str(e)}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback complet:\n{traceback.format_exc()}")
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
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Method: {request.method}")
        logger.info(f"IP: {get_client_ip(request)}")
        
        # ========== RATE LIMITING (Security by Design) ==========
        from django.core.cache import cache
        
        client_ip = get_client_ip(request)
        rate_limit_key = f'password_reset_confirm_rate_limit_{client_ip}'
        attempts = cache.get(rate_limit_key, 0)
        max_attempts = 5  # Maximum 5 tentatives par IP par heure
        rate_limit_window = 3600  # 1 heure
        
        if attempts >= max_attempts:
            logger.warning(f"Rate limit dépassé pour password_reset_confirm depuis IP: {client_ip}")
            return Response({
                'error': 'Trop de tentatives. Veuillez réessayer dans 1 heure.',
                'code': 'RATE_LIMIT_EXCEEDED'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Incrémenter le compteur
        cache.set(rate_limit_key, attempts + 1, rate_limit_window)
        # ========== FIN RATE LIMITING ==========
        
        logger.info(f"request.data type: {type(request.data)}")
        logger.info(f"request.data: {request.data}")
        
        data = request.data
        
        # ========== VALIDATION reCAPTCHA (Security by Design) ==========
        if recaptcha_service.is_enabled():
            recaptcha_token = data.get('recaptcha_token')
            if not recaptcha_token:
                logger.warning(f"reCAPTCHA token manquant pour password_reset_confirm depuis IP: {client_ip}")
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
                    logger.warning(f"reCAPTCHA validation échouée pour password_reset_confirm: {recaptcha_data}")
                    return Response({
                        'error': 'Vérification de sécurité échouée',
                        'recaptcha_error': recaptcha_data.get('error'),
                        'recaptcha_required': True,
                        'code': 'RECAPTCHA_FAILED'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                logger.info(f"reCAPTCHA validé pour password_reset_confirm: score={recaptcha_data.get('score')}")
                
            except RecaptchaValidationError as e:
                logger.error(f"Erreur reCAPTCHA lors de la réinitialisation: {str(e)}")
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
        
        logger.info(f"uidb64: {uidb64}")
        logger.info(f"token: {token[:20] if token else None}...")
        logger.info(f"password présent: {bool(password)}")
        logger.info(f"password_confirm présent: {bool(password_confirm)}")
        
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
            logger.error(f"Champs manquants: {missing_fields}")
            return Response({
                'error': f'Champs requis manquants: {", ".join(missing_fields)}',
                'code': 'MISSING_FIELDS',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que les mots de passe correspondent
        if password != password_confirm:
            logger.error(f"Les mots de passe ne correspondent pas")
            return Response({
                'error': 'Les mots de passe ne correspondent pas.',
                'code': 'PASSWORD_MISMATCH'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info("Mots de passe correspondent, décodage de l'uid...")
        
        # Décoder l'uid et récupérer l'utilisateur
        try:
            decoded_bytes = urlsafe_base64_decode(uidb64)
            logger.info(f"uidb64 décodé en bytes: {decoded_bytes}")
            uid = force_str(decoded_bytes)
            logger.info(f"uid décodé (string): {uid}")
            user = User.objects.get(pk=uid)
            logger.info(f"Utilisateur trouvé: username={user.username}, email={user.email}, id={user.id}, is_active={user.is_active}, has_usable_password={user.has_usable_password()}")
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
            logger.error(f"Erreur lors du décodage ou utilisateur non trouvé: {type(e).__name__}: {str(e)}")
            return Response({
                'error': 'Lien de réinitialisation invalide ou expiré',
                'code': 'INVALID_LINK'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier le token de réinitialisation
        logger.info("Vérification du token de réinitialisation...")
        token_valid = default_token_generator.check_token(user, token)
        logger.info(f"Token valide: {token_valid}")
        
        if not token_valid:
            logger.warning(f"Token de réinitialisation invalide ou expiré pour l'utilisateur {user.username}")
            password_reset_timeout = getattr(settings, 'PASSWORD_RESET_TIMEOUT', 604800)  # 7 jours par défaut
            error_message = f'Le lien de réinitialisation est invalide ou a expiré. Les liens sont valides pendant {password_reset_timeout // 86400} jours. Veuillez demander une nouvelle réinitialisation.'
            
            return Response({
                'error': error_message,
                'code': 'INVALID_TOKEN'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'utilisateur a un mot de passe utilisable (doit être True pour une réinitialisation)
        has_usable = user.has_usable_password()
        logger.info(f"Utilisateur a un mot de passe utilisable: {has_usable}")
        
        if not has_usable:
            logger.warning(f"Tentative de réinitialisation pour un utilisateur sans mot de passe: {user.username}")
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
            logger.error(f"Mot de passe invalide: {list(e.messages)}")
            
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
        logger.info(f"Mot de passe réinitialisé pour {user.username}")
        
        # Générer les tokens JWT et connecter automatiquement l'utilisateur
        logger.info("Génération des tokens JWT...")
        try:
            access_token, refresh_token = AuthService.create_tokens(user)
            logger.info("Tokens JWT générés avec succès")
        except Exception as token_error:
            logger.error(f"ERREUR lors de la génération des tokens: {str(token_error)}")
            import traceback
            logger.error(f"Traceback tokens: {traceback.format_exc()}")
            raise
        
        # Créer la réponse avec les tokens dans les cookies
        logger.info("Création de la réponse...")
        try:
            user_data = UserSerializer(user).data
            logger.info(f"Données utilisateur sérialisées: {list(user_data.keys())}")
        except Exception as serializer_error:
            logger.error(f"ERREUR lors de la sérialisation de l'utilisateur: {str(serializer_error)}")
            import traceback
            logger.error(f"Traceback serializer: {traceback.format_exc()}")
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
            logger.error(f"ERREUR lors de la définition des cookies: {str(cookie_error)}")
            import traceback
            logger.error(f"Traceback cookies: {traceback.format_exc()}")
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
            logger.warning(f"ERREUR lors du log de connexion (non bloquant): {str(log_error)}")
            import traceback
            logger.warning(f"Traceback log: {traceback.format_exc()}")
        
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
            logger.info(f"Log d'activité enregistré pour la réinitialisation du mot de passe de {user.username}")
        except Exception as log_error:
            logger.warning(f"ERREUR lors du log d'activité (non bloquant): {str(log_error)}")
        
        logger.info(f"Réinitialisation finalisée avec succès pour {user.username}")
        logger.info("=" * 60)
        
        return response
        
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de parsing JSON: {str(e)}")
        return Response({
            'error': 'Format de données invalide',
            'code': 'INVALID_JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"ERREUR EXCEPTION dans password_reset_confirm: {str(e)}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback complet:\n{traceback.format_exc()}")
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
        
        logger.debug(f"recaptcha_config: {config}")
        return Response(config, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la config reCAPTCHA: {str(e)}")
        return Response({
            'error': 'Configuration de sécurité indisponible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API PROCESSUS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processus_list(request):
    """Liste des processus de l'utilisateur connecté"""
    try:
        processus = Processus.objects.filter(cree_par=request.user).order_by('-created_at')
        serializer = ProcessusSerializer(processus, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des processus: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les processus'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def processus_create(request):
    """Créer un nouveau processus"""
    try:
        serializer = ProcessusCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            processus = serializer.save()
            return Response(ProcessusSerializer(processus).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du processus: {str(e)}")
        return Response({
            'error': 'Impossible de créer le processus'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processus_detail(request, uuid):
    """Détails d'un processus"""
    try:
        processus = Processus.objects.get(uuid=uuid)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus.uuid):
            return Response({
                'error': 'Vous n\'avez pas accès à ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        serializer = ProcessusSerializer(processus)
        return Response(serializer.data)
    except Processus.DoesNotExist:
        return Response({
            'error': 'Processus non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du processus: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le processus'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, PacListPermission])
def pac_list(request):
    """Liste des PACs de l'utilisateur connecté avec leurs détails"""
    try:
        logger.info(f"[pac_list] Utilisateur connecté: {request.user.username} (ID: {request.user.id})")

        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les PACs sans filtre
            pacs = Pac.objects.all().select_related(
            'processus', 'cree_par', 'annee', 'validated_by'
        ).prefetch_related(
            'details__dysfonctionnement_recommandation',
            'details__nature',
            'details__categorie',
            'details__source'
        )
        elif not user_processus_uuids:
            logger.info(f"[pac_list] Aucun processus assigné pour l'utilisateur {request.user.username}")
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun PAC trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Filtrer les PACs par les processus où l'utilisateur a un rôle actif
            pacs = Pac.objects.filter(processus__uuid__in=user_processus_uuids).select_related(
                'processus', 'cree_par', 'annee', 'validated_by'
            ).prefetch_related(
                'details__dysfonctionnement_recommandation',
                'details__nature',
                'details__categorie',
                'details__source'
            )
        # ========== FIN FILTRAGE ==========

        logger.info(f"[pac_list] Nombre de PACs pour l'utilisateur {request.user.username}: {pacs.count()}")

        # Utiliser PacCompletSerializer pour inclure les détails
        serializer = PacCompletSerializer(pacs, many=True)
        logger.info(f"[pac_list] Données sérialisées: {len(serializer.data)} PACs")
        return Response({
            'success': True,
            'data': serializer.data,
            'count': pacs.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des PACs: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les PACs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACCreatePermission])
def pac_create(request):
    """
    Créer un nouveau PAC.
    Validation stricte: un seul PAC par (processus, annee, num_amendement).
    Retourne 400 si doublon.
    """
    try:
        logger.info(f"[pac_create] Données reçues: {request.data}")
        data = request.data.copy()
        clone = str(data.pop('clone', 'false')).lower() in ['1', 'true', 'yes', 'on']

        annee_uuid = data.get('annee')
        processus_uuid = data.get('processus')
        try:
            num_amendement = int(data.get('num_amendement', 0))
        except (ValueError, TypeError):
            num_amendement = 0

        if not annee_uuid or not processus_uuid:
            return Response({
                'success': False,
                'error': "Les champs 'annee' et 'processus' sont requis."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': "Vous n'avez pas accès à ce processus. Vous n'avez pas de rôle actif pour ce processus."
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # VALIDATION 1 : Si INITIAL (num_amendement == 0), vérifier qu'il n'existe pas déjà
        if num_amendement == 0:
            existing = Pac.objects.filter(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=0
            ).exists()
            if existing:
                return Response({
                    'success': False,
                    'error': "Un PAC initial existe déjà pour cette année et ce processus. Vous ne pouvez créer que des amendements."
                }, status=status.HTTP_400_BAD_REQUEST)

        # VALIDATION 2 : Si amendement, vérifier que le précédent existe et est validé
        else:
            prev_num = num_amendement - 1
            try:
                pac_prev = Pac.objects.get(
                    annee_id=annee_uuid,
                    processus_id=processus_uuid,
                    num_amendement=prev_num
                )
            except Pac.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f"Impossible de créer l'amendement {num_amendement} : l'amendement {prev_num} n'existe pas pour cette année et ce processus."
                }, status=status.HTTP_400_BAD_REQUEST)
            if not pac_prev.is_validated:
                return Response({
                    'success': False,
                    'error': f"Impossible de créer l'amendement {num_amendement} : l'amendement {prev_num} doit être validé d'abord."
                }, status=status.HTTP_400_BAD_REQUEST)
            existing_num = Pac.objects.filter(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=num_amendement
            ).exists()
            if existing_num:
                return Response({
                    'success': False,
                    'error': f"L'amendement {num_amendement} existe déjà pour cette année et ce processus."
                }, status=status.HTTP_400_BAD_REQUEST)
            # initial_ref = le PAC initial (num_amendement == 0)
            pac_initial = Pac.objects.get(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=0
            )
            data['initial_ref'] = str(pac_initial.uuid)

        data['num_amendement'] = num_amendement

        # ========== CRÉATION ==========
        serializer = PacCreateSerializer(data=data, context={'request': request})
        if not serializer.is_valid():
            logger.error(f"[pac_create] Erreurs de validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pac = serializer.save()
        logger.info(f"[pac_create] PAC créé: {pac.uuid}")

        log_pac_creation(
            user=request.user,
            pac=pac,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        # Clone des détails si amendement et clone demandé
        if num_amendement > 0 and clone:
            # Source = PAC du numéro précédent
            source_pac = Pac.objects.filter(
                annee_id=annee_uuid,
                processus_id=processus_uuid,
                num_amendement=num_amendement - 1
            ).first()
            if source_pac:
                details_with_suivi = source_pac.details.select_related(
                    'traitement', 'traitement__suivi',
                    'traitement__suivi__etat_mise_en_oeuvre', 'traitement__suivi__appreciation',
                    'traitement__suivi__preuve', 'traitement__suivi__statut'
                ).all()
                clone_count = 0
                for detail in details_with_suivi:
                    new_detail = DetailsPac.objects.create(
                        pac=pac,
                        numero_pac=detail.numero_pac,
                        libelle=detail.libelle,
                        dysfonctionnement_recommandation=detail.dysfonctionnement_recommandation,
                        nature=detail.nature,
                        categorie=detail.categorie,
                        source=detail.source,
                        periode_de_realisation=detail.periode_de_realisation,
                    )
                    if hasattr(detail, 'traitement') and detail.traitement:
                        t = detail.traitement
                        new_traitement = TraitementPac.objects.create(
                            details_pac=new_detail,
                            action=t.action,
                            type_action=t.type_action,
                            delai_realisation=t.delai_realisation,
                            responsable_direction=t.responsable_direction,
                            responsable_sous_direction=t.responsable_sous_direction,
                        )
                        if hasattr(t, 'responsables_directions'):
                            new_traitement.responsables_directions.set(t.responsables_directions.all())
                        if hasattr(t, 'responsables_sous_directions'):
                            new_traitement.responsables_sous_directions.set(t.responsables_sous_directions.all())
                        # Copier le suivi si présent
                        if hasattr(t, 'suivi') and t.suivi:
                            s = t.suivi
                            if s.etat_mise_en_oeuvre and s.appreciation:
                                PacSuivi.objects.create(
                                    traitement=new_traitement,
                                    etat_mise_en_oeuvre=s.etat_mise_en_oeuvre,
                                    resultat=s.resultat,
                                    appreciation=s.appreciation,
                                    preuve=s.preuve,
                                    statut=s.statut,
                                    date_mise_en_oeuvre_effective=s.date_mise_en_oeuvre_effective,
                                    date_cloture=s.date_cloture,
                                    cree_par=request.user,
                                )
                    clone_count += 1
                # Audit: log du clonage (Security by Design)
                if clone_count > 0:
                    try:
                        log_activity(
                            user=request.user,
                            action='clone',
                            entity_type='pac',
                            entity_id=str(pac.uuid),
                            entity_name=f"PAC {pac.uuid}",
                            description=f"Clonage d'amendement depuis {source_pac.uuid} (amendement {num_amendement - 1}) - {clone_count} détails copiés",
                            ip_address=get_client_ip(request),
                            user_agent=request.META.get('HTTP_USER_AGENT')
                        )
                    except Exception as log_err:
                        logger.warning(f"[pac_create] Erreur log clonage: {log_err}")

        return Response({
            'success': True,
            'message': 'PAC créé avec succès',
            'data': PacSerializer(pac).data
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        import traceback
        logger.error(f"[pac_create] Erreur: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'success': False,
            'error': 'Impossible de créer le PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PacDetailPermission])
def pac_detail(request, uuid):
    """Détails d'un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid)
        
        serializer = PacSerializer(pac)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'success': False,
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du PAC: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer le PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PacDetailPermission])
def pac_complet(request, uuid):
    """Récupérer un PAC complet avec tous ses traitements et suivis"""
    try:
        pac = Pac.objects.select_related(
            'processus', 'cree_par', 'annee'
        ).prefetch_related(
            'details__dysfonctionnement_recommandation',
            'details__nature',
            'details__categorie',
            'details__source',
            'details__traitement__type_action',
            'details__traitement__responsable_direction',
            'details__traitement__responsable_sous_direction',
            'details__traitement__preuve__medias',
            'details__traitement__suivi__etat_mise_en_oeuvre',
            'details__traitement__suivi__appreciation',
            'details__traitement__suivi__statut',
            'details__traitement__suivi__cree_par',
            'details__traitement__suivi__preuve__medias'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par PacDetailPermission
        # via le décorateur @permission_classes
        
        serializer = PacCompletSerializer(pac)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'success': False,
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du PAC complet: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer le PAC complet'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACCreatePermission])
def pac_get_or_create(request):
    """
    Récupérer ou créer un PAC unique pour (processus, annee, num_amendement).
    Si num_amendement est absent, le calcule automatiquement.
    """
    try:
        logger.info(f"[pac_get_or_create] Début - données reçues: {request.data}")
        data = request.data

        def _to_uuid(val):
            if val is None:
                return None
            if isinstance(val, str) and val.strip():
                return val.strip()
            if hasattr(val, 'uuid'):
                return str(getattr(val, 'uuid'))
            if isinstance(val, dict) and val.get('uuid'):
                return str(val['uuid'])
            return str(val) if val else None

        annee_uuid = _to_uuid(data.get('annee'))
        processus_uuid = _to_uuid(data.get('processus'))
        initial_ref_uuid = _to_uuid(data.get('initial_ref'))

        # Résoudre num_amendement
        raw_num = data.get('num_amendement')
        if raw_num is not None:
            try:
                num_amendement = int(raw_num)
            except (ValueError, TypeError):
                num_amendement = None
        else:
            num_amendement = None

        logger.info(f"[pac_get_or_create] annee_uuid={annee_uuid}, processus_uuid={processus_uuid}, num_amendement={num_amendement}")

        if not (annee_uuid and processus_uuid):
            logger.warning("[pac_get_or_create] annee ou processus manquant")
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis. 'num_amendement' peut être omis et sera déterminé automatiquement."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': "Vous n'avez pas accès à ce processus. Vous n'avez pas de rôle actif pour ce processus."
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Auto-calculer num_amendement si absent
        if num_amendement is None:
            logger.info("[pac_get_or_create] num_amendement absent, calcul automatique")
            try:
                num_amendement = _get_next_num_amendement_for_pac(request.user, annee_uuid, processus_uuid)
                logger.info(f"[pac_get_or_create] num_amendement automatique: {num_amendement}")
            except Exception as tt_error:
                logger.error(f"[pac_get_or_create] Erreur calcul num_amendement: {tt_error}")
                import traceback
                logger.error(traceback.format_exc())
                return Response({
                    'error': 'Impossible de déterminer le numéro d\'amendement.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ========== VÉRIFICATION DES PERMISSIONS ==========
        is_creating_amendement = (num_amendement > 0) or bool(initial_ref_uuid)
        if is_creating_amendement:
            amendement_permission = PACAmendementCreatePermission()
            if not amendement_permission.has_permission(request, None):
                return Response({
                    'success': False,
                    'error': "Vous n'avez pas les permissions nécessaires pour créer un amendement PAC."
                }, status=status.HTTP_403_FORBIDDEN)
        else:
            try:
                pac_create_permission = PACCreatePermission()
                pac_create_permission.has_permission(request, None)
            except PermissionDenied as e:
                return Response({
                    'success': False,
                    'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un PAC."
                }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION DES PERMISSIONS ==========

        # Vérifier si un PAC existe déjà avec ce (processus, annee, num_amendement)
        try:
            pac = Pac.objects.get(
                processus__uuid=processus_uuid,
                annee__uuid=annee_uuid,
                num_amendement=num_amendement,
            )
            logger.info(f"[pac_get_or_create] PAC existant trouvé: {pac.uuid}")
            serializer = PacSerializer(pac)
            response_data = dict(serializer.data)
            response_data['created'] = False
            return Response(response_data, status=status.HTTP_200_OK)

        except Pac.DoesNotExist:
            logger.info(f"[pac_get_or_create] Aucun PAC existant, création d'un nouveau PAC")

            from django.http import QueryDict
            if isinstance(data, QueryDict):
                data = data.copy()
            elif not isinstance(data, dict):
                data = dict(data) if hasattr(data, 'items') else {}

            # Pour un amendement, trouver/valider l'initial_ref automatiquement
            if num_amendement > 0 and not initial_ref_uuid:
                pac_initial = Pac.objects.filter(
                    annee_id=annee_uuid,
                    processus_id=processus_uuid,
                    num_amendement=0
                ).first()
                if not pac_initial:
                    return Response({
                        'error': 'Aucun PAC initial trouvé pour créer cet amendement. Veuillez d\'abord créer et valider un PAC initial.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                if not pac_initial.is_validated:
                    return Response({
                        'error': 'Le PAC initial doit être validé avant de pouvoir créer un amendement.',
                        'initial_pac_uuid': str(pac_initial.uuid)
                    }, status=status.HTTP_400_BAD_REQUEST)
                initial_ref_uuid = str(pac_initial.uuid)
            elif num_amendement > 0 and initial_ref_uuid:
                try:
                    pac_initial = Pac.objects.get(uuid=initial_ref_uuid)
                    if not pac_initial.is_validated:
                        return Response({
                            'error': 'Le PAC initial doit être validé avant de pouvoir créer un amendement.',
                            'initial_pac_uuid': str(initial_ref_uuid)
                        }, status=status.HTTP_400_BAD_REQUEST)
                except Pac.DoesNotExist:
                    return Response({
                        'error': 'Le PAC initial spécifié n\'existe pas.'
                    }, status=status.HTTP_400_BAD_REQUEST)

            create_payload = {
                'processus': processus_uuid,
                'annee': annee_uuid,
                'num_amendement': num_amendement,
            }
            if initial_ref_uuid:
                create_payload['initial_ref'] = initial_ref_uuid
            logger.info(f"[pac_get_or_create] Payload création: {create_payload}")
            create_serializer = PacCreateSerializer(data=create_payload, context={'request': request})

            if create_serializer.is_valid():
                logger.info("[pac_get_or_create] Serializer valide, sauvegarde...")
                try:
                    pac = create_serializer.save()
                    logger.info(f"[pac_get_or_create] PAC créé avec succès: {pac.uuid}")
                except Exception as save_error:
                    logger.error(f"[pac_get_or_create] Erreur lors de la sauvegarde: {save_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    if 'UNIQUE constraint' in str(save_error):
                        try:
                            pac = Pac.objects.get(
                                processus__uuid=processus_uuid,
                                annee__uuid=annee_uuid,
                                num_amendement=num_amendement,
                            )
                            serializer = PacSerializer(pac)
                            response_data = dict(serializer.data)
                            response_data['created'] = False
                            return Response(response_data, status=status.HTTP_200_OK)
                        except Pac.DoesNotExist:
                            pass
                    return Response({
                        'error': 'Erreur lors de la sauvegarde du PAC',
                        'details': str(save_error)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                try:
                    log_pac_creation(
                        user=request.user,
                        pac=pac,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT')
                    )
                except Exception as log_error:
                    logger.error(f"[pac_get_or_create] Erreur log (non bloquant): {log_error}")

                try:
                    serializer = PacSerializer(pac)
                    response_data = dict(serializer.data)
                    response_data['created'] = True
                    return Response(response_data, status=status.HTTP_201_CREATED)
                except Exception as serializer_error:
                    logger.error(f"[pac_get_or_create] Erreur sérialisation: {serializer_error}")
                    return Response({
                        'error': 'Erreur lors de la sérialisation du PAC',
                        'details': str(serializer_error)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            logger.error(f"[pac_get_or_create] Erreurs de validation: {create_serializer.errors}")
            return Response(create_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"[pac_get_or_create] Erreur exception non gérée: {str(e)}")
        import traceback
        logger.error(f"[pac_get_or_create] Traceback: {traceback.format_exc()}")
        return Response({
            'error': 'Impossible de traiter la demande',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACUpdatePermission])
def pac_update(request, uuid):
    """Mettre à jour un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid)
        
        # Protection : empêcher la modification du processus après création
        if 'processus' in request.data:
            return Response({
                'error': 'Le processus ne peut pas être modifié après la création du PAC'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Protection : empêcher la modification si le PAC est validé
        if pac.is_validated:
            return Response({
                'error': 'Ce PAC est validé. Les champs ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = PacUpdateSerializer(pac, data=request.data, partial=True)
        if serializer.is_valid():
            updated_pac = serializer.save()
            
            # Log de l'activité
            log_pac_update(
                user=request.user,
                pac=updated_pac,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return Response(PacSerializer(updated_pac).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de mettre à jour le PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, PACDeletePermission])
def pac_delete(request, uuid):
    """Supprimer un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid)

        # Récupérer le premier détail pour avoir un libellé (si existant)
        premier_detail = pac.details.first()
        libelle = premier_detail.libelle if premier_detail else 'N/A'

        pac_info = {
            'uuid': str(pac.uuid),
            'libelle': libelle,
            'processus': pac.processus.nom if pac.processus else None
        }

        # Log de l'activité avant suppression
        logger.info(
            f"Suppression PAC - User: {request.user.email}, "
            f"PAC: {pac_info['libelle']}, UUID: {pac_info['uuid']}, "
            f"IP: {get_client_ip(request)}"
        )

        # Suppression du PAC (cascade sur traitements et suivis)
        pac.delete()

        return Response({
            'message': 'PAC supprimé avec succès',
            'pac': pac_info
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de supprimer le PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _check_pac_completude(pac, numero_pac_display=None):
    """
    Vérifie que tous les champs obligatoires du PAC, de ses détails et de leurs
    traitements sont renseignés avant validation.
    Retourne None si tout est OK, sinon un message d'erreur (str).
    """
    details = pac.details.select_related(
        'dysfonctionnement_recommandation', 'nature', 'categorie', 'source',
        'traitement', 'traitement__type_action', 'traitement__responsable_direction',
    ).prefetch_related('traitement__responsables_directions').all()

    if not details.exists():
        return "Le tableau doit avoir au moins une ligne avant d'être validé."

    for detail in details:
        # ── Champs DetailsPac ──────────────────────────────────────────
        if not detail.libelle or not detail.libelle.strip():
            return "Le champ « Libellé » est obligatoire pour toutes les lignes."
        if not detail.dysfonctionnement_recommandation_id:
            return "Le champ « Dysfonctionnement / Recommandation » est obligatoire pour toutes les lignes."
        if not detail.nature_id:
            return "Le champ « Nature » est obligatoire pour toutes les lignes."
        if not detail.categorie_id:
            return "Le champ « Catégorie » est obligatoire pour toutes les lignes."
        if not detail.source_id:
            return "Le champ « Source » est obligatoire pour toutes les lignes."
        if not detail.periode_de_realisation:
            return "Le champ « Période de réalisation » est obligatoire pour toutes les lignes."

        # ── Traitement ────────────────────────────────────────────────
        if not hasattr(detail, 'traitement') or not detail.traitement:
            return "Toutes les lignes doivent avoir un traitement (Actions) avant validation."

        t = detail.traitement
        if not t.action or not t.action.strip():
            return "Le champ « Actions » est obligatoire pour tous les traitements."
        if not t.type_action_id:
            return "Le champ « Type d'action » est obligatoire pour tous les traitements."

        has_responsable = (
            t.responsable_direction_id
            or t.responsable_sous_direction_id
            or t.responsables_directions.exists()
            or t.responsables_sous_directions.exists()
        )
        if not has_responsable:
            return "Au moins un « Responsable » est obligatoire pour tous les traitements."

        if not t.delai_realisation:
            return "Le champ « Délai de réalisation » est obligatoire pour tous les traitements."

    return None  # Tout est complet


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACValidatePermission])
def pac_validate(request, uuid):
    """Valider un PAC (verrouille les champs PAC et Traitement)"""
    try:
        pac = Pac.objects.select_related('validated_by', 'cree_par').get(uuid=uuid)
        
        # Vérifier si le PAC est déjà validé
        if pac.is_validated:
            return Response({
                'error': 'Ce PAC est déjà validé',
                'validated_at': pac.validated_at,
                'validated_by': f"{pac.validated_by.first_name} {pac.validated_by.last_name}".strip() or pac.validated_by.username if pac.validated_by else None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que tous les champs obligatoires sont renseignés
        error_msg = _check_pac_completude(pac)
        if error_msg:
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        # Valider le PAC
        from django.utils import timezone
        pac.is_validated = True
        pac.validated_at = timezone.now()
        pac.validated_by = request.user
        pac.save()
        
        logger.info(
            f"PAC validé par {request.user.username}: "
            f"PAC UUID: {uuid}, "
            f"IP: {get_client_ip(request)}"
        )
        
        return Response(PacSerializer(pac).data, status=status.HTTP_200_OK)
        
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la validation du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de valider le PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACValidatePermission])
def pac_validate_by_type(request):
    """Valider tous les PACs d'un même amendement (processus, année, num_amendement)"""
    try:
        processus_uuid = request.data.get('processus')
        annee_uuid = request.data.get('annee')
        try:
            num_amendement = int(request.data.get('num_amendement', 0))
        except (ValueError, TypeError):
            num_amendement = 0

        if not all([processus_uuid, annee_uuid]):
            return Response({
                'error': 'processus et annee sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer tous les PACs du même contexte (processus, année, num_amendement)
        pacs_to_validate = Pac.objects.filter(
            processus__uuid=processus_uuid,
            annee__uuid=annee_uuid,
            num_amendement=num_amendement
        ).select_related('processus', 'annee').prefetch_related('details__traitement')
        
        if not pacs_to_validate.exists():
            return Response({
                'error': 'Aucun PAC trouvé pour ce contexte'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Vérifier que tous les PACs peuvent être validés
        errors = []
        for pac in pacs_to_validate:
            if pac.is_validated:
                continue  # Déjà validé, on continue

            first_detail = pac.details.first()
            numero_pac_display = first_detail.numero_pac if first_detail and first_detail.numero_pac else str(pac.uuid)

            error_msg = _check_pac_completude(pac, numero_pac_display)
            if error_msg:
                errors.append(error_msg)
        
        if errors:
            return Response({
                'error': 'Certains PACs ne peuvent pas être validés',
                'details': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider tous les PACs
        from django.utils import timezone
        validated_count = 0
        for pac in pacs_to_validate:
            if not pac.is_validated:
                pac.is_validated = True
                pac.validated_at = timezone.now()
                pac.validated_by = request.user
                pac.save()
                validated_count += 1
        
        logger.info(
            f"{validated_count} PAC(s) validé(s) par {request.user.username}: "
            f"processus={processus_uuid}, annee={annee_uuid}, num_amendement={num_amendement}, "
            f"IP: {get_client_ip(request)}"
        )
        
        return Response({
            'message': f'{validated_count} PAC(s) validé(s) avec succès',
            'validated_count': validated_count,
            'total_count': pacs_to_validate.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la validation par amendement: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de valider les PACs',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACUnvalidatePermission])
def pac_unvalidate(request, uuid):
    """Dévalider un PAC (déverrouille les champs)"""
    try:
        pac = Pac.objects.select_related('validated_by', 'cree_par').get(uuid=uuid)
        
        # Vérifier si le PAC n'est pas validé
        if not pac.is_validated:
            return Response({
                'error': 'Ce PAC n\'est pas validé'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dévalider le PAC (même s'il y a des suivis, l'utilisateur avec la permission peut dévalider)
        pac.is_validated = False
        pac.validated_at = None
        pac.validated_by = None
        pac.save()
        
        return Response(PacSerializer(pac).data, status=status.HTTP_200_OK)
        
    except Pac.DoesNotExist:
        logger.error(f"Tentative de dévalidation d'un PAC inexistant: {uuid} par {request.user.username}")
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la dévalidation du PAC {uuid}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de dévalider le PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API TRAITEMENTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def traitement_list(request):
    """Liste des traitements"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les traitements sans filtre
            traitements = TraitementPac.objects.all().order_by('-delai_realisation')
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun traitement trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            traitements = TraitementPac.objects.filter(
                details_pac__pac__processus__uuid__in=user_processus_uuids
            ).order_by('-delai_realisation')
        # ========== FIN FILTRAGE ==========
        
        serializer = TraitementPacSerializer(traitements, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': traitements.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des traitements: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer les traitements'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACTraitementCreatePermission])
def traitement_create(request):
    """Créer un nouveau traitement"""
    try:
        logger.info(f"[traitement_create] Données reçues: {request.data}")
        
        # Vérifier si le PAC est validé avant la création
        if 'details_pac' in request.data:
            details_pac_uuid = request.data['details_pac']
            logger.info(f"[traitement_create] Recherche du DetailsPac avec UUID: {details_pac_uuid}")
            
            try:
                details_pac = DetailsPac.objects.select_related('pac').get(uuid=details_pac_uuid)
                logger.info(f"[traitement_create] DetailsPac trouvé: {details_pac.uuid}, PAC validé: {details_pac.pac.is_validated}")
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, details_pac.pac.processus.uuid):
                    return Response({
                        'success': False,
                        'error': 'Vous n\'avez pas accès à ce traitement. Vous n\'avez pas de rôle actif pour ce processus.'
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                # ========== VÉRIFICATION PERMISSION CREATE_TRAITEMENT (Security by Design) ==========
                # La permission est déjà vérifiée par le décorateur @permission_classes([PACTraitementCreatePermission])
                # Mais on vérifie explicitement ici aussi pour être sûr
                try:
                    traitement_create_permission = PACTraitementCreatePermission()
                    traitement_create_permission.has_permission(request, None)
                except PermissionDenied as e:
                    return Response({
                        'success': False,
                        'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un traitement."
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                # Vérifier si un traitement existe déjà pour ce détail
                existing_traitement = TraitementPac.objects.filter(details_pac=details_pac).first()
                if existing_traitement:
                    logger.warning(f"[traitement_create] Un traitement existe déjà pour ce détail: {existing_traitement.uuid}")
                    return Response({
                        'details_pac': ["Un traitement existe déjà pour ce détail PAC. Un détail ne peut avoir qu'un seul traitement."]
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if details_pac.pac.is_validated:
                    return Response({
                        'details_pac': ['Ce PAC est validé. Impossible de créer un nouveau traitement.']
                    }, status=status.HTTP_400_BAD_REQUEST)
            except DetailsPac.DoesNotExist:
                logger.error(f"[traitement_create] DetailsPac non trouvé avec UUID: {details_pac_uuid}")
                return Response({
                    'details_pac': [f'Aucun détail PAC trouvé avec l\'UUID fourni: {details_pac_uuid}']
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TraitementPacCreateSerializer(data=request.data)
        if serializer.is_valid():
            traitement = serializer.save()

            # Log de l'activité
            try:
                log_traitement_creation(
                    user=request.user,
                    traitement=traitement,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
            except Exception as log_error:
                logger.error(f"Erreur lors du log de création du traitement: {str(log_error)}")
                # Continue même si le log échoue

            # Sérialiser la réponse
            try:
                response_data = TraitementPacSerializer(traitement).data
                return Response(response_data, status=status.HTTP_201_CREATED)
            except Exception as serializer_error:
                logger.error(f"Erreur lors de la sérialisation du traitement créé: {str(serializer_error)}")
                import traceback
                logger.error(traceback.format_exc())
                # Le traitement a été créé, retourner au moins l'UUID
                return Response({
                    'uuid': str(traitement.uuid),
                    'action': traitement.action
                }, status=status.HTTP_201_CREATED)

        logger.error(f"[traitement_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du traitement: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer le traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def pac_traitements(request, uuid):
    """Récupérer les traitements d'un PAC spécifique"""
    try:
        pac = Pac.objects.select_related('processus').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce PAC. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les traitements du PAC via les détails (OneToOne)
        traitements = TraitementPac.objects.filter(details_pac__pac=pac).order_by('-delai_realisation')
        serializer = TraitementPacSerializer(traitements, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': traitements.count()
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'success': False,
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des traitements du PAC: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer les traitements'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def traitement_detail(request, uuid):
    """Récupérer un traitement spécifique"""
    try:
        traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, traitement.details_pac.pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce traitement. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        serializer = TraitementPacSerializer(traitement)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except TraitementPac.DoesNotExist:
        return Response({
            'error': 'Traitement non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACTraitementUpdatePermission])
def traitement_update(request, uuid):
    """Mettre à jour un traitement"""
    try:
        traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=uuid)
        
        # Protection : empêcher la modification si le PAC est validé
        if traitement.details_pac.pac.is_validated:
            return Response({
                'error': 'Ce PAC est validé. Les champs de traitement ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TraitementPacUpdateSerializer(traitement, data=request.data, partial=True)
        if serializer.is_valid():
            traitement = serializer.save()
            return Response(TraitementPacSerializer(traitement).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except TraitementPac.DoesNotExist:
        return Response({
            'error': 'Traitement non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de mettre à jour le traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API SUIVIS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_list(request):
    """Liste des suivis"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les suivis sans filtre
            suivis = PacSuivi.objects.all().order_by('-created_at')
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun suivi trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            suivis = PacSuivi.objects.filter(
                traitement__details_pac__pac__processus__uuid__in=user_processus_uuids
            ).order_by('-created_at')
        # ========== FIN FILTRAGE ==========
        
        serializer = PacSuiviSerializer(suivis, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': suivis.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des suivis: {str(e)}")
        return Response({
            'success': False,
            'error': 'Impossible de récupérer les suivis'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def traitement_suivis(request, uuid):
    """Récupérer les suivis d'un traitement PAC"""
    try:
        # Charger les relations nécessaires (OneToOne : un seul suivi par traitement)
        try:
            traitement = TraitementPac.objects.select_related('suivi', 'details_pac', 'details_pac__pac', 'details_pac__pac__processus').get(uuid=uuid)
            
            # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
            if not user_has_access_to_processus(request.user, traitement.details_pac.pac.processus.uuid):
                return Response({
                    'success': False,
                    'error': 'Vous n\'avez pas accès à ce traitement. Vous n\'avez pas de rôle actif pour ce processus.'
                }, status=status.HTTP_403_FORBIDDEN)
            # ========== FIN VÉRIFICATION ==========
            
            if hasattr(traitement, 'suivi') and traitement.suivi:
                suivi = traitement.suivi
                serializer = PacSuiviSerializer(suivi)
                return Response(serializer.data)
            else:
                return Response({
                    'message': 'Aucun suivi pour ce traitement',
                    'suivi': None
                }, status=status.HTTP_200_OK)
        except TraitementPac.DoesNotExist:
            return Response({
                'error': 'Traitement non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des suivis du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les suivis du traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACSuiviCreatePermission])
def suivi_create(request):
    """Créer un nouveau suivi"""
    try:
        # Permettre la création de suivi lors de la copie d'amendement (from_amendment_copy=True)
        from_amendment_copy = request.data.get('from_amendment_copy', False)
        
        # Vérifier si le traitement est dans un PAC validé avant la création
        # SAUF si c'est une copie d'amendement (dans ce cas, on permet la création même si le PAC n'est pas validé)
        if 'traitement' in request.data:
            try:
                traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=request.data['traitement'])
                if not traitement.details_pac.pac.is_validated and not from_amendment_copy:
                    return Response({
                        'error': 'Le PAC doit être validé avant de pouvoir créer un suivi. Veuillez d\'abord valider tous les détails et traitements du PAC.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except TraitementPac.DoesNotExist:
                pass  # La validation du serializer gérera cette erreur
        
        serializer = PacSuiviCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            statut = serializer.validated_data.get('statut')
            date_cloture = serializer.validated_data.get('date_cloture')
            if statut and statut.nom and 'clôtur' in statut.nom.lower() and not date_cloture:
                return Response({
                    'date_cloture': 'La date de clôture est requise lorsque le statut indique une clôture.'
                }, status=status.HTTP_400_BAD_REQUEST)

            suivi = serializer.save()

            # Log de l'activité
            try:
                log_suivi_creation(
                    user=request.user,
                    suivi=suivi,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
            except Exception as log_error:
                logger.error(f"Erreur lors du log de création du suivi: {str(log_error)}")
                # Continue même si le log échoue

            # Sérialiser la réponse
            try:
                response_data = PacSuiviSerializer(suivi).data
                return Response(response_data, status=status.HTTP_201_CREATED)
            except Exception as serializer_error:
                logger.error(f"Erreur lors de la sérialisation du suivi créé: {str(serializer_error)}")
                import traceback
                logger.error(traceback.format_exc())
                # Le suivi a été créé, retourner au moins l'UUID
                return Response({
                    'uuid': str(suivi.uuid),
                    'resultat': suivi.resultat
                }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du suivi: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer le suivi'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_detail(request, uuid):
    """Récupérer le détail d'un suivi"""
    try:
        suivi = PacSuivi.objects.select_related(
            'traitement', 'traitement__details_pac', 'traitement__details_pac__pac',
            'etat_mise_en_oeuvre', 'appreciation', 'preuve', 'statut'
        ).prefetch_related(
            'preuve__medias'
        ).get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, suivi.traitement.details_pac.pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce suivi. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        return Response({
            'success': True,
            'data': PacSuiviSerializer(suivi).data
        }, status=status.HTTP_200_OK)
    except PacSuivi.DoesNotExist:
        return Response({'error': 'Suivi non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du suivi: {str(e)}")
        return Response({'error': "Impossible de récupérer le suivi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACSuiviUpdatePermission])
def suivi_update(request, uuid):
    """Mettre à jour un suivi"""
    try:
        suivi = PacSuivi.objects.select_related('traitement', 'traitement__details_pac', 'traitement__details_pac__pac').get(uuid=uuid)
        
        # Protection : empêcher la modification si le PAC n'est pas validé
        if not suivi.traitement.details_pac.pac.is_validated:
            return Response({
                'error': 'Le PAC doit être validé avant de pouvoir modifier un suivi.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = PacSuiviUpdateSerializer(suivi, data=request.data, partial=True)
        if serializer.is_valid():
            statut = serializer.validated_data.get('statut', suivi.statut)
            date_cloture = serializer.validated_data.get('date_cloture')
            if statut and statut.nom and 'clôtur' in statut.nom.lower() and not (date_cloture or suivi.date_cloture):
                return Response({
                    'date_cloture': 'La date de clôture est requise lorsque le statut indique une clôture.'
                }, status=status.HTTP_400_BAD_REQUEST)

            suivi = serializer.save()
            return Response(PacSuiviSerializer(suivi).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        # DRF retournera automatiquement une réponse 403 avec le message approprié
        raise
    except PacSuivi.DoesNotExist:
        return Response({'error': 'Suivi non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du suivi: {str(e)}")
        return Response({'error': "Impossible de mettre à jour le suivi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API DETAILS PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def details_pac_list(request, uuid):
    """Liste des détails d'un PAC spécifique"""
    try:
        pac = Pac.objects.get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, pac.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce PAC. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les détails du PAC
        details = DetailsPac.objects.filter(pac=pac).select_related(
            'pac', 'dysfonctionnement_recommandation', 'nature', 'categorie', 'source'
        ).order_by('periode_de_realisation')
        
        serializer = DetailsPacSerializer(details, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': details.count()
        }, status=status.HTTP_200_OK)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les détails'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, PACDetailCreatePermission])
def details_pac_create(request):
    """Créer un nouveau détail de PAC"""
    try:
        logger.info(f"[details_pac_create] Données reçues: {request.data}")
        
        # Vérifier si le PAC est validé avant la création
        if 'pac' in request.data:
            try:
                pac = Pac.objects.get(uuid=request.data['pac'])
                logger.info(f"[details_pac_create] PAC trouvé: {pac.uuid}, validé: {pac.is_validated}")
                
                # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
                if not user_has_access_to_processus(request.user, pac.processus.uuid):
                    return Response({
                        'success': False,
                        'error': 'Vous n\'avez pas accès à ce PAC. Vous n\'avez pas de rôle actif pour ce processus.'
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                # ========== VÉRIFICATION PERMISSION CREATE_DETAIL_PAC (Security by Design) ==========
                # La permission est déjà vérifiée par le décorateur @permission_classes([PACDetailCreatePermission])
                # Mais on vérifie explicitement ici aussi pour être sûr
                try:
                    detail_create_permission = PACDetailCreatePermission()
                    detail_create_permission.has_permission(request, None)
                except PermissionDenied as e:
                    return Response({
                        'success': False,
                        'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un détail PAC."
                    }, status=status.HTTP_403_FORBIDDEN)
                # ========== FIN VÉRIFICATION ==========
                
                if pac.is_validated:
                    return Response({
                        'error': 'Ce PAC est validé. Impossible de créer un nouveau détail.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except Pac.DoesNotExist:
                logger.error(f"[details_pac_create] PAC non trouvé avec UUID: {request.data['pac']}")
                pass  # La validation du serializer gérera cette erreur
        
        serializer = DetailsPacCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            detail = serializer.save()
            logger.info(f"[details_pac_create] ✅ Détail créé avec succès: {detail.uuid}")
            return Response(DetailsPacSerializer(detail).data, status=status.HTTP_201_CREATED)
        
        logger.error(f"[details_pac_create] Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du détail: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Impossible de créer le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, PACReadPermission])
def details_pac_detail(request, uuid):
    """Récupérer un détail spécifique"""
    try:
        detail = DetailsPac.objects.select_related(
            'pac', 'dysfonctionnement_recommandation', 'nature', 'categorie', 'source'
        ).get(uuid=uuid)
        
        serializer = DetailsPacSerializer(detail)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except DetailsPac.DoesNotExist:
        return Response({
            'error': 'Détail non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du détail: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, PACDetailUpdatePermission])
def details_pac_update(request, uuid):
    """Mettre à jour un détail de PAC"""
    try:
        detail = DetailsPac.objects.select_related('pac').get(uuid=uuid)
        
        # Protection : empêcher la modification si le PAC est validé
        if detail.pac.is_validated:
            return Response({
                'error': 'Ce PAC est validé. Les champs de détail ne peuvent plus être modifiés.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DetailsPacUpdateSerializer(detail, data=request.data, partial=True)
        if serializer.is_valid():
            detail = serializer.save()
            return Response(DetailsPacSerializer(detail).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except DetailsPac.DoesNotExist:
        return Response({
            'error': 'Détail non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du détail: {str(e)}")
        return Response({
            'error': 'Impossible de mettre à jour le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, PACDetailDeletePermission])
def details_pac_delete(request, uuid):
    """Supprimer un détail de PAC"""
    try:
        detail = DetailsPac.objects.select_related('pac').get(uuid=uuid)

        # Vérifier que le PAC n'est pas validé
        if detail.pac.is_validated:
            return Response({
                'error': 'Impossible de supprimer un détail d\'un PAC validé'
            }, status=status.HTTP_400_BAD_REQUEST)

        detail_info = {
            'uuid': str(detail.uuid),
            'libelle': detail.libelle,
            'pac': detail.pac.uuid if detail.pac else None
        }

        # Suppression du détail
        detail.delete()
        
        return Response({
            'message': 'Détail supprimé avec succès',
            'detail': detail_info
        }, status=status.HTTP_200_OK)
    except DetailsPac.DoesNotExist:
        return Response({
            'error': 'Détail non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du détail: {str(e)}")
        return Response({
            'error': 'Impossible de supprimer le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== NOTIFICATIONS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_upcoming_notifications(request):
    """Récupérer les traitements bientôt à terme pour les notifications"""
    try:
        from datetime import datetime as dt_class
        from django.contrib.contenttypes.models import ContentType

        today = timezone.now().date()
        
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les notifications sans filtre
            traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                delai_realisation__isnull=False
            ).select_related(
                'details_pac', 
                'details_pac__pac',
                'details_pac__pac__processus',
                'details_pac__nature',
                'type_action'
            ).prefetch_related(
                'responsables_directions',
                'responsables_sous_directions'
            )
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucune notification trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Récupérer tous les traitements des processus de l'utilisateur avec leurs délais de réalisation
            traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                details_pac__pac__processus__uuid__in=user_processus_uuids,
            delai_realisation__isnull=False
        ).select_related(
            'details_pac', 
            'details_pac__pac',
            'details_pac__pac__processus',
            'details_pac__nature',
            'type_action'
        ).prefetch_related(
            'responsables_directions',
            'responsables_sous_directions'
        )
        
        notifications = []
        
        for traitement in traitements:
            try:
                # Vérifier que le traitement a bien un details_pac et un pac
                if not traitement.details_pac or not traitement.details_pac.pac:
                    continue
                    
                delai_date = traitement.delai_realisation
                if not delai_date:
                    continue
                
                # Convertir en date si nécessaire
                if isinstance(delai_date, dt_class):
                    delai_date = delai_date.date()
                
                # Calculer la différence en jours
                try:
                    diff_days = (delai_date - today).days
                except (TypeError, AttributeError) as e:
                    logger.warning(f"[pac_upcoming_notifications] Erreur lors du calcul de la différence de jours: {e}")
                    continue
                
                # Inclure les traitements arrivés à terme (en retard) et bientôt à terme (dans les 7 prochains jours)
                if diff_days <= 7:
                    # Déterminer la priorité
                    if diff_days < 0:
                        priority = 'high'  # En retard
                        delai_label = f'En retard de {abs(diff_days)} jour{"s" if abs(diff_days) > 1 else ""}'
                    elif diff_days == 0:
                        priority = 'high'  # Échéance aujourd'hui
                        delai_label = 'Échéance aujourd\'hui'
                    elif diff_days <= 3:
                        priority = 'high'  # Dans les 3 prochains jours
                        delai_label = f'Échéance dans {diff_days} jour{"s" if diff_days > 1 else ""}'
                    else:
                        priority = 'medium'  # Dans 4-7 jours
                        delai_label = f'Échéance dans {diff_days} jours'
                    
                    # Construire le titre
                    pac = traitement.details_pac.pac
                    numero_pac = traitement.details_pac.numero_pac or f'PAC-{pac.uuid}'
                    action_title = traitement.action[:50] if traitement.action else 'Action non spécifiée'
                    if len(traitement.action or '') > 50:
                        action_title += '...'
                    
                    title = f'{numero_pac} - Action : {action_title}'
                    
                    # Construire l'URL d'action
                    action_url = f'/pac/{pac.uuid}'
                    message = f'Délai de réalisation {delai_label}'
                    
                    # Récupérer les informations supplémentaires
                    nature_label = traitement.details_pac.nature.nom if traitement.details_pac.nature else None
                    type_action = traitement.type_action.nom if traitement.type_action else None
                    
                    notifications.append({
                        'id': str(traitement.uuid),
                        'type': 'traitement',
                        'title': title,
                        'numero_pac': numero_pac,
                        'action': (traitement.action or 'Action non spécifiée')[:80],
                        'message': message,
                        'due_date': delai_date.isoformat() if hasattr(delai_date, 'isoformat') else str(delai_date),
                        'priority': priority,
                        'action_url': action_url,
                        'nature_label': nature_label,
                        'type_action': type_action,
                        'delai_label': delai_label,
                        'pac_uuid': str(pac.uuid),
                        'traitement_uuid': str(traitement.uuid),
                        'notification_uuid': None,
                        'read_at': None,
                    })

                    # Enregistrer/mettre à jour la notification côté serveur (table parametre.Notification)
                    try:
                        content_type = ContentType.objects.get_for_model(TraitementPac)
                        notif, created = Notification.objects.get_or_create(
                            user=request.user,
                            content_type=content_type,
                            object_id=traitement.uuid,
                            source_app='pac',
                            notification_type='traitement',
                            defaults={
                                'title': title,
                                'message': message,
                                'action_url': action_url,
                                'priority': priority,
                                'due_date': delai_date,
                            },
                        )
                        if not created:
                            updated_fields = []
                            if notif.title != title:
                                notif.title = title
                                updated_fields.append('title')
                            if notif.message != message:
                                notif.message = message
                                updated_fields.append('message')
                            if notif.action_url != action_url:
                                notif.action_url = action_url
                                updated_fields.append('action_url')
                            if notif.priority != priority:
                                notif.priority = priority
                                updated_fields.append('priority')
                            if notif.due_date != delai_date:
                                notif.due_date = delai_date
                                updated_fields.append('due_date')
                            if updated_fields:
                                notif.save(update_fields=updated_fields + ['updated_at'])
                        notifications[-1]['notification_uuid'] = str(notif.uuid)
                        notifications[-1]['read_at'] = notif.read_at.isoformat() if notif.read_at else None
                    except Exception as notif_err:
                        logger.warning(f"[pac_upcoming_notifications] Notification get_or_create: {notif_err}")
            except Exception as e:
                logger.error(f"[pac_upcoming_notifications] Erreur lors du traitement du traitement {traitement.uuid}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # Trier par priorité (high en premier) puis par date
        notifications.sort(key=lambda x: (
            0 if x['priority'] == 'high' else 1 if x['priority'] == 'medium' else 2,
            x['due_date']
        ))
        
        logger.info(f"[pac_upcoming_notifications] {len(notifications)} notifications trouvées pour l'utilisateur {request.user.username}")
        
        return Response({
            'success': True,
            'notifications': notifications
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des notifications: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'notifications': [],
            'error': 'Erreur lors de la récupération des notifications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATISTIQUES PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_stats(request):
    """Statistiques des PACs de l'utilisateur connecté"""
    try:
        logger.info(f"[pac_stats] Début de la fonction pour l'utilisateur: {request.user.username}")
        scope = request.query_params.get('scope', 'tous')
        
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les PACs, avec filtre processus optionnel (?processus=UUID)
            pacs_base = Pac.objects.all()
            processus_filter = request.query_params.get('processus')
            if processus_filter and str(processus_filter).upper() != 'ALL':
                try:
                    from uuid import UUID
                    UUID(str(processus_filter))
                    pacs_base = pacs_base.filter(processus__uuid=processus_filter)
                except (ValueError, TypeError):
                    pass
        elif not user_processus_uuids:
            return Response({
                'success': True,
                'data': {
                    'total_pacs': 0, 'pacs_valides': 0, 'pacs_non_valides': 0,
                    'pacs_avec_traitement': 0, 'pacs_sans_traitement': 0,
                    'pacs_avec_suivi': 0, 'pacs_sans_suivi': 0,
                    'total_traitements': 0, 'total_suivis': 0
                },
                'message': 'Aucune donnée de PAC trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Récupérer tous les PACs des processus de l'utilisateur
            pacs_base = Pac.objects.filter(processus__uuid__in=user_processus_uuids)
        logger.info(f"[pac_stats] Queryset créé")
        # ========== FIN FILTRAGE ==========
        
        logger.info(f"[pac_stats] Nombre total de PACs de l'utilisateur: {pacs_base.count()}")

        # Filtrer selon le scope
        if scope == 'dernier':
            # Dernier PAC par processus = celui avec le num_amendement le plus élevé
            from django.db.models import Max
            last_uuids = []
            for proc_uuid in pacs_base.values_list('processus', flat=True).distinct():
                max_num = pacs_base.filter(processus=proc_uuid).aggregate(m=Max('num_amendement'))['m']
                last = pacs_base.filter(processus=proc_uuid, num_amendement=max_num).first()
                if last:
                    last_uuids.append(last.uuid)
            pacs_initiaux_base = pacs_base.filter(uuid__in=last_uuids)
        else:
            # Filtrer les PACs initiaux uniquement (num_amendement == 0)
            pacs_initiaux_base = pacs_base.filter(num_amendement=0)
        logger.info(f"[pac_stats] Nombre de PACs initiaux: {pacs_initiaux_base.count()}")
        
        total_pacs = pacs_initiaux_base.count()
        
        # Compter les PACs initiaux validés
        # Debug: Vérifier tous les PACs initiaux et leur statut de validation
        logger.info(f"[pac_stats] Vérification des PACs initiaux et leur statut de validation:")
        for pac in pacs_initiaux_base:
            # Recharger depuis la DB pour être sûr d'avoir la valeur à jour
            pac.refresh_from_db()
            logger.info(f"[pac_stats] PAC {pac.uuid}: is_validated={pac.is_validated} (type: {type(pac.is_validated).__name__}), validated_at={pac.validated_at}, validated_by={pac.validated_by}")
            
            # Vérifier aussi avec une requête directe
            pac_direct = Pac.objects.get(uuid=pac.uuid)
            logger.info(f"[pac_stats] PAC {pac.uuid} (requête directe): is_validated={pac_direct.is_validated} (type: {type(pac_direct.is_validated).__name__})")
        
        # Utiliser une requête directe sur la base filtrée
        # Un PAC est considéré comme validé si is_validated=True OU si validated_at/validated_by sont remplis
        from django.db.models import Q
        # Utiliser pacs_initiaux_base qui a déjà été filtré correctement (gère le cas super admin)
        pacs_valides_filter1 = pacs_initiaux_base.filter(
            Q(is_validated=True) | Q(validated_at__isnull=False) | Q(validated_by__isnull=False)
        ).count()
        logger.info(f"[pac_stats] Nombre de PACs initiaux validés (via filter avec Q): {pacs_valides_filter1}")
        
        # Essayer avec une requête qui vérifie explicitement que ce n'est pas False
        pacs_valides_filter2 = pacs_initiaux_base.exclude(is_validated=False).count()
        logger.info(f"[pac_stats] Nombre de PACs initiaux validés (via exclude is_validated=False): {pacs_valides_filter2}")
        
        # Compter aussi manuellement pour vérifier (plus fiable)
        # Un PAC est considéré comme validé si is_validated=True OU si validated_at/validated_by sont remplis
        pacs_valides_manual = 0
        for pac in pacs_initiaux_base:
            pac.refresh_from_db()
            # Vérifier explicitement que is_validated est True (booléen Python)
            # OU que validated_at/validated_by sont remplis (cas où is_validated n'a pas été mis à jour)
            is_validated = (
                pac.is_validated is True or 
                pac.is_validated == 1 or 
                (isinstance(pac.is_validated, bool) and pac.is_validated) or
                pac.validated_at is not None or
                pac.validated_by is not None
            )
            if is_validated:
                pacs_valides_manual += 1
                logger.info(f"[pac_stats] PAC {pac.uuid} considéré comme validé: is_validated={pac.is_validated}, validated_at={pac.validated_at}, validated_by={pac.validated_by}")
        logger.info(f"[pac_stats] Nombre de PACs initiaux validés (manuel): {pacs_valides_manual}")
        
        # Utiliser le comptage manuel (plus fiable que la requête filter)
        # Si les deux méthodes donnent des résultats différents, utiliser le manuel
        if pacs_valides_filter1 != pacs_valides_manual or pacs_valides_filter2 != pacs_valides_manual:
            logger.warning(f"[pac_stats] Incohérence détectée! filter1()={pacs_valides_filter1}, filter2()={pacs_valides_filter2}, manuel={pacs_valides_manual}. Utilisation du comptage manuel.")
            pacs_valides = pacs_valides_manual
        else:
            pacs_valides = pacs_valides_filter1
        
        # Récupérer les PACs initiaux avec leurs relations pour les boucles (pour les autres stats)
        pacs = pacs_initiaux_base.select_related(
            'processus', 'cree_par', 'annee'
        ).prefetch_related('details__traitement', 'details__traitement__suivi')
        
        # Compter les PACs avec traitement et suivi
        # Pour "Avec Traitement", compter TOUS les PACs (initiaux ET amendements) qui ont des traitements
        pacs_avec_traitement = 0
        pacs_avec_suivi = 0
        
        # Récupérer TOUS les PACs des processus de l'utilisateur (initiaux ET amendements) pour compter ceux avec traitement
        # Utiliser pacs_base qui a déjà été filtré correctement (gère le cas super admin)
        all_pacs = pacs_base.select_related(
            'processus', 'cree_par', 'annee'
        ).prefetch_related('details__traitement', 'details__traitement__suivi')
        
        logger.info(f"[pac_stats] Nombre total de PACs (initiaux + amendements): {all_pacs.count()}")
        
        # Compter les PACs avec traitement (tous types confondus)
        for pac in all_pacs:
            try:
                has_traitement = False
                has_suivi = False
                
                # Vérifier si le PAC a au moins un détail avec un traitement
                details = pac.details.all()
                for detail in details:
                    try:
                        if hasattr(detail, 'traitement') and detail.traitement:
                            has_traitement = True
                            # Vérifier si le traitement a un suivi
                            if hasattr(detail.traitement, 'suivi') and detail.traitement.suivi:
                                has_suivi = True
                                break
                    except Exception as e:
                        logger.warning(f"[pac_stats] Erreur lors de l'accès au traitement du détail {detail.uuid}: {e}")
                        continue
                
                # Compter une seule fois par PAC
                if has_traitement:
                    pacs_avec_traitement += 1
                    logger.info(f"[pac_stats] PAC {pac.uuid} (num_amendement={pac.num_amendement}) a un traitement")
                if has_suivi:
                    pacs_avec_suivi += 1
            except Exception as e:
                logger.error(f"[pac_stats] Erreur lors du traitement du PAC {pac.uuid}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        logger.info(f"[pac_stats] Nombre de PACs avec traitement (tous types): {pacs_avec_traitement}")
        logger.info(f"[pac_stats] Nombre de PACs avec suivi (tous types): {pacs_avec_suivi}")
        
        # Pour les autres stats, continuer avec les PACs initiaux uniquement
        
        # Analyser TOUS les traitements (pas seulement un par PAC)
        # Pour les traitements bientôt à terme, on continue à filtrer sur les PACs initiaux uniquement
        today = timezone.now().date()
        traitements_arrives_termes = 0
        traitements_bientot_termes = 0
        
        # Récupérer tous les traitements de l'utilisateur avec leurs délais de réalisation
        # Filtrer uniquement les traitements qui ont un details_pac et un pac initial associé
        # Utiliser pacs_initiaux_base pour obtenir les PACs initiaux, puis filtrer les traitements
        pacs_initiaux_uuids = list(pacs_initiaux_base.values_list('uuid', flat=True))
        
        # Si aucun PAC initial, les listes de traitements seront vides
        if not pacs_initiaux_uuids:
            traitements = TraitementPac.objects.none()
        else:
            traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                details_pac__pac__uuid__in=pacs_initiaux_uuids,
                delai_realisation__isnull=False
            ).select_related('details_pac', 'details_pac__pac')
        
        logger.info(f"[pac_stats] Nombre de traitements avec délai trouvés (PACs initiaux uniquement): {traitements.count()}")
        
        for traitement in traitements:
            try:
                # Vérifier que le traitement a bien un details_pac et un pac
                if not traitement.details_pac or not traitement.details_pac.pac:
                    continue
                    
                delai_date = traitement.delai_realisation
                if not delai_date:
                    continue
                
                # DateField retourne un objet date de Python, on peut l'utiliser directement
                # Si par erreur c'est un datetime, convertir en date
                try:
                    from datetime import datetime as dt_class
                    if isinstance(delai_date, dt_class):
                        delai_date = delai_date.date()
                except Exception:
                    # Si la conversion échoue, on continue avec la date telle quelle
                    pass
                
                # Traitement arrivé à terme (la date est passée)
                try:
                    if delai_date < today:
                        traitements_arrives_termes += 1
                        logger.debug(f"[pac_stats] Traitement arrivé à terme: {traitement.uuid}, délai: {delai_date}")
                    # Traitement bientôt à terme (dans les 7 prochains jours)
                    else:
                        diff_days = (delai_date - today).days
                        if 0 <= diff_days <= 7:
                            traitements_bientot_termes += 1
                            logger.debug(f"[pac_stats] Traitement bientôt à terme: {traitement.uuid}, délai: {delai_date}, jours restants: {diff_days}")
                except (TypeError, AttributeError) as e:
                    logger.warning(f"[pac_stats] Erreur lors de la comparaison de dates: {e}, type: {type(delai_date)}")
                    continue
            except Exception as e:
                logger.error(f"[pac_stats] Erreur lors du traitement du traitement {traitement.uuid}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # Compter le total des traitements de l'utilisateur pour les PACs initiaux uniquement
        # Filtrer uniquement les traitements qui ont un details_pac et un pac initial associé
        # Utiliser pacs_initiaux_uuids qui a déjà été créé plus haut
        if not pacs_initiaux_uuids:
            total_traitements = 0
        else:
            total_traitements = TraitementPac.objects.filter(
                details_pac__isnull=False,
                details_pac__pac__uuid__in=pacs_initiaux_uuids
            ).count()
        
        # Compter le total des suivis de l'utilisateur pour les PACs initiaux uniquement
        # Filtrer uniquement les suivis qui ont un traitement avec details_pac et pac initial associé
        if not pacs_initiaux_uuids:
            total_suivis = 0
        else:
            total_suivis = PacSuivi.objects.filter(
                traitement__isnull=False,
                traitement__details_pac__isnull=False,
                traitement__details_pac__pac__uuid__in=pacs_initiaux_uuids
            ).count()
        
        logger.info(f"[pac_stats] Statistiques calculées: total_pacs={total_pacs}, pacs_valides={pacs_valides}, "
                   f"pacs_avec_traitement={pacs_avec_traitement}, pacs_avec_suivi={pacs_avec_suivi}, "
                   f"total_traitements={total_traitements}, total_suivis={total_suivis}, "
                   f"traitements_arrives_termes={traitements_arrives_termes}, traitements_bientot_termes={traitements_bientot_termes}")
        
        # Statistiques pour les graphiques
        stats = {
            'total_pacs': total_pacs,
            'pacs_valides': pacs_valides,
            'pacs_avec_traitement': pacs_avec_traitement,
            'pacs_avec_suivi': pacs_avec_suivi,
            'total_traitements': total_traitements,
            'total_suivis': total_suivis,
            'traitements_arrives_termes': traitements_arrives_termes,
            'traitements_bientot_termes': traitements_bientot_termes
        }
        
        logger.info(f"[pac_stats] Stats à retourner: {stats}")
        
        return Response({
            'success': True,
            'data': stats
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques PAC: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des statistiques PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_pac_previous_year(request):
    """
    Récupérer le dernier PAC (INITIAL, AMENDEMENT_1 ou AMENDEMENT_2) de l'année précédente
    pour un processus donné.

    Query params:
    - annee: UUID de l'année actuelle
    - processus: UUID du processus

    Retourne le dernier type de tableau (ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL)
    """
    try:
        from parametre.models import Annee

        annee_uuid = request.query_params.get('annee')
        processus_uuid = request.query_params.get('processus')

        if not annee_uuid or not processus_uuid:
            return Response({
                'error': 'Les paramètres annee et processus sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer l'année actuelle et calculer l'année précédente
        try:
            annee_actuelle = Annee.objects.get(uuid=annee_uuid)
            annee_precedente_valeur = annee_actuelle.annee - 1
            annee_precedente = Annee.objects.get(annee=annee_precedente_valeur)
        except Annee.DoesNotExist:
            logger.info(f"[get_last_pac_previous_year] Année précédente {annee_precedente_valeur if 'annee_precedente_valeur' in locals() else 'N/A'} non trouvée")
            return Response({
                'message': f'Aucune année {annee_precedente_valeur if "annee_precedente_valeur" in locals() else "précédente"} trouvée dans le système',
                'found': False,
                'data': None
            }, status=status.HTTP_200_OK)

        logger.info(f"[get_last_pac_previous_year] Recherche du dernier PAC pour processus={processus_uuid}, année={annee_precedente.annee}")

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce processus. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Récupérer le PAC avec le num_amendement le plus élevé pour l'année précédente
        pac = Pac.objects.filter(
            annee=annee_precedente,
            processus__uuid=processus_uuid,
        ).select_related('processus', 'annee', 'cree_par', 'validated_by').order_by('-num_amendement').first()

        if pac:
            logger.info(f"[get_last_pac_previous_year] PAC trouvé: {pac.uuid} (num_amendement={pac.num_amendement})")
            serializer = PacSerializer(pac)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun PAC trouvé pour l'année précédente (200 pour que le frontend ne voit pas 404)
        logger.info(f"[get_last_pac_previous_year] Aucun PAC trouvé pour l'année {annee_precedente.annee}")
        return Response({
            'message': f'Aucun Plan d\'Action de Conformité trouvé pour l\'année {annee_precedente.annee}',
            'found': False,
            'data': None
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier PAC de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération du PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
