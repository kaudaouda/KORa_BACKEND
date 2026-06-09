from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from ..models import ActivitePeriodique, DetailsAP, SuivisAP
from permissions.permissions import (
    ActivitePeriodiqueListPermission,
    ActivitePeriodiqueCreatePermission,
    ActivitePeriodiqueUpdatePermission,
    ActivitePeriodiqueDeletePermission,
    ActivitePeriodiqueValidatePermission,
    ActivitePeriodiqueUnvalidatePermission,
    ActivitePeriodiqueReadPermission,
    ActivitePeriodiqueDetailPermission,
    ActivitePeriodiqueAmendementCreatePermission,
    ActivitePeriodiqueDetailCreatePermission,
    ActivitePeriodiqueDetailUpdatePermission,
    ActivitePeriodiqueDetailDeletePermission,
    ActivitePeriodiqueSuiviCreatePermission,
    ActivitePeriodiqueSuiviUpdatePermission,
    ActivitePeriodiqueSuiviDeletePermission,
)
from ..serializers import (
    ActivitePeriodiqueSerializer,
    ActivitePeriodiqueCompletSerializer,
    DetailsAPSerializer,
    DetailsAPCreateSerializer,
    SuivisAPSerializer,
    SuivisAPCreateSerializer,
    MediaLivrableSerializer,
    MediaLivrableCreateSerializer,
    MediaLivrableUpdateSerializer,
)
from parametre.models import Media
try:
    from parametre.models import MediaLivrable
except (ImportError, AttributeError):
    MediaLivrable = None
from parametre.models import Processus, Annee
from parametre.views import (
    log_activite_periodique_creation,
    log_activite_periodique_update,
    log_activite_periodique_validation,
    get_client_ip,
)
from parametre.permissions import check_permission_or_403, get_user_processus_list, user_has_access_to_processus
import logging

logger = logging.getLogger(__name__)

