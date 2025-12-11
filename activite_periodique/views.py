"""
Vues API pour l'application Activité Périodique
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import ActivitePeriodique, DetailsAP, SuivisAP
from .serializers import (
    ActivitePeriodiqueSerializer,
    ActivitePeriodiqueCompletSerializer,
    DetailsAPSerializer,
    DetailsAPCreateSerializer,
    SuivisAPSerializer,
    SuivisAPCreateSerializer
)
from parametre.models import Processus, Annee, Versions
from parametre.views import (
    log_activite_periodique_creation,
    log_activite_periodique_update,
    log_activite_periodique_validation,
    get_client_ip
)
import logging

logger = logging.getLogger(__name__)


# ==================== UTILITAIRES TYPE TABLEAU ====================

def _has_amendements_following(ap):
    """
    Vérifier si un AP a des amendements suivants (doit être verrouillé).
    Un tableau doit être verrouillé si un tableau plus récent a été créé pour le même contexte.
    """
    try:
        type_code = ap.type_tableau.code if ap.type_tableau else None
        
        if type_code == 'INITIAL':
            # Pour INITIAL : vérifier s'il y a AMENDEMENT_1 ou AMENDEMENT_2 pour le même processus/année
            return ActivitePeriodique.objects.filter(
                processus=ap.processus,
                annee=ap.annee,
                type_tableau__code__in=['AMENDEMENT_1', 'AMENDEMENT_2'],
                cree_par=ap.cree_par
            ).exists()
        elif type_code == 'AMENDEMENT_1':
            # Pour AMENDEMENT_1 : vérifier s'il y a AMENDEMENT_2 créé après lui pour le même processus/année
            return ActivitePeriodique.objects.filter(
                processus=ap.processus,
                annee=ap.annee,
                type_tableau__code='AMENDEMENT_2',
                cree_par=ap.cree_par,
                created_at__gt=ap.created_at  # Créé après cet AMENDEMENT_1
            ).exists()
        elif type_code == 'AMENDEMENT_2':
            # AMENDEMENT_2 ne peut pas avoir d'amendements suivants
            return False
        else:
            # Par défaut, vérifier les amendements directs (relation inverse)
            return ap.amendements.exists()
    except Exception as e:
        logger.error(f'Erreur dans _has_amendements_following: {str(e)}')
        return False

def _get_next_type_tableau_for_ap(user, annee, processus_uuid):
    """
    Retourne l'instance Versions à utiliser automatiquement pour (annee, processus) d'un user.
    Ordre: INITIAL -> AMENDEMENT_1 -> AMENDEMENT_2. Si tous existent déjà, retourne AMENDEMENT_2.
    """
    try:
        logger.info(f"[_get_next_type_tableau_for_ap] user={user}, annee={annee}, processus_uuid={processus_uuid}")
        codes_order = ['INITIAL', 'AMENDEMENT_1', 'AMENDEMENT_2']
        existing_types = set(
            ActivitePeriodique.objects.filter(
                cree_par=user,
                annee__annee=annee,
                processus_id=processus_uuid
            ).values_list('type_tableau__code', flat=True)
        )
        logger.info(f"[_get_next_type_tableau_for_ap] existing_types={existing_types}")
        for code in codes_order:
            if code not in existing_types:
                version = Versions.objects.get(code=code)
                logger.info(f"[_get_next_type_tableau_for_ap] Retourne version {code}: {version}")
                return version
        # Tous déjà présents: retourner le dernier
        version = Versions.objects.get(code=codes_order[-1])
        logger.info(f"[_get_next_type_tableau_for_ap] Tous présents, retourne {version}")
        return version
    except Versions.DoesNotExist as e:
        logger.error(f"[_get_next_type_tableau_for_ap] Versions.DoesNotExist: {e}")
        fallback = Versions.objects.order_by('nom').first()
        logger.info(f"[_get_next_type_tableau_for_ap] Fallback sur {fallback}")
        return fallback
    except Exception as e:
        logger.error(f"[_get_next_type_tableau_for_ap] Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


# ==================== ENDPOINTS API ACTIVITE PERIODIQUE ====================

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
        logger.error(f'Erreur dans activite_periodique_home: {str(e)}')
        return Response({
            'success': False,
            'message': 'Erreur serveur',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def activites_periodiques_list(request):
    """Liste toutes les Activités Périodiques de l'utilisateur connecté"""
    try:
        aps = ActivitePeriodique.objects.filter(cree_par=request.user).select_related(
            'processus', 'type_tableau', 'annee', 'cree_par', 'validated_by'
        ).prefetch_related('amendements').order_by('-annee__annee', 'processus__numero_processus')
        
        serializer = ActivitePeriodiqueSerializer(aps, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans activites_periodiques_list: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des Activités Périodiques',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def activite_periodique_detail(request, uuid):
    """Détails d'une Activité Périodique spécifique"""
    try:
        ap = ActivitePeriodique.objects.select_related(
            'processus', 'type_tableau', 'annee', 'cree_par', 'validated_by'
        ).prefetch_related(
            'details__frequence',
            'details__suivis__mois',
            'details__suivis__etat_mise_en_oeuvre',
            'details__responsables_directions',
            'details__responsables_sous_directions',
            'details__responsables_services'
        ).get(uuid=uuid, cree_par=request.user)
        
        serializer = ActivitePeriodiqueCompletSerializer(ap)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans activite_periodique_detail: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération de l\'Activité Périodique',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activite_periodique_get_or_create(request):
    """
    Récupérer ou créer une Activité Périodique unique pour (processus, annee, type_tableau).
    """
    try:
        logger.info(f"[activite_periodique_get_or_create] Début - données reçues: {request.data}")
        data = request.data.copy()
        annee_value = data.get('annee')
        processus_uuid = data.get('processus')
        type_tableau_uuid = data.get('type_tableau')

        # Convertir annee en entier si c'est une chaîne
        if annee_value:
            try:
                annee_value = int(annee_value)
            except (ValueError, TypeError):
                return Response({
                    'error': "Le champ 'annee' doit être un nombre entier"
                }, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"[activite_periodique_get_or_create] annee={annee_value}, processus_uuid={processus_uuid}, type_tableau_uuid={type_tableau_uuid}")

        # Si type_tableau est absent mais annee + processus sont fournis, l'attribuer automatiquement
        initial_ref_uuid = data.get('initial_ref')
        if annee_value and processus_uuid and not type_tableau_uuid:
            logger.info("[activite_periodique_get_or_create] type_tableau absent, appel à _get_next_type_tableau_for_ap")
            try:
                auto_tt = _get_next_type_tableau_for_ap(request.user, annee_value, processus_uuid)
                if auto_tt:
                    data['type_tableau'] = str(auto_tt.uuid)
                    type_tableau_uuid = data['type_tableau']
                    logger.info(f"[activite_periodique_get_or_create] type_tableau automatique défini: {type_tableau_uuid} (code: {auto_tt.code})")
            except Exception as tt_error:
                logger.error(f"[activite_periodique_get_or_create] Erreur lors de la détermination automatique du type_tableau: {tt_error}")

        if not (annee_value and processus_uuid):
            logger.warning("[activite_periodique_get_or_create] annee ou processus manquant")
            return Response({
                'error': "Les champs 'annee' et 'processus' sont requis. 'type_tableau' peut être omis et sera déterminé automatiquement."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer l'objet Annee
        try:
            annee_obj = Annee.objects.get(annee=annee_value)
        except Annee.DoesNotExist:
            return Response({
                'error': f"Année {annee_value} non trouvée dans la base de données"
            }, status=status.HTTP_404_NOT_FOUND)

        # Vérifier si une AP existe déjà avec ce (processus, annee, type_tableau)
        try:
            ap = ActivitePeriodique.objects.get(
                processus__uuid=processus_uuid,
                annee=annee_obj,
                type_tableau__uuid=type_tableau_uuid,
                cree_par=request.user
            )
            logger.info(f"[activite_periodique_get_or_create] AP existante trouvée: {ap.uuid}")
            serializer = ActivitePeriodiqueSerializer(ap)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except ActivitePeriodique.DoesNotExist:
            logger.info(f"[activite_periodique_get_or_create] Aucune AP existante, création d'une nouvelle AP")

            # Créer une nouvelle AP
            data['annee'] = str(annee_obj.uuid)
            # Ne pas passer cree_par dans data, le serializer le gère via le contexte

            serializer = ActivitePeriodiqueSerializer(data=data, context={'request': request})

            if serializer.is_valid():
                logger.info(f"[activite_periodique_get_or_create] Serializer valide, données validées: {serializer.validated_data}")
                ap = serializer.save()
                logger.info(f"[activite_periodique_get_or_create] AP créée avec succès: {ap.uuid}")

                # Log de l'activité
                try:
                    ip_address = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    log_activite_periodique_creation(request.user, ap, ip_address, user_agent)
                except Exception as log_error:
                    logger.error(f"Erreur lors du logging de la création de l'AP: {log_error}")

                response_serializer = ActivitePeriodiqueSerializer(ap)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)

            logger.error(f"[activite_periodique_get_or_create] Erreurs de validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"[activite_periodique_get_or_create] Erreur exception non gérée: {str(e)}")
        import traceback
        logger.error(f"[activite_periodique_get_or_create] Traceback: {traceback.format_exc()}")
        return Response({
            'error': 'Erreur lors de la création/récupération de l\'Activité Périodique',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activite_periodique_create(request):
    """Créer une nouvelle Activité Périodique"""
    try:
        data = request.data.copy()
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
                logger.error(f"Erreur lors du logging de la création de l'AP: {log_error}")

            response_serializer = ActivitePeriodiqueSerializer(ap)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f'Erreur dans activite_periodique_create: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la création de l\'Activité Périodique',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def activite_periodique_update(request, uuid):
    """Mettre à jour une Activité Périodique"""
    try:
        ap = ActivitePeriodique.objects.select_related('type_tableau', 'processus', 'annee').get(uuid=uuid, cree_par=request.user)
        
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
                logger.error(f"Erreur lors du logging de la mise à jour de l'AP: {log_error}")

            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans activite_periodique_update: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la mise à jour de l\'Activité Périodique',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def activite_periodique_delete(request, uuid):
    """Supprimer une Activité Périodique"""
    try:
        ap = ActivitePeriodique.objects.get(uuid=uuid, cree_par=request.user)
        ap.delete()
        return Response({
            'message': 'Activité Périodique supprimée avec succès'
        }, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans activite_periodique_delete: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la suppression de l\'Activité Périodique',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activite_periodique_validate(request, uuid):
    """Valider une Activité Périodique"""
    try:
        ap = ActivitePeriodique.objects.select_related('processus', 'annee', 'type_tableau').prefetch_related(
            'details__frequence',
            'details__responsables_directions',
            'details__responsables_sous_directions',
            'details__responsables_services'
        ).get(uuid=uuid, cree_par=request.user)
        
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
            logger.error(f"Erreur lors du logging de la validation de l'AP: {log_error}")

        serializer = ActivitePeriodiqueSerializer(ap)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans activite_periodique_validate: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la validation de l\'Activité Périodique',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS API DETAILS AP ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def details_ap_list(request):
    """Liste tous les détails AP de l'utilisateur connecté"""
    try:
        details = DetailsAP.objects.filter(activite_periodique__cree_par=request.user).select_related(
            'activite_periodique', 'responsabilite_direction', 'responsabilite_sous_direction', 'responsabilite_service'
        ).prefetch_related('responsables_directions', 'responsables_sous_directions', 'responsables_services')
        
        serializer = DetailsAPSerializer(details, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_list: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des détails AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def details_ap_by_activite_periodique(request, ap_uuid):
    """Récupérer tous les détails AP pour une Activité Périodique spécifique"""
    try:
        # Vérifier que l'AP existe et appartient à l'utilisateur
        ap = ActivitePeriodique.objects.get(uuid=ap_uuid, cree_par=request.user)
        
        # Récupérer les détails AP
        details = DetailsAP.objects.filter(activite_periodique=ap).select_related(
            'activite_periodique', 'responsabilite_direction', 'responsabilite_sous_direction', 'responsabilite_service', 'frequence'
        ).prefetch_related('responsables_directions', 'responsables_sous_directions', 'responsables_services', 'suivis__mois', 'suivis__etat_mise_en_oeuvre')
        
        serializer = DetailsAPSerializer(details, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ActivitePeriodique.DoesNotExist:
        return Response({
            'error': 'Activité Périodique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_by_activite_periodique: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des détails AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def details_ap_create(request):
    """Créer un nouveau détail AP"""
    try:
        data = request.data.copy()
        ap_uuid = data.get('activite_periodique')
        
        # Vérifier que l'AP existe et appartient à l'utilisateur
        try:
            ap = ActivitePeriodique.objects.get(uuid=ap_uuid, cree_par=request.user)
        except ActivitePeriodique.DoesNotExist:
            return Response({
                'error': 'Activité Périodique non trouvée'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Vérifier que l'AP n'est pas validée
        if ap.is_validated:
            return Response({
                'error': 'Impossible d\'ajouter un détail à une Activité Périodique validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(ap):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DetailsAPCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            detail = serializer.save()
            # Utiliser DetailsAPSerializer pour la réponse (avec tous les champs read_only)
            response_serializer = DetailsAPSerializer(detail)
            logger.info(f"[details_ap_create] ✅ Détail créé avec succès: {detail.uuid}, numero_ap: {detail.numero_ap}")
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_create: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la création du détail AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def details_ap_update(request, uuid):
    """Mettre à jour un détail AP"""
    try:
        detail = DetailsAP.objects.select_related('activite_periodique', 'activite_periodique__type_tableau', 'activite_periodique__processus', 'activite_periodique__annee').get(
            uuid=uuid,
            activite_periodique__cree_par=request.user
        )
        
        # Vérifier que l'AP n'est pas validée
        if detail.activite_periodique.is_validated:
            return Response({
                'error': 'Impossible de modifier un détail d\'une Activité Périodique validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(detail.activite_periodique):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DetailsAPSerializer(detail, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except DetailsAP.DoesNotExist:
        return Response({
            'error': 'Détail AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_update: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la mise à jour du détail AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def details_ap_delete(request, uuid):
    """Supprimer un détail AP"""
    try:
        detail = DetailsAP.objects.select_related('activite_periodique', 'activite_periodique__type_tableau', 'activite_periodique__processus', 'activite_periodique__annee').get(
            uuid=uuid,
            activite_periodique__cree_par=request.user
        )
        
        # Vérifier que l'AP n'est pas validée
        if detail.activite_periodique.is_validated:
            return Response({
                'error': 'Impossible de supprimer un détail d\'une Activité Périodique validée'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que l'AP n'a pas d'amendements suivants (les tableaux précédents ne peuvent plus être modifiés)
        if _has_amendements_following(detail.activite_periodique):
            return Response({
                'error': 'Impossible de modifier ce tableau : un amendement a déjà été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        detail.delete()
        return Response({
            'message': 'Détail AP supprimé avec succès'
        }, status=status.HTTP_200_OK)
    except DetailsAP.DoesNotExist:
        return Response({
            'error': 'Détail AP non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Erreur dans details_ap_delete: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la suppression du détail AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ENDPOINTS API SUIVIS AP ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivis_ap_list(request):
    """Liste tous les suivis AP de l'utilisateur connecté"""
    try:
        suivis = SuivisAP.objects.filter(
            details_ap__activite_periodique__cree_par=request.user
        ).select_related('details_ap', 'mois', 'etat_mise_en_oeuvre')
        
        serializer = SuivisAPSerializer(suivis, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f'Erreur dans suivis_ap_list: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération des suivis AP',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suivis_ap_by_detail_ap(request, detail_ap_uuid):
    """Récupérer tous les suivis AP pour un détail AP spécifique"""
    try:
        # Vérifier que le détail AP existe et appartient à l'utilisateur
        detail_ap = DetailsAP.objects.select_related('activite_periodique').get(
            uuid=detail_ap_uuid,
            activite_periodique__cree_par=request.user
        )
        
        # Récupérer les suivis
        suivis = SuivisAP.objects.filter(details_ap=detail_ap).select_related('mois', 'etat_mise_en_oeuvre')
        
        serializer = SuivisAPSerializer(suivis, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
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
@permission_classes([IsAuthenticated])
def suivi_ap_create(request):
    """Créer un nouveau suivi AP"""
    try:
        data = request.data.copy()
        detail_ap_uuid = data.get('details_ap')
        
        # Vérifier que le détail AP existe et appartient à l'utilisateur
        try:
            detail_ap = DetailsAP.objects.select_related('activite_periodique', 'activite_periodique__type_tableau', 'activite_periodique__processus', 'activite_periodique__annee').get(
                uuid=detail_ap_uuid,
                activite_periodique__cree_par=request.user
            )
        except DetailsAP.DoesNotExist:
            return Response({
                'error': 'Détail AP non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Vérifier que l'AP est validée (les suivis ne peuvent être renseignés que si l'AP est validée)
        # Exception : permettre la création lors de la copie d'amendement
        from_amendment_copy = data.get('from_amendment_copy', False)
        if not detail_ap.activite_periodique.is_validated and not from_amendment_copy:
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
@permission_classes([IsAuthenticated])
def suivi_ap_update(request, uuid):
    """Mettre à jour un suivi AP"""
    try:
        suivi = SuivisAP.objects.select_related(
            'details_ap__activite_periodique', 'details_ap__activite_periodique__type_tableau', 
            'details_ap__activite_periodique__processus', 'details_ap__activite_periodique__annee',
            'mois', 'etat_mise_en_oeuvre'
        ).get(
            uuid=uuid,
            details_ap__activite_periodique__cree_par=request.user
        )
        
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
@permission_classes([IsAuthenticated])
def suivi_ap_delete(request, uuid):
    """Supprimer un suivi AP"""
    try:
        suivi = SuivisAP.objects.select_related(
            'details_ap__activite_periodique', 'mois', 'etat_mise_en_oeuvre'
        ).get(
            uuid=uuid,
            details_ap__activite_periodique__cree_par=request.user
        )

        # Vérifier que l'AP n'a pas d'amendements (verrouillée)
        ap = suivi.details_ap.activite_periodique
        if _has_amendements_following(ap):
            return Response({
                'error': 'Ce tableau ne peut plus être modifié car un amendement a été créé. Veuillez modifier l\'amendement correspondant.'
            }, status=status.HTTP_400_BAD_REQUEST)

        suivi.delete()
        return Response({
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

        # Chercher tous les APs de l'année précédente pour ce processus
        # Ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL
        codes_order = ['AMENDEMENT_2', 'AMENDEMENT_1', 'INITIAL']

        for code in codes_order:
            ap = ActivitePeriodique.objects.filter(
                cree_par=request.user,
                annee=annee_precedente,
                processus__uuid=processus_uuid,
                type_tableau__code=code
            ).select_related('processus', 'annee', 'type_tableau', 'cree_par', 'validated_by').first()

            if ap:
                logger.info(f"[get_last_ap_previous_year] AP trouvé: {ap.uuid} (type: {code})")
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
@permission_classes([IsAuthenticated])
def activite_periodique_stats(request):
    """Statistiques des Activités Périodiques de l'utilisateur connecté"""
    try:
        logger.info(f"[activite_periodique_stats] Début pour l'utilisateur: {request.user.username}")

        # Récupérer toutes les Activités Périodiques de l'utilisateur
        aps_base = ActivitePeriodique.objects.filter(cree_par=request.user)
        logger.info(f"[activite_periodique_stats] Nombre total d'APs: {aps_base.count()}")

        # Filtrer uniquement les APs initiaux (exclure les amendements)
        aps_initiaux = aps_base.filter(
            type_tableau__isnull=False,
            type_tableau__code='INITIAL'
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
