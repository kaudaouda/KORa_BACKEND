"""
Vues API pour l'application PAC
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from .models import Pac, TraitementPac, PacSuivi, DetailsPac
from parametre.models import Processus, Media, Preuve, Versions
from parametre.views import log_pac_creation, log_pac_update, log_traitement_creation, log_suivi_creation, log_user_login, get_client_ip
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
        codes_order = ['INITIAL', 'AMENDEMENT_1', 'AMENDEMENT_2']
        existing_types = set(
            Pac.objects.filter(
                cree_par=user,
                annee_id=annee_uuid,
                processus_id=processus_uuid
            ).values_list('type_tableau__code', flat=True)
        )
        for code in codes_order:
            if code not in existing_types:
                return Versions.objects.get(code=code)
        # Tous déjà présents: retourner le dernier
        return Versions.objects.get(code=codes_order[-1])
    except Versions.DoesNotExist:
        # En cas de configuration incomplète, fallback sur le premier disponible
        return Versions.objects.order_by('nom').first()



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
        processus = Processus.objects.get(uuid=uuid, cree_par=request.user)
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
@permission_classes([IsAuthenticated])
def pac_list(request):
    """Liste des PACs de l'utilisateur connecté"""
    try:
        pacs = Pac.objects.filter(cree_par=request.user).select_related(
            'processus', 'nature', 'categorie', 'source', 'cree_par',
            'annee', 'type_tableau'
        ).order_by('-created_at')
        serializer = PacSerializer(pacs, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des PACs: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les PACs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pac_create(request):
    """Créer un nouveau PAC (nouvelle ligne)"""
    try:
        logger.info(f"Données reçues pour la création de PAC: {request.data}")
        data = request.data

        annee_uuid = data.get('annee')
        processus_uuid = data.get('processus')
        type_tableau_uuid = data.get('type_tableau')

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
@permission_classes([IsAuthenticated])
def pac_detail(request, uuid):
    """Détails d'un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid, cree_par=request.user)
        serializer = PacSerializer(pac)
        return Response(serializer.data)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le PAC'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
        ).get(uuid=uuid, cree_par=request.user)
        
        serializer = PacCompletSerializer(pac)
        return Response(serializer.data)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du PAC complet: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le PAC complet'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pac_get_or_create(request):
    """
    Créer une nouvelle ligne de PAC (même si le trio existe déjà).
    Plusieurs lignes peuvent avoir le même (processus, année, type_tableau).
    """
    try:
        data = request.data
        annee_uuid = data.get('annee')
        processus_uuid = data.get('processus')
        type_tableau_uuid = data.get('type_tableau')

        # Si type_tableau est absent mais annee + processus sont fournis, l'attribuer automatiquement
        if annee_uuid and processus_uuid and not type_tableau_uuid:
            auto_tt = _get_next_type_tableau_for_context(request.user, annee_uuid, processus_uuid)
            if auto_tt:
                data = data.copy()
                data['type_tableau'] = str(auto_tt.uuid)
                type_tableau_uuid = data['type_tableau']

        if not (annee_uuid and processus_uuid):
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis. 'type_tableau' peut être omis et sera déterminé automatiquement."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Toujours créer une nouvelle ligne de PAC
        create_serializer = PacCreateSerializer(data=data, context={'request': request})
        if create_serializer.is_valid():
            pac = create_serializer.save()
            log_pac_creation(
                user=request.user,
                pac=pac,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return Response(PacSerializer(pac).data, status=status.HTTP_201_CREATED)
        return Response(create_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Erreur pac_get_or_create: {str(e)}")
        return Response({
            'error': 'Impossible de traiter la demande'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def pac_update(request, uuid):
    """Mettre à jour un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid, cree_par=request.user)
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
@permission_classes([IsAuthenticated])
def pac_delete(request, uuid):
    """Supprimer un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid, cree_par=request.user)
        pac_info = {
            'uuid': str(pac.uuid),
            'libelle': pac.libelle,
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
@permission_classes([IsAuthenticated])
def pac_validate(request, uuid):
    """Valider un PAC (verrouille les champs PAC et Traitement)"""
    try:
        pac = Pac.objects.select_related('validated_by', 'cree_par').get(uuid=uuid)
        
        # Vérifier que l'utilisateur est le créateur ou un admin
        if pac.cree_par != request.user and not request.user.is_staff:
            return Response({
                'error': 'Vous n\'avez pas les permissions pour valider ce PAC'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
@permission_classes([IsAuthenticated])
def pac_unvalidate(request, uuid):
    """Dévalider un PAC (déverrouille les champs)"""
    try:
        pac = Pac.objects.select_related('validated_by', 'cree_par').get(uuid=uuid)
        
        # Vérifier que l'utilisateur est le créateur ou un admin
        if pac.cree_par != request.user and not request.user.is_staff:
            return Response({
                'error': 'Vous n\'avez pas les permissions pour dévalider ce PAC'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Vérifier si le PAC n'est pas validé
        if not pac.is_validated:
            return Response({
                'error': 'Ce PAC n\'est pas validé'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier qu'aucun suivi n'existe avant de dévalider
        from pac.models import DetailsPac, TraitementPac, PacSuivi
        details = pac.details.all()
        for detail in details:
            if hasattr(detail, 'traitement') and detail.traitement:
                traitement = detail.traitement
                if hasattr(traitement, 'suivi') and traitement.suivi:
                    return Response({
                        'error': 'Impossible de dévalider le PAC : des suivis existent déjà. Supprimez d\'abord les suivis.'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dévalider le PAC
        pac.is_validated = False
        pac.validated_at = None
        pac.validated_by = None
        pac.save()
        
        logger.info(
            f"PAC dévalidé par {request.user.username}: "
            f"PAC UUID: {uuid}, "
            f"IP: {get_client_ip(request)}"
        )
        
        return Response(PacSerializer(pac).data, status=status.HTTP_200_OK)
        
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la dévalidation du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de dévalider le PAC',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API TRAITEMENTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def traitement_list(request):
    """Liste des traitements"""
    try:
        traitements = TraitementPac.objects.filter(details_pac__pac__cree_par=request.user).order_by('-delai_realisation')
        serializer = TraitementPacSerializer(traitements, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des traitements: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les traitements'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def traitement_create(request):
    """Créer un nouveau traitement"""
    try:
        serializer = TraitementPacCreateSerializer(data=request.data)
        if serializer.is_valid():
            traitement = serializer.save()
            
            # Log de l'activité
            log_traitement_creation(
                user=request.user,
                traitement=traitement,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return Response(TraitementPacSerializer(traitement).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du traitement: {str(e)}")
        return Response({
            'error': 'Impossible de créer le traitement'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pac_traitements(request, uuid):
    """Récupérer les traitements d'un PAC spécifique"""
    try:
        # Vérifier que le PAC appartient à l'utilisateur connecté
        pac = Pac.objects.get(uuid=uuid, cree_par=request.user)
        
        # Récupérer les traitements du PAC via les détails (OneToOne)
        traitements = TraitementPac.objects.filter(details_pac__pac=pac).order_by('-delai_realisation')
        serializer = TraitementPacSerializer(traitements, many=True)
        return Response(serializer.data)
    except Pac.DoesNotExist:
        return Response({
            'error': 'PAC non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des traitements du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les traitements'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def traitement_detail(request, uuid):
    """Récupérer un traitement spécifique"""
    try:
        traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=uuid)
        
        # Vérifier que le PAC du détail du traitement appartient à l'utilisateur connecté
        if traitement.details_pac.pac.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = TraitementPacSerializer(traitement)
        return Response(serializer.data)
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
@permission_classes([IsAuthenticated])
def traitement_update(request, uuid):
    """Mettre à jour un traitement"""
    try:
        traitement = TraitementPac.objects.select_related('details_pac', 'details_pac__pac').get(uuid=uuid)
        
        # Vérifier que le PAC du détail du traitement appartient à l'utilisateur connecté
        if traitement.details_pac.pac.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
        suivis = PacSuivi.objects.filter(cree_par=request.user).order_by('-created_at')
        serializer = PacSuiviSerializer(suivis, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des suivis: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les suivis'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def traitement_suivis(request, uuid):
    """Récupérer les suivis d'un traitement PAC"""
    try:
        # Charger les relations nécessaires (OneToOne : un seul suivi par traitement)
        try:
            traitement = TraitementPac.objects.select_related('suivi').get(uuid=uuid)
            # Vérifier que le traitement appartient à un PAC de l'utilisateur connecté
            if traitement.details_pac.pac.cree_par != request.user:
                return Response({
                    'error': 'Accès non autorisé'
                }, status=status.HTTP_403_FORBIDDEN)
            
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
@permission_classes([IsAuthenticated])
def suivi_create(request):
    """Créer un nouveau suivi"""
    try:
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
            log_suivi_creation(
                user=request.user,
                suivi=suivi,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return Response(PacSuiviSerializer(suivi).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du suivi: {str(e)}")
        return Response({
            'error': 'Impossible de créer le suivi'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_detail(request, uuid):
    """Récupérer le détail d'un suivi"""
    try:
        suivi = PacSuivi.objects.select_related(
            'traitement', 'etat_mise_en_oeuvre', 'appreciation', 'preuve', 'statut'
        ).prefetch_related(
            'preuve__medias'
        ).get(uuid=uuid, cree_par=request.user)
        return Response(PacSuiviSerializer(suivi).data)
    except PacSuivi.DoesNotExist:
        return Response({'error': 'Suivi non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du suivi: {str(e)}")
        return Response({'error': "Impossible de récupérer le suivi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def suivi_update(request, uuid):
    """Mettre à jour un suivi"""
    try:
        suivi = PacSuivi.objects.get(uuid=uuid)
        if suivi.cree_par != request.user:
            return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)

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
    except PacSuivi.DoesNotExist:
        return Response({'error': 'Suivi non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du suivi: {str(e)}")
        return Response({'error': "Impossible de mettre à jour le suivi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== API DETAILS PAC ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def details_pac_list(request, uuid):
    """Liste des détails d'un PAC spécifique"""
    try:
        # Vérifier que le PAC appartient à l'utilisateur connecté
        pac = Pac.objects.get(uuid=uuid, cree_par=request.user)
        
        # Récupérer les détails du PAC
        details = DetailsPac.objects.filter(pac=pac).select_related(
            'pac', 'dysfonctionnement_recommandation', 'nature', 'categorie', 'source'
        ).order_by('periode_de_realisation')
        
        serializer = DetailsPacSerializer(details, many=True)
        return Response(serializer.data)
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
@permission_classes([IsAuthenticated])
def details_pac_create(request):
    """Créer un nouveau détail de PAC"""
    try:
        serializer = DetailsPacCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            detail = serializer.save()
            return Response(DetailsPacSerializer(detail).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du détail: {str(e)}")
        return Response({
            'error': 'Impossible de créer le détail'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def details_pac_detail(request, uuid):
    """Récupérer un détail spécifique"""
    try:
        detail = DetailsPac.objects.select_related(
            'pac', 'dysfonctionnement_recommandation', 'nature', 'categorie', 'source'
        ).get(uuid=uuid)
        
        # Vérifier que le PAC du détail appartient à l'utilisateur connecté
        if detail.pac.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = DetailsPacSerializer(detail)
        return Response(serializer.data)
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
@permission_classes([IsAuthenticated])
def details_pac_update(request, uuid):
    """Mettre à jour un détail de PAC"""
    try:
        detail = DetailsPac.objects.select_related('pac').get(uuid=uuid)
        
        # Vérifier que le PAC du détail appartient à l'utilisateur connecté
        if detail.pac.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
@permission_classes([IsAuthenticated])
def details_pac_delete(request, uuid):
    """Supprimer un détail de PAC"""
    try:
        detail = DetailsPac.objects.select_related('pac').get(uuid=uuid)
        
        # Vérifier que le PAC du détail appartient à l'utilisateur connecté
        if detail.pac.cree_par != request.user:
            return Response({
                'error': 'Accès non autorisé'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
