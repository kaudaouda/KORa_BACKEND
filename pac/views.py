"""
Vues API pour l'application PAC
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
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
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from datetime import datetime, timedelta
from .models import Pac, TraitementPac, PacSuivi, DetailsPac
from parametre.models import Processus, Media, Preuve, Versions
from parametre.views import log_pac_creation, log_pac_update, log_traitement_creation, log_suivi_creation, log_user_login, get_client_ip, log_activity
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
# ==================== UTILITAIRES TYPE TABLEAU ====================

def _get_next_type_tableau_for_context(user, annee_uuid, processus_uuid):
    """
    Retourne l'instance Versions à utiliser automatiquement pour (annee, processus) d'un user.
    Ordre: INITIAL -> AMENDEMENT_1 -> AMENDEMENT_2. Si tous existent déjà, retourne AMENDEMENT_2.
    """
    try:
        logger.info(f"[_get_next_type_tableau_for_context] user={user}, annee_uuid={annee_uuid}, processus_uuid={processus_uuid}")
        codes_order = ['INITIAL', 'AMENDEMENT_1', 'AMENDEMENT_2']
        existing_types = set(
            Pac.objects.filter(
                cree_par=user,
                annee_id=annee_uuid,
                processus_id=processus_uuid
            ).values_list('type_tableau__code', flat=True)
        )
        logger.info(f"[_get_next_type_tableau_for_context] existing_types={existing_types}")
        for code in codes_order:
            if code not in existing_types:
                version = Versions.objects.get(code=code)
                logger.info(f"[_get_next_type_tableau_for_context] Retourne version {code}: {version}")
                return version
        # Tous déjà présents: retourner le dernier
        version = Versions.objects.get(code=codes_order[-1])
        logger.info(f"[_get_next_type_tableau_for_context] Tous présents, retourne {version}")
        return version
    except Versions.DoesNotExist as e:
        logger.error(f"[_get_next_type_tableau_for_context] Versions.DoesNotExist: {e}")
        # En cas de configuration incomplète, fallback sur le premier disponible
        fallback = Versions.objects.order_by('nom').first()
        logger.info(f"[_get_next_type_tableau_for_context] Fallback sur {fallback}")
        return fallback
    except Exception as e:
        logger.error(f"[_get_next_type_tableau_for_context] Erreur: {e}")
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

        # Authentifier l'utilisateur avec l'email
        try:
            user = User.objects.get(email=email)
            user = authenticate(username=user.username, password=password)
        except User.DoesNotExist:
            user = None
        
        if user is None:
            return Response({
                'error': 'Identifiants invalides'
            }, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({
                'error': 'Compte utilisateur désactivé'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Générer les tokens
        access_token, refresh_token = AuthService.create_tokens(user)

        # Log de l'activité de connexion
        log_user_login(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        # Créer la réponse
        response = Response({
            'message': 'Connexion réussie',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

        # Définir les cookies
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
    """Déconnexion d'un utilisateur"""
    try:
        # Créer la réponse
        response = Response({
            'message': 'Déconnexion réussie'
        }, status=status.HTTP_200_OK)

        # Supprimer les cookies
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

            # Créer la réponse avec le nouveau token
            response = Response({
                'message': 'Token rafraîchi avec succès'
            }, status=status.HTTP_200_OK)

            # Mettre à jour le cookie access_token
            response.set_cookie(
                'access_token',
                str(new_access_token),
                max_age=60 * 60,  # 1 heure
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
@permission_classes([IsAuthenticated])
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
            'processus', 'cree_par', 'annee', 'type_tableau', 'validated_by'
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
                'processus', 'cree_par', 'annee', 'type_tableau', 'validated_by'
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
    """Créer un nouveau PAC (nouvelle ligne)"""
    try:
        logger.info(f"Données reçues pour la création de PAC: {request.data}")
        data = request.data

        annee_uuid = data.get('annee')
        processus_uuid = data.get('processus')
        type_tableau_uuid = data.get('type_tableau')

        # ========== VÉRIFICATION DES PERMISSIONS (Security by Design) ==========
        # La permission est déjà vérifiée par le décorateur @permission_classes([PACCreatePermission])
        # Mais on vérifie explicitement ici aussi pour être sûr
        # Note: Le décorateur devrait normalement bloquer avant d'arriver ici, mais on garde cette vérification pour sécurité
        if processus_uuid:
            try:
                pac_create_permission = PACCreatePermission()
                pac_create_permission.has_permission(request, None)
            except PermissionDenied as e:
                return Response({
                    'success': False,
                    'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un PAC."
                }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION DES PERMISSIONS ==========

        # Si type_tableau manque mais annee + processus sont fournis, déterminer automatiquement le type
        if annee_uuid and processus_uuid and not type_tableau_uuid:
            auto_tt = _get_next_type_tableau_for_context(request.user, annee_uuid, processus_uuid)
            if auto_tt:
                # Copier les données pour mutation sûre
                data = data.copy()
                data['type_tableau'] = str(auto_tt.uuid)

        # Toujours créer un nouveau PAC (nouvelle ligne)
        # Plusieurs lignes peuvent avoir le même (processus, année, type_tableau)
        serializer = PacCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            logger.info(f"Serializer valide, données validées: {serializer.validated_data}")
            pac = serializer.save()
            
            # Log de l'activité
            log_pac_creation(
                user=request.user,
                pac=pac,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return Response(PacSerializer(pac).data, status=status.HTTP_201_CREATED)
        
        logger.error(f"Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        import traceback
        logger.error(f"Erreur lors de la création du PAC: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response({
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
            'processus', 'cree_par', 'annee', 'type_tableau'
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
    Récupérer ou créer un PAC unique pour (processus, annee, type_tableau).
    Un seul PAC peut exister pour une combinaison (processus, annee, type_tableau).
    """
    try:
        logger.info(f"[pac_get_or_create] Début - données reçues: {request.data}")
        data = request.data
        annee_uuid = data.get('annee')
        processus_uuid = data.get('processus')
        type_tableau_uuid = data.get('type_tableau')

        logger.info(f"[pac_get_or_create] annee_uuid={annee_uuid}, processus_uuid={processus_uuid}, type_tableau_uuid={type_tableau_uuid}")

        # Si type_tableau est absent mais annee + processus sont fournis, l'attribuer automatiquement
        initial_ref_uuid = data.get('initial_ref')  # Utiliser celui fourni si présent
        if annee_uuid and processus_uuid and not type_tableau_uuid:
            logger.info("[pac_get_or_create] type_tableau absent, appel à _get_next_type_tableau_for_context")
            try:
                auto_tt = _get_next_type_tableau_for_context(request.user, annee_uuid, processus_uuid)
                if auto_tt:
                    data = data.copy() if not isinstance(data, dict) else data
                    data['type_tableau'] = str(auto_tt.uuid)
                    type_tableau_uuid = data['type_tableau']
                    logger.info(f"[pac_get_or_create] type_tableau automatique défini: {type_tableau_uuid} (code: {auto_tt.code})")
                    
                    # Si c'est un amendement (AMENDEMENT_1 ou AMENDEMENT_2), trouver le PAC initial
                    # Sauf si initial_ref a déjà été fourni dans la requête
                    if auto_tt.code in ['AMENDEMENT_1', 'AMENDEMENT_2']:
                        if not initial_ref_uuid:
                            try:
                                # Trouver le PAC initial pour ce processus/année
                                pac_initial = Pac.objects.filter(
                                    cree_par=request.user,
                                    annee_id=annee_uuid,
                                    processus_id=processus_uuid,
                                    type_tableau__code='INITIAL'
                                ).first()
                                
                                if pac_initial:
                                    # Vérifier que le PAC initial est validé
                                    if not pac_initial.is_validated:
                                        logger.warning(f"[pac_get_or_create] ⚠️ Le PAC initial {pac_initial.uuid} n'est pas validé. Impossible de créer un amendement.")
                                        return Response({
                                            'error': 'Le PAC initial doit être validé avant de pouvoir créer un amendement. Veuillez d\'abord valider tous les détails et traitements du PAC initial.',
                                            'initial_pac_uuid': str(pac_initial.uuid)
                                        }, status=status.HTTP_400_BAD_REQUEST)
                                    
                                    initial_ref_uuid = str(pac_initial.uuid)
                                    data['initial_ref'] = initial_ref_uuid
                                    logger.info(f"[pac_get_or_create] PAC initial trouvé automatiquement: {initial_ref_uuid} pour l'amendement {auto_tt.code}")
                                else:
                                    logger.warning(f"[pac_get_or_create] ⚠️ Aucun PAC initial trouvé pour processus={processus_uuid}, annee={annee_uuid}. L'amendement sera créé sans initial_ref.")
                                    return Response({
                                        'error': 'Aucun PAC initial trouvé pour créer cet amendement. Veuillez d\'abord créer et valider un PAC initial.'
                                    }, status=status.HTTP_400_BAD_REQUEST)
                            except Exception as init_error:
                                logger.error(f"[pac_get_or_create] Erreur lors de la recherche du PAC initial: {init_error}")
                                import traceback
                                logger.error(traceback.format_exc())
                        else:
                            logger.info(f"[pac_get_or_create] initial_ref déjà fourni: {initial_ref_uuid}")
                    elif auto_tt.code == 'INITIAL':
                        # Pour un PAC INITIAL, initial_ref doit être null
                        if 'initial_ref' in data:
                            data.pop('initial_ref')
                            logger.info(f"[pac_get_or_create] initial_ref retiré car c'est un PAC INITIAL")
            except Exception as tt_error:
                logger.error(f"[pac_get_or_create] Erreur lors de la détermination automatique du type_tableau: {tt_error}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue sans type_tableau si erreur

        if not (annee_uuid and processus_uuid):
            logger.warning("[pac_get_or_create] annee ou processus manquant")
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis. 'type_tableau' peut être omis et sera déterminé automatiquement."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ========== VÉRIFICATION DES PERMISSIONS (Security by Design) ==========
        # Détecter si on crée un amendement (après la détermination automatique du type)
        is_creating_amendement = False
        if initial_ref_uuid:
            # Si initial_ref est fourni, c'est forcément un amendement
            is_creating_amendement = True
        elif type_tableau_uuid:
            # Vérifier le type_tableau pour déterminer si c'est un amendement
            try:
                from parametre.models import Versions
                type_tableau_obj = Versions.objects.get(uuid=type_tableau_uuid)
                if type_tableau_obj.code in ['AMENDEMENT_1', 'AMENDEMENT_2']:
                    is_creating_amendement = True
            except Versions.DoesNotExist:
                pass
        
        # Si on crée un amendement, vérifier la permission create_amendement_pac
        if is_creating_amendement:
            amendement_permission = PACAmendementCreatePermission()
            if not amendement_permission.has_permission(request, None):
                return Response({
                    'success': False,
                    'error': "Vous n'avez pas les permissions nécessaires pour créer un amendement PAC."
                }, status=status.HTTP_403_FORBIDDEN)
        else:
            # Pour un PAC initial, vérifier la permission create_pac
            try:
                pac_create_permission = PACCreatePermission()
                pac_create_permission.has_permission(request, None)
            except PermissionDenied as e:
                return Response({
                    'success': False,
                    'error': str(e) or "Vous n'avez pas les permissions nécessaires pour créer un PAC."
                }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION DES PERMISSIONS ==========

        # Vérifier si un PAC existe déjà avec ce (processus, annee, type_tableau)
        try:
            pac = Pac.objects.get(
                processus__uuid=processus_uuid,
                annee__uuid=annee_uuid,
                type_tableau__uuid=type_tableau_uuid,
                cree_par=request.user
            )
            logger.info(f"[pac_get_or_create] PAC existant trouvé: {pac.uuid}")
            
            # Sérialiser le PAC existant pour la réponse
            serializer = PacSerializer(pac)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Pac.DoesNotExist:
            logger.info(f"[pac_get_or_create] Aucun PAC existant, création d'un nouveau PAC")
            
            # S'assurer que data est un dictionnaire mutable
            if not isinstance(data, dict):
                data = data.copy() if hasattr(data, 'copy') else dict(data)
            
            # Si initial_ref n'est pas dans data mais qu'on doit créer un amendement, le trouver
            if 'initial_ref' not in data or not data.get('initial_ref'):
                # Vérifier si le type_tableau est un amendement
                if type_tableau_uuid:
                    try:
                        type_tableau_obj = Versions.objects.get(uuid=type_tableau_uuid)
                        if type_tableau_obj.code in ['AMENDEMENT_1', 'AMENDEMENT_2']:
                            # Trouver le PAC initial
                            pac_initial = Pac.objects.filter(
                                cree_par=request.user,
                                annee_id=annee_uuid,
                                processus_id=processus_uuid,
                                type_tableau__code='INITIAL'
                            ).first()
                            
                            if pac_initial:
                                # Vérifier que le PAC initial est validé
                                if not pac_initial.is_validated:
                                    logger.warning(f"[pac_get_or_create] ⚠️ Le PAC initial {pac_initial.uuid} n'est pas validé. Impossible de créer un amendement.")
                                    return Response({
                                        'error': 'Le PAC initial doit être validé avant de pouvoir créer un amendement. Veuillez d\'abord valider tous les détails et traitements du PAC initial.',
                                        'initial_pac_uuid': str(pac_initial.uuid)
                                    }, status=status.HTTP_400_BAD_REQUEST)
                                
                                data['initial_ref'] = str(pac_initial.uuid)
                                logger.info(f"[pac_get_or_create] PAC initial ajouté automatiquement: {pac_initial.uuid}")
                            else:
                                logger.warning(f"[pac_get_or_create] ⚠️ Aucun PAC initial trouvé pour créer l'amendement {type_tableau_obj.code}")
                                return Response({
                                    'error': 'Aucun PAC initial trouvé pour créer cet amendement. Veuillez d\'abord créer et valider un PAC initial.'
                                }, status=status.HTTP_400_BAD_REQUEST)
                    except Versions.DoesNotExist:
                        logger.warning(f"[pac_get_or_create] Type tableau {type_tableau_uuid} non trouvé")
                    except Exception as e:
                        logger.error(f"[pac_get_or_create] Erreur lors de la recherche du PAC initial: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
            else:
                logger.info(f"[pac_get_or_create] initial_ref fourni: {data.get('initial_ref')}")
                # Vérifier que le PAC initial fourni est validé
                initial_ref_uuid = data.get('initial_ref')
                if initial_ref_uuid:
                    try:
                        pac_initial = Pac.objects.get(uuid=initial_ref_uuid, cree_par=request.user)
                        if not pac_initial.is_validated:
                            logger.warning(f"[pac_get_or_create] ⚠️ Le PAC initial {initial_ref_uuid} n'est pas validé. Impossible de créer un amendement.")
                            return Response({
                                'error': 'Le PAC initial doit être validé avant de pouvoir créer un amendement. Veuillez d\'abord valider tous les détails et traitements du PAC initial.',
                                'initial_pac_uuid': str(initial_ref_uuid)
                            }, status=status.HTTP_400_BAD_REQUEST)
                    except Pac.DoesNotExist:
                        logger.warning(f"[pac_get_or_create] ⚠️ Le PAC initial {initial_ref_uuid} n'existe pas ou n'appartient pas à l'utilisateur.")
                        return Response({
                            'error': 'Le PAC initial spécifié n\'existe pas ou n\'appartient pas à votre compte.'
                        }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier aussi si le type_tableau est un amendement avant de créer
            if type_tableau_uuid:
                try:
                    type_tableau_obj = Versions.objects.get(uuid=type_tableau_uuid)
                    if type_tableau_obj.code in ['AMENDEMENT_1', 'AMENDEMENT_2']:
                        # S'assurer qu'on a un initial_ref et qu'il est validé
                        initial_ref_uuid = data.get('initial_ref')
                        if not initial_ref_uuid:
                            return Response({
                                'error': 'Un amendement doit être lié à un PAC initial validé. Aucun PAC initial trouvé.'
                            }, status=status.HTTP_400_BAD_REQUEST)
                except Versions.DoesNotExist:
                    pass  # Type tableau non trouvé, laisser le serializer gérer l'erreur
            
            # Créer un nouveau PAC
            create_serializer = PacCreateSerializer(data=data, context={'request': request})

            if create_serializer.is_valid():
                logger.info("[pac_get_or_create] Serializer valide, sauvegarde...")
                try:
                    pac = create_serializer.save()
                    logger.info(f"[pac_get_or_create] PAC créé avec succès: {pac.uuid}")
                except Exception as save_error:
                    logger.error(f"[pac_get_or_create] Erreur lors de la sauvegarde du PAC: {save_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Si c'est une erreur de contrainte unique, c'est qu'un autre utilisateur a créé le PAC entre temps
                    if 'unique_pac_per_processus_annee_type_tableau' in str(save_error) or 'unique_pac_per_processus_annee_type_tableau_user' in str(save_error) or 'UNIQUE constraint' in str(save_error):
                        try:
                            # Essayer de récupérer le PAC existant
                            pac = Pac.objects.get(
                                processus__uuid=processus_uuid,
                                annee__uuid=annee_uuid,
                                type_tableau__uuid=type_tableau_uuid,
                                cree_par=request.user
                            )
                            logger.info(f"[pac_get_or_create] PAC existant récupéré après erreur de contrainte: {pac.uuid}")
                            serializer = PacSerializer(pac)
                            return Response(serializer.data, status=status.HTTP_200_OK)
                        except Pac.DoesNotExist:
                            pass
                    
                    return Response({
                        'error': 'Erreur lors de la sauvegarde du PAC',
                        'details': str(save_error)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Log de l'activité
                try:
                    log_pac_creation(
                        user=request.user,
                        pac=pac,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT')
                    )
                    logger.info(f"[pac_get_or_create] Log d'activité créé avec succès")
                except Exception as log_error:
                    logger.error(f"[pac_get_or_create] Erreur lors du log d'activité (non bloquant): {log_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Continue car le PAC est déjà créé

                # Sérialiser le PAC pour la réponse
                try:
                    serializer = PacSerializer(pac)
                    logger.info(f"[pac_get_or_create] Sérialisation du PAC pour la réponse...")
                    logger.info(f"[pac_get_or_create] Sérialisation réussie, envoi de la réponse")
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Exception as serializer_error:
                    logger.error(f"[pac_get_or_create] Erreur lors de la sérialisation du PAC: {serializer_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return Response({
                        'error': 'Erreur lors de la sérialisation du PAC',
                        'details': str(serializer_error)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            logger.error(f"[pac_get_or_create] Erreurs de validation: {create_serializer.errors}")
            return Response(create_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Pac.MultipleObjectsReturned:
            # Cas théorique où plusieurs PACs existent (avant l'application de la contrainte)
            logger.warning("[pac_get_or_create] Plusieurs PACs trouvés, utilisation du premier")
            pac = Pac.objects.filter(
                processus__uuid=processus_uuid,
                annee__uuid=annee_uuid,
                type_tableau__uuid=type_tableau_uuid,
                cree_par=request.user
            ).first()
            serializer = PacSerializer(pac)
            return Response(serializer.data, status=status.HTTP_200_OK)

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
        
        # Vérifier que tous les détails et traitements sont renseignés
        details = pac.details.all()
        if not details.exists():
            return Response({
                'error': 'Le PAC doit avoir au moins un détail avant d\'être validé'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        for detail in details:
            if not hasattr(detail, 'traitement') or not detail.traitement:
                return Response({
                    'error': f'Le détail {detail.uuid} n\'a pas de traitement. Tous les détails doivent avoir un traitement avant validation.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            traitement = detail.traitement
            if not traitement.action:
                return Response({
                    'error': f'Le traitement du détail {detail.uuid} n\'a pas d\'action. Tous les traitements doivent être complets avant validation.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
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
    """Valider tous les PACs d'un même type_tableau (processus, année, type_tableau)"""
    try:
        processus_uuid = request.data.get('processus')
        annee_uuid = request.data.get('annee')
        type_tableau_uuid = request.data.get('type_tableau')
        
        if not all([processus_uuid, annee_uuid, type_tableau_uuid]):
            return Response({
                'error': 'processus, annee et type_tableau sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Récupérer tous les PACs du même contexte (processus, année, type_tableau) des processus de l'utilisateur
        pacs_to_validate = Pac.objects.filter(
            processus__uuid=processus_uuid,
            annee__uuid=annee_uuid,
            type_tableau__uuid=type_tableau_uuid
        ).select_related('processus', 'annee', 'type_tableau').prefetch_related('details__traitement')
        
        if not pacs_to_validate.exists():
            return Response({
                'error': 'Aucun PAC trouvé pour ce contexte'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Vérifier que tous les PACs peuvent être validés
        errors = []
        for pac in pacs_to_validate:
            if pac.is_validated:
                continue  # Déjà validé, on continue
            
            # Récupérer le numero_pac depuis le premier détail (comme dans le serializer)
            # Le modèle Pac n'a pas d'attribut numero_pac, il faut le récupérer depuis DetailsPac
            first_detail = pac.details.first()
            numero_pac_display = first_detail.numero_pac if first_detail and first_detail.numero_pac else str(pac.uuid)
            
            details = pac.details.all()
            if not details.exists():
                errors.append(f'Le PAC {numero_pac_display} doit avoir au moins un détail')
                continue
            
            for detail in details:
                if not hasattr(detail, 'traitement') or not detail.traitement:
                    errors.append(f'Le détail du PAC {numero_pac_display} n\'a pas de traitement')
                    break
                
                traitement = detail.traitement
                if not traitement.action:
                    errors.append(f'Le traitement du PAC {numero_pac_display} n\'a pas d\'action')
                    break
        
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
            f"{validated_count} PAC(s) validé(s) par type_tableau par {request.user.username}: "
            f"processus={processus_uuid}, annee={annee_uuid}, type_tableau={type_tableau_uuid}, "
            f"IP: {get_client_ip(request)}"
        )
        
        return Response({
            'message': f'{validated_count} PAC(s) validé(s) avec succès',
            'validated_count': validated_count,
            'total_count': pacs_to_validate.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la validation par type_tableau: {str(e)}")
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
                    
                    # Récupérer les informations supplémentaires
                    nature_label = traitement.details_pac.nature.nom if traitement.details_pac.nature else None
                    type_action = traitement.type_action.nom if traitement.type_action else None
                    
                    notifications.append({
                        'id': str(traitement.uuid),
                        'type': 'traitement',
                        'title': title,
                        'message': f'Délai de réalisation {delai_label}',
                        'due_date': delai_date.isoformat() if hasattr(delai_date, 'isoformat') else str(delai_date),
                        'priority': priority,
                        'action_url': action_url,
                        'nature_label': nature_label,
                        'type_action': type_action,
                        'delai_label': delai_label,
                        'pac_uuid': str(pac.uuid),
                        'traitement_uuid': str(traitement.uuid)
                    })
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
        
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les PACs sans filtre
            pacs_base = Pac.objects.all()
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
        
        # Filtrer uniquement les PACs initiaux (exclure les amendements)
        # Vérifier tous les codes de type_tableau pour debug
        all_pac_types = pacs_base.values_list('type_tableau__code', flat=True).distinct()
        logger.info(f"[pac_stats] Types de PACs trouvés: {list(all_pac_types)}")
        logger.info(f"[pac_stats] Nombre total de PACs de l'utilisateur: {pacs_base.count()}")
        
        # Filtrer les PACs initiaux (code peut être 'INITIAL' ou 'INITIALE')
        # Exclure les PACs avec type_tableau null
        pacs_initiaux_base = pacs_base.filter(
            type_tableau__isnull=False,
            type_tableau__code__in=['INITIAL', 'INITIALE']
        )
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
            'processus', 'cree_par', 'annee', 'type_tableau'
        ).prefetch_related('details__traitement', 'details__traitement__suivi')
        
        # Compter les PACs avec traitement et suivi
        # Pour "Avec Traitement", compter TOUS les PACs (initiaux ET amendements) qui ont des traitements
        pacs_avec_traitement = 0
        pacs_avec_suivi = 0
        
        # Récupérer TOUS les PACs des processus de l'utilisateur (initiaux ET amendements) pour compter ceux avec traitement
        # Utiliser pacs_base qui a déjà été filtré correctement (gère le cas super admin)
        all_pacs = pacs_base.select_related(
            'processus', 'cree_par', 'annee', 'type_tableau'
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
                    logger.info(f"[pac_stats] PAC {pac.uuid} (type: {pac.type_tableau.code if pac.type_tableau else 'None'}) a un traitement")
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
                'found': False
            }, status=status.HTTP_404_NOT_FOUND)

        logger.info(f"[get_last_pac_previous_year] Recherche du dernier PAC pour processus={processus_uuid}, année={annee_precedente.annee}")

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce processus. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Chercher tous les PACs de l'année précédente pour ce processus
        # Ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL
        codes_order = ['AMENDEMENT_2', 'AMENDEMENT_1', 'INITIAL']

        for code in codes_order:
            pac = Pac.objects.filter(
                annee=annee_precedente,
                processus__uuid=processus_uuid,
                type_tableau__code=code
            ).select_related('processus', 'annee', 'type_tableau', 'cree_par', 'validated_by').first()

            if pac:
                logger.info(f"[get_last_pac_previous_year] PAC trouvé: {pac.uuid} (type: {code})")
                serializer = PacSerializer(pac)
                return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun PAC trouvé pour l'année précédente
        logger.info(f"[get_last_pac_previous_year] Aucun PAC trouvé pour l'année {annee_precedente.annee}")
        return Response({
            'message': f'Aucun Plan d\'Action de Conformité trouvé pour l\'année {annee_precedente.annee}',
            'found': False
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier PAC de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération du PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