from .utils import _has_amendements_following, _get_next_num_amendement_for_ap

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def activite_periodique_home(request):
    """Endpoint de base pour l'activité périodique"""
    try:
        return Response({
            'success': True,
            'message': 'API Activité Périodique',
            'data': {
                'version': '1.0.0',
                'description': 'Application de gestion des activités périodiques'
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur dans activite_periodique_home: %s", str(e))
        return Response({
            'success': False,
            'message': 'Erreur serveur',
            'error': "Une erreur inattendue s'est produite. Veuillez réessayer."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueListPermission])
def activites_periodiques_list(request):
    """Liste toutes les Activités Périodiques de l'utilisateur connecté"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les Activités Périodiques sans filtre
            aps = ActivitePeriodique.objects.all().select_related(
                'processus', 'annee', 'cree_par', 'validated_by'
            ).prefetch_related('amendements').order_by('-annee__annee', 'processus__numero_processus')
        elif not user_processus_uuids:
            # Aucun processus assigné
            logger.info("[activites_periodiques_list] Aucun processus assigné pour l'utilisateur %s", request.user.username)
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucune Activité Périodique trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Filtrer les Activités Périodiques par les processus où l'utilisateur a un rôle actif
            aps = ActivitePeriodique.objects.filter(processus__uuid__in=user_processus_uuids).select_related(
                'processus', 'annee', 'cree_par', 'validated_by'
            ).prefetch_related('amendements').order_by('-annee__annee', 'processus__numero_processus')
        # ========== FIN FILTRAGE ==========
        
        serializer = ActivitePeriodiqueSerializer(aps, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': aps.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Erreur dans activites_periodiques_list: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des Activités Périodiques',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueDetailPermission])
def activite_periodique_detail(request, uuid):
    """Détails d'une Activité Périodique spécifique"""
    try:
        ap = ActivitePeriodique.objects.select_related(
            'processus', 'annee', 'cree_par', 'validated_by'
        ).prefetch_related(
            'details__frequence',
            'details__suivis__mois',
            'details__suivis__etat_mise_en_oeuvre',
            'details__responsables_directions',
            'details__responsables_sous_directions',
            'details__responsables_services'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par ActivitePeriodiqueDetailPermission
        # via le décorateur @permission_classes (gère automatiquement les super admins)
        
        serializer = ActivitePeriodiqueCompletSerializer(ap)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans activite_periodique_detail: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération de l\'Activité Périodique',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueCreatePermission])
def activite_periodique_get_or_create(request):
    """
    Récupérer ou créer une Activité Périodique unique pour (processus, annee, num_amendement).
    """
    try:
        logger.info("[activite_periodique_get_or_create] Début - données reçues: %s", request.data)
        data = request.data.copy()
        annee_value = data.get('annee')
        processus_uuid = data.get('processus')

        # Convertir annee en entier si c'est une chaîne
        if annee_value:
            try:
                annee_value = int(annee_value)
            except (ValueError, TypeError):
                return Response({
                    'error': "Le champ 'annee' doit être un nombre entier"
                }, status=status.HTTP_400_BAD_REQUEST)

        # Déterminer num_amendement : utiliser la valeur fournie ou l'attribuer automatiquement
        num_amendement_raw = data.get('num_amendement')
        if num_amendement_raw is None and annee_value and processus_uuid:
            try:
                num_amendement_value = _get_next_num_amendement_for_ap(request.user, annee_value, processus_uuid)
                data['num_amendement'] = num_amendement_value
            except Exception as tt_error:
                logger.error("[activite_periodique_get_or_create] Erreur détermination automatique num_amendement: %s", tt_error)
                num_amendement_value = 0
                data['num_amendement'] = num_amendement_value
        else:
            try:
                num_amendement_value = int(num_amendement_raw) if num_amendement_raw is not None else 0
            except (ValueError, TypeError):
                num_amendement_value = 0
            data['num_amendement'] = num_amendement_value

        logger.info("[activite_periodique_get_or_create] annee=%s, processus_uuid=%s, num_amendement=%s", annee_value, processus_uuid, num_amendement_value)

        if not (annee_value and processus_uuid):
            logger.warning("[activite_periodique_get_or_create] annee ou processus manquant")
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis."
            }, status=status.HTTP_400_BAD_REQUEST)

        # ========== VÉRIFICATION DES PERMISSIONS (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueCreatePermission vérifie déjà
        # la permission create_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION DES PERMISSIONS ==========

        # Récupérer l'objet Annee
        try:
            annee_obj = Annee.objects.get(annee=annee_value)
        except Annee.DoesNotExist:
            return Response({
                'error': f"Année {annee_value} non trouvée dans la base de données"
            }, status=status.HTTP_404_NOT_FOUND)

        # Vérifier si une AP existe déjà avec ce (processus, annee, type_tableau)
        # Note: On cherche d'abord une AP créée par l'utilisateur pour ce contexte
        # Si aucune n'existe, on vérifiera l'accès au processus avant de créer
        try:
            ap = ActivitePeriodique.objects.get(
                processus__uuid=processus_uuid,
                annee=annee_obj,
                num_amendement=num_amendement_value,
                cree_par=request.user
            )
            logger.info("[activite_periodique_get_or_create] AP existante trouvée: %s", ap.uuid)
            
            # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
            # Même si l'AP a été créée par l'utilisateur, vérifier qu'il a toujours accès au processus
            if not user_has_access_to_processus(request.user, ap.processus.uuid):
                return Response({
                    'success': False,
                    'error': 'Vous n\'avez pas accès à cette Activité Périodique. Vous n\'avez pas de rôle actif pour ce processus.'
                }, status=status.HTTP_403_FORBIDDEN)
            # ========== FIN VÉRIFICATION ==========
            
            serializer = ActivitePeriodiqueSerializer(ap)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except ActivitePeriodique.DoesNotExist:
            logger.info("[activite_periodique_get_or_create] Aucune AP existante, création d'une nouvelle AP")

            # Créer une nouvelle AP
            data['annee'] = str(annee_obj.uuid)
            # Ne pas passer cree_par dans data, le serializer le gère via le contexte

            serializer = ActivitePeriodiqueSerializer(data=data, context={'request': request})

            if serializer.is_valid():
                logger.info("[activite_periodique_get_or_create] Serializer valide, données validées: %s", serializer.validated_data)
                ap = serializer.save()
                logger.info("[activite_periodique_get_or_create] AP créée avec succès: %s", ap.uuid)

                # Log de l'activité
                try:
                    ip_address = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    log_activite_periodique_creation(request.user, ap, ip_address, user_agent)
                except Exception as log_error:
                    logger.error("Erreur lors du logging de la création de l'AP: %s", log_error)

                response_serializer = ActivitePeriodiqueSerializer(ap)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)

            logger.error("[activite_periodique_get_or_create] Erreurs de validation: %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error("[activite_periodique_get_or_create] Erreur exception non gérée: %s", str(e))
        import traceback
        logger.error("[activite_periodique_get_or_create] Traceback: %s", traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la création/récupération de l\'Activité Périodique',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueCreatePermission])
