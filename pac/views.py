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
from .models import Pac, Traitement, Suivi
from parametre.models import Processus
from .serializers import (
    UserSerializer, ProcessusSerializer, ProcessusCreateSerializer,
    PacSerializer, PacCreateSerializer, PacUpdateSerializer, TraitementSerializer, 
    TraitementCreateSerializer, SuiviSerializer, SuiviCreateSerializer
)
from shared.authentication import AuthService
from shared.services.recaptcha_service import recaptcha_service, RecaptchaValidationError
import json
import logging

logger = logging.getLogger(__name__)


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Récupérer le profil de l'utilisateur connecté"""
    try:
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


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """Rafraîchir le token d'accès"""
    try:
        refresh_token = request.COOKIES.get('refresh_token')
        
        if not refresh_token:
            return Response({
                'error': 'Refresh token manquant',
                'code': 'REFRESH_TOKEN_MISSING'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_token)
            access_token = refresh.access_token

            # Créer la réponse
            response = Response({
                'message': 'Token rafraîchi avec succès'
            }, status=status.HTTP_200_OK)

            # Mettre à jour le cookie access_token
            response.set_cookie(
                'access_token',
                str(access_token),
                max_age=60 * 60,  # 1 heure
                httponly=True,
                secure=False,  # True en production avec HTTPS
                samesite='Lax'
            )

            return response

        except Exception as e:
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
@permission_classes([AllowAny])
def recaptcha_config(request):
    """Obtenir la configuration reCAPTCHA pour le frontend"""
    try:
        from django.conf import settings
        
        config = {
            'enabled': recaptcha_service.is_enabled(),
            'site_key': getattr(settings, 'RECAPTCHA_SITE_KEY', None),
            'min_score': recaptcha_service.get_min_score(),
        }
        
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
            'processus', 'nature', 'categorie', 'source', 'cree_par'
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
    """Créer un nouveau PAC"""
    try:
        serializer = PacCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            pac = serializer.save()
            return Response(PacSerializer(pac).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du PAC: {str(e)}")
        return Response({
            'error': 'Impossible de créer le PAC'
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


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def pac_update(request, uuid):
    """Mettre à jour un PAC"""
    try:
        pac = Pac.objects.get(uuid=uuid, cree_par=request.user)
        serializer = PacUpdateSerializer(pac, data=request.data, partial=True)
        if serializer.is_valid():
            updated_pac = serializer.save()
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


# ==================== API TRAITEMENTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def traitement_list(request):
    """Liste des traitements"""
    try:
        traitements = Traitement.objects.filter(pac__cree_par=request.user).order_by('-delai_realisation')
        serializer = TraitementSerializer(traitements, many=True)
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
        serializer = TraitementCreateSerializer(data=request.data)
        if serializer.is_valid():
            traitement = serializer.save()
            return Response(TraitementSerializer(traitement).data, status=status.HTTP_201_CREATED)
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
        
        # Récupérer les traitements du PAC
        traitements = Traitement.objects.filter(pac=pac).order_by('-delai_realisation')
        serializer = TraitementSerializer(traitements, many=True)
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


# ==================== API SUIVIS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivi_list(request):
    """Liste des suivis"""
    try:
        suivis = Suivi.objects.filter(cree_par=request.user).order_by('-created_at')
        serializer = SuiviSerializer(suivis, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des suivis: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les suivis'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suivi_create(request):
    """Créer un nouveau suivi"""
    try:
        serializer = SuiviCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            suivi = serializer.save()
            return Response(SuiviSerializer(suivi).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur lors de la création du suivi: {str(e)}")
        return Response({
            'error': 'Impossible de créer le suivi'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
