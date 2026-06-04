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

def suivis_ap_list(request):
    """Liste tous les suivis AP de l'utilisateur connecté"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        if not user_processus_uuids:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'Aucun suivi AP trouvé pour vos processus attribués.'
            }, status=status.HTTP_200_OK)

        suivis = SuivisAP.objects.filter(
            details_ap__activite_periodique__processus__uuid__in=user_processus_uuids
        ).select_related('details_ap', 'mois', 'etat_mise_en_oeuvre')
        # ========== FIN FILTRAGE ==========
        
        serializer = SuivisAPSerializer(suivis, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': suivis.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans suivis_ap_list: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des suivis AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueReadPermission])
def suivis_ap_by_detail_ap(request, detail_ap_uuid):
    """Récupérer tous les suivis AP pour un détail AP spécifique"""
    try:
        detail_ap = DetailsAP.objects.select_related('activite_periodique', 'activite_periodique__processus').get(
            uuid=detail_ap_uuid
        )
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # La permission ActivitePeriodiqueReadPermission vérifie déjà l'accès au processus via l'AP
        # Mais on garde cette vérification pour cohérence
        if not user_has_access_to_processus(request.user, detail_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce détail. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Récupérer les suivis
        suivis = SuivisAP.objects.filter(details_ap=detail_ap).select_related('mois', 'etat_mise_en_oeuvre')
        
        serializer = SuivisAPSerializer(suivis, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': suivis.count()
        }, status=status.HTTP_200_OK)
    except DetailsAP.DoesNotExist:
        return Response({
            'error': 'Détail AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans suivis_ap_by_detail_ap: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des suivis AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueSuiviCreatePermission])
def suivi_ap_create(request):
    """Créer un nouveau suivi AP"""
    try:
        data = request.data.copy()
        detail_ap_uuid = data.get('details_ap')
        
        # Vérifier que le détail AP existe
        try:
            detail_ap = DetailsAP.objects.select_related('activite_periodique', 'activite_periodique__processus', 'activite_periodique__annee').get(
                uuid=detail_ap_uuid
            )
        except DetailsAP.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Détail AP non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, detail_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce détail. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # ========== VÉRIFICATION PERMISSION ÉCRIRE (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueSuiviCreatePermission vérifie déjà
        # la permission create_suivi_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP est validée (les suivis ne peuvent être renseignés que si l'AP est validée)
        # Exception : permettre la création lors de la copie d'amendement ou pour les super admins / superviseur SMI
        from_amendment_copy = data.get('from_amendment_copy', False)
        from parametre.permissions import can_manage_users, is_super_admin, is_supervisor_smi
        is_super = can_manage_users(request.user) or is_super_admin(request.user) or is_supervisor_smi(request.user)
        
        if not detail_ap.activite_periodique.is_validated and not from_amendment_copy and not is_super:
            return Response({
                'error': 'Impossible d\'ajouter un suivi: l\'Activité Périodique doit être validée d\'abord. Veuillez remplir tous les champs requis des détails et valider le tableau.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(detail_ap.activite_periodique):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SuivisAPCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            suivi = serializer.save()
            response_serializer = SuivisAPSerializer(suivi)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f'Erreur dans suivi_ap_create: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la création du suivi AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueSuiviUpdatePermission])
def suivi_ap_update(request, uuid):
    """Mettre à jour un suivi AP"""
    try:
        suivi = SuivisAP.objects.select_related(
            'details_ap__activite_periodique', 
            'details_ap__activite_periodique__processus', 'details_ap__activite_periodique__annee',
            'mois', 'etat_mise_en_oeuvre'
        ).get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, suivi.details_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce suivi. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # ========== VÉRIFICATION PERMISSION ÉCRIRE (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueSuiviUpdatePermission vérifie déjà
        # la permission update_suivi_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP est validée (les suivis ne peuvent être modifiés que si l'AP est validée)
        if not suivi.details_ap.activite_periodique.is_validated:
            return Response({
                'error': 'Impossible de modifier un suivi: l\'Activité Périodique doit être validée d\'abord. Veuillez remplir tous les champs requis des détails et valider le tableau.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(suivi.details_ap.activite_periodique):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SuivisAPSerializer(suivi, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except SuivisAP.DoesNotExist:
        return Response({
            'error': 'Suivi AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans suivi_ap_update: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la mise à jour du suivi AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueSuiviDeletePermission])
def suivi_ap_delete(request, uuid):
    """Supprimer un suivi AP"""
    try:
        suivi = SuivisAP.objects.select_related(
            'details_ap__activite_periodique', 'details_ap__activite_periodique__processus',
            'mois', 'etat_mise_en_oeuvre'
        ).get(uuid=uuid)

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, suivi.details_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce suivi. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # ========== VÉRIFICATION PERMISSION ÉCRIRE (Security by Design) ==========
        # Note: La permission DRF ActivitePeriodiqueSuiviDeletePermission vérifie déjà
        # la permission delete_suivi_activite_periodique, donc pas besoin de vérifier ici
        # ========== FIN VÉRIFICATION ==========

        # Vérifier que l'AP n'a pas d'amendements (verrouillée)
        ap = suivi.details_ap.activite_periodique
        if _has_amendements_following(ap):
            return Response({
                'error': 'Ce tableau ne peut plus être modifié car un amendement a été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)

        suivi.delete()
        return Response({
            'success': True,
            'message': 'Suivi AP supprimé avec succès'
        }, status=status.HTTP_200_OK)
    except SuivisAP.DoesNotExist:
        return Response({
            'error': 'Suivi AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans suivi_ap_delete: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la suppression du suivi AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_ap_previous_year(request):
    """
    Récupérer le dernier AP (INITIAL, AMENDEMENT_1 ou AMENDEMENT_2) de l'année précédente
    pour un processus donné.

    Query params:
    - annee: valeur de l'année actuelle (integer)
    - processus: UUID du processus

    Retourne le dernier type de tableau (ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL)
    """
    try:
        annee_value = request.query_params.get('annee')
        processus_uuid = request.query_params.get('processus')

        if not annee_value or not processus_uuid:
            return Response({
                'error': 'Les paramètres annee et processus sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Convertir annee en entier
        try:
            annee_actuelle_valeur = int(annee_value)
            annee_precedente_valeur = annee_actuelle_valeur - 1
        except (ValueError, TypeError):
            return Response({
                'error': 'Le paramètre annee doit être un nombre entier'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier que l'année précédente existe
        try:
            annee_precedente = Annee.objects.get(annee=annee_precedente_valeur)
        except Annee.DoesNotExist:
            logger.info(f"[get_last_ap_previous_year] Année précédente {annee_precedente_valeur} non trouvée")
            return Response({
                'message': f'Aucune année {annee_precedente_valeur} trouvée dans le système',
                'found': False
            }, status=status.HTTP_404_NOT_FOUND)

        logger.info(f"[get_last_ap_previous_year] Recherche du dernier AP pour processus={processus_uuid}, année={annee_precedente.annee}")

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce processus. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Retourner le dernier AP (num_amendement le plus élevé)
        ap = ActivitePeriodique.objects.filter(
            annee=annee_precedente,
            processus__uuid=processus_uuid,
        ).select_related('processus', 'annee', 'cree_par', 'validated_by').order_by('-num_amendement').first()

        if ap:
            logger.info(f"[get_last_ap_previous_year] AP trouvé: {ap.uuid} (num_amendement: {ap.num_amendement})")
            serializer = ActivitePeriodiqueSerializer(ap)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun AP trouvé pour l'année précédente
        logger.info(f"[get_last_ap_previous_year] Aucun AP trouvé pour l'année {annee_precedente.annee}")
        return Response({
            'message': f'Aucune Activité Périodique trouvée pour l\'année {annee_precedente.annee}',
            'found': False
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier AP de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération de l\'AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATISTIQUES ACTIVITE PERIODIQUE ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueListPermission])
def activite_periodique_stats(request):
    """Statistiques des Activités Périodiques de l'utilisateur connecté"""
    try:
        logger.info(f"[activite_periodique_stats] Début pour l'utilisateur: {request.user.username}")
        scope = request.query_params.get('scope', 'tous')

        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les AP, avec filtre processus optionnel (?processus=UUID)
            aps_base = ActivitePeriodique.objects.all()
            processus_filter = request.query_params.get('processus')
            if processus_filter and str(processus_filter).upper() != 'ALL':
                try:
                    from uuid import UUID
                    UUID(str(processus_filter))
                    aps_base = aps_base.filter(processus__uuid=processus_filter)
                except (ValueError, TypeError):
                    pass
        elif not user_processus_uuids:
            # Aucun processus assigné
            logger.info(f"[activite_periodique_stats] Aucun processus assigné pour l'utilisateur {request.user.username}")
            return Response({
                'success': True,
                'data': {
                    'total_aps': 0, 'aps_valides': 0, 'aps_en_attente': 0,
                    'total_details': 0, 'total_suivis': 0
                },
                'message': 'Aucune donnée d\'Activité Périodique trouvée pour vos processus attribués.'
            }, status=status.HTTP_200_OK)
        else:
            # Récupérer toutes les Activités Périodiques des processus de l'utilisateur
            aps_base = ActivitePeriodique.objects.filter(processus__uuid__in=user_processus_uuids)
        logger.info(f"[activite_periodique_stats] Nombre total d'APs: {aps_base.count()}")
        # ========== FIN FILTRAGE ==========

        # Filtrer selon le scope
        if scope == 'dernier':
            from django.db.models import Case, When, IntegerField, Max
            type_priority = Case(
                When(num_amendement=2, then=3),
                When(num_amendement=1, then=2),
                When(num_amendement=0, then=1),
                default=0, output_field=IntegerField()
            )
            annotated = aps_base.annotate(priority=type_priority)
            last_uuids = []
            for proc_uuid in annotated.values_list('processus', flat=True).distinct():
                max_p = annotated.filter(processus=proc_uuid).aggregate(max_p=Max('priority'))['max_p']
                last = annotated.filter(processus=proc_uuid, priority=max_p).first()
                if last:
                    last_uuids.append(last.uuid)
            aps_initiaux = aps_base.filter(uuid__in=last_uuids)
        else:
            aps_initiaux = aps_base.filter(
                num_amendement=0
            )
        logger.info(f"[activite_periodique_stats] Nombre d'APs initiaux: {aps_initiaux.count()}")

        total_aps = aps_initiaux.count()

        # Compter les APs validées
        aps_valides = aps_initiaux.filter(is_validated=True).count()
        logger.info(f"[activite_periodique_stats] APs validées: {aps_valides}")

        # Compter les APs en attente
        aps_en_attente = aps_initiaux.filter(is_validated=False).count()
        logger.info(f"[activite_periodique_stats] APs en attente: {aps_en_attente}")

        # Compter le total de détails et suivis pour les APs initiaux
        total_details = DetailsAP.objects.filter(
            activite_periodique__in=aps_initiaux
        ).count()

        total_suivis = SuivisAP.objects.filter(
            details_ap__activite_periodique__in=aps_initiaux
        ).count()

        logger.info(f"[activite_periodique_stats] Détails: {total_details}, Suivis: {total_suivis}")

        # Construire la réponse
        stats = {
            'total_aps': total_aps,
            'aps_valides': aps_valides,
            'aps_en_attente': aps_en_attente,
            'total_details': total_details,
            'total_suivis': total_suivis
        }

        logger.info(f"[activite_periodique_stats] Statistiques calculées: {stats}")

        return Response(stats, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques AP: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des statistiques',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== MEDIA LIVRABLE ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def media_livrables_by_suivi(request, suivi_uuid):
    """Récupérer tous les MediaLivrable d'un suivi AP"""
    try:
        if MediaLivrable is None:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': 'MediaLivrable non disponible (migration non appliquée)'
            }, status=status.HTTP_200_OK)
        
        suivi = SuivisAP.objects.select_related(
            'details_ap__activite_periodique__processus'
        ).get(uuid=suivi_uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, suivi.details_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce suivi. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        media_livrables = MediaLivrable.objects.filter(suivi_ap=suivi).prefetch_related('medias').order_by('-created_at')
        serializer = MediaLivrableSerializer(media_livrables, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': media_livrables.count()
        }, status=status.HTTP_200_OK)
    except SuivisAP.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Suivi AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans media_livrables_by_suivi: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des MediaLivrable'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueSuiviUpdatePermission])