def activite_periodique_create(request):
    """Créer une nouvelle Activité Périodique"""
    try:
        data = request.data.copy()
        processus_uuid = data.get('processus')
        
        # ========== VÉRIFICATION DES PERMISSIONS (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueCreatePermission vérifie déjà
        # la permission create_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION DES PERMISSIONS ==========
        
        # Ne pas passer cree_par dans data, le serializer le gère via le contexte
        serializer = ActivitePeriodiqueSerializer(data=data, context={'request': request})

        if serializer.is_valid():
            ap = serializer.save()

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_activite_periodique_creation(request.user, ap, ip_address, user_agent)
            except Exception as log_error:
                logger.error("Erreur lors du logging de la création de l'AP: %s", log_error)

            response_serializer = ActivitePeriodiqueSerializer(ap)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Erreur dans activite_periodique_create: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la création de l\'Activité Périodique',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueUpdatePermission])
def activite_periodique_update(request, uuid):
    """Mettre à jour une Activité Périodique"""
    try:
        ap = ActivitePeriodique.objects.select_related('processus', 'annee').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, ap.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à cette Activité Périodique. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # ========== VÉRIFICATION PERMISSION ÉCRIRE (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueUpdatePermission vérifie déjà
        # la permission update_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(ap):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ActivitePeriodiqueSerializer(ap, data=request.data, partial=True, context={'request': request})

        if serializer.is_valid():
            ap = serializer.save()

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_activite_periodique_update(request.user, ap, ip_address, user_agent)
            except Exception as log_error:
                logger.error("Erreur lors du logging de la mise à jour de l'AP: %s", log_error)

            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans activite_periodique_update: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la mise à jour de l\'Activité Périodique',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueDeletePermission])
def activite_periodique_delete(request, uuid):
    """Supprimer une Activité Périodique"""
    try:
        ap = ActivitePeriodique.objects.get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, ap.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à cette Activité Périodique. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # ========== VÉRIFICATION PERMISSION ÉCRIRE (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueDeletePermission vérifie déjà
        # la permission delete_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION ==========
        
        ap.delete()
        return Response({
            'success': True,
            'message': 'Activité Périodique supprimée avec succès'
        }, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans activite_periodique_delete: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la suppression de l\'Activité Périodique',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueValidatePermission])
def activite_periodique_validate(request, uuid):
    """Valider une Activité Périodique"""
    try:
        ap = ActivitePeriodique.objects.select_related('processus', 'annee').prefetch_related(
            'details__frequence',
            'details__responsables_directions',
            'details__responsables_sous_directions',
            'details__responsables_services'
        ).get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueValidatePermission vérifie déjà
        # la permission validate_activite_periodique, donc pas besoin de vérifier ici
        if not user_has_access_to_processus(request.user, ap.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à cette Activité Périodique. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier qu'il y a au moins un détail
        details = ap.details.all()
        if not details.exists():
            return Response({
                'error': 'Impossible de valider: aucune activité périodique n\'a de détails renseignés'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que tous les champs requis de chaque détail sont renseignés
        details_incomplets = []
        for detail in details:
            champs_manquants = []
            
            # Vérifier activites_periodiques
            if not detail.activites_periodiques or not detail.activites_periodiques.strip():
                champs_manquants.append('Activités périodiques')
            
            # Vérifier frequence
            if not detail.frequence:
                champs_manquants.append('Fréquence')
            
            # Vérifier qu'au moins un responsable est renseigné
            has_responsable = (
                detail.responsables_directions.exists() or
                detail.responsables_sous_directions.exists() or
                detail.responsables_services.exists()
            )
            if not has_responsable:
                champs_manquants.append('Responsabilité')
            
            if champs_manquants:
                details_incomplets.append({
                    'numero_ap': detail.numero_ap or str(detail.uuid),
                    'champs_manquants': champs_manquants
                })
        
        if details_incomplets:
            messages_erreur = []
            for detail_incomplet in details_incomplets:
                messages_erreur.append(
                    f"Détail {detail_incomplet['numero_ap']}: {', '.join(detail_incomplet['champs_manquants'])}"
                )
            return Response({
                'error': 'Impossible de valider: certains détails ne sont pas complets',
                'details_incomplets': details_incomplets,
                'message': 'Les champs suivants doivent être renseignés pour tous les détails: ' + ', '.join(messages_erreur)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider l'AP
        ap.is_validated = True
        ap.validated_at = timezone.now()
        ap.validated_by = request.user
        ap.save()

        # Log de l'activité
        try:
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            log_activite_periodique_validation(request.user, ap, ip_address, user_agent)
        except Exception as log_error:
            logger.error("Erreur lors du logging de la validation de l'AP: %s", log_error)

        serializer = ActivitePeriodiqueSerializer(ap)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans activite_periodique_validate: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la validation de l\'Activité Périodique',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueUnvalidatePermission])
def activite_periodique_unvalidate(request, uuid):
    """Dévalider une Activité Périodique (déverrouille les champs)"""
    try:
        ap = ActivitePeriodique.objects.select_related('validated_by', 'cree_par', 'processus', 'annee').get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueUnvalidatePermission vérifie déjà
        # la permission unvalidate_activite_periodique, donc pas besoin de vérifier ici
        if not user_has_access_to_processus(request.user, ap.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à cette Activité Périodique. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier si l'AP n'est pas validée
        if not ap.is_validated:
            return Response({
                'error': 'Cette Activité Périodique n\'est pas validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dévalider l'AP (même s'il y a des suivis, l'utilisateur avec la permission peut dévalider)
        ap.is_validated = False
        ap.validated_at = None
        ap.validated_by = None
        ap.save()
        
        # Log de l'activité
        try:
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            logger.info(
                "Dévalidation AP - User: %s, AP: %s, UUID: %s, Processus: %s, IP: %s, User-Agent: %s", request.user.email, ap.numero_ap or ap.uuid, ap.uuid, ap.processus.nom if ap.processus else None, ip_address, user_agent
            )
        except Exception as log_error:
            logger.error("Erreur lors du logging de la dévalidation de l'AP: %s", log_error)
        
        serializer = ActivitePeriodiqueSerializer(ap)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except ActivitePeriodique.DoesNotExist:
        logger.error("Tentative de dévalidation d'une AP inexistante: %s par %s", uuid, request.user.username)
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Erreur dans activite_periodique_unvalidate: %s", str(e))
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la dévalidation de l\'Activité Périodique',
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS API DETAILS AP ====================