def media_livrable_create(request):
    """Créer un nouveau MediaLivrable"""
    try:
        suivi_uuid = request.data.get('suivi_ap')
        if not suivi_uuid:
            return Response({
                'success': False,
                'error': 'Le suivi AP est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            suivi = SuivisAP.objects.select_related(
                'details_ap__activite_periodique__processus'
            ).get(uuid=suivi_uuid)
        except SuivisAP.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Suivi AP non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, suivi.details_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce suivi. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP n'a pas d'amendements (verrouillée)
        ap = suivi.details_ap.activite_periodique
        if _has_amendements_following(ap):
            return Response({
                'success': False,
                'error': 'Ce tableau ne peut plus être modifié car un amendement a été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = MediaLivrableCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            media_livrable = serializer.save()
            response_serializer = MediaLivrableSerializer(media_livrable)
            return Response({
                'success': True,
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f'Erreur lors de la création du MediaLivrable: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la création du MediaLivrable'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueSuiviUpdatePermission])
def media_livrable_update(request, uuid):
    """Mettre à jour un MediaLivrable"""
    try:
        try:
            media_livrable = MediaLivrable.objects.select_related(
                'suivi_ap__details_ap__activite_periodique__processus'
            ).get(uuid=uuid)
        except MediaLivrable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'MediaLivrable non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        suivi = media_livrable.suivi_ap
        if not user_has_access_to_processus(request.user, suivi.details_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce MediaLivrable. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP n'a pas d'amendements (verrouillée)
        ap = suivi.details_ap.activite_periodique
        if _has_amendements_following(ap):
            return Response({
                'success': False,
                'error': 'Ce tableau ne peut plus être modifié car un amendement a été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = MediaLivrableUpdateSerializer(media_livrable, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            media_livrable = serializer.save()
            response_serializer = MediaLivrableSerializer(media_livrable)
            return Response({
                'success': True,
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f'Erreur lors de la mise à jour du MediaLivrable: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour du MediaLivrable'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, ActivitePeriodiqueSuiviUpdatePermission])
def media_livrable_delete(request, uuid):
    """Supprimer un MediaLivrable"""
    try:
        try:
            media_livrable = MediaLivrable.objects.select_related(
                'suivi_ap__details_ap__activite_periodique__processus'
            ).get(uuid=uuid)
        except MediaLivrable.DoesNotExist:
            return Response({
                'success': False,
                'error': 'MediaLivrable non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        suivi = media_livrable.suivi_ap
        if not user_has_access_to_processus(request.user, suivi.details_ap.activite_periodique.processus.uuid):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas accès à ce MediaLivrable. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========
        
        # Vérifier que l'AP n'a pas d'amendements (verrouillée)
        ap = suivi.details_ap.activite_periodique
        if _has_amendements_following(ap):
            return Response({
                'success': False,
                'error': 'Ce tableau ne peut plus être modifié car un amendement a été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        media_livrable.delete()
        return Response({
            'success': True,
            'message': 'MediaLivrable supprimé avec succès'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur lors de la suppression du MediaLivrable: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression du MediaLivrable'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
