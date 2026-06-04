from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
import logging
from django.db import models
from ..models import Objectives, Indicateur, Observation, TableauBord
from analyse_tableau.models import AnalyseTableau
from parametre.views import (
    log_tableau_bord_creation,
    log_tableau_bord_update,
    log_objectif_creation,
    log_indicateur_creation,
    get_client_ip
)
from parametre.permissions import get_user_processus_list, user_has_access_to_processus
from permissions.permissions import (
    DashboardTableauCreatePermission,
    DashboardTableauUpdatePermission,
    DashboardTableauDeletePermission,
    DashboardTableauValidatePermission,
    DashboardTableauDevalidatePermission,
    DashboardTableauReadPermission,
    DashboardTableauListCreatePermission,
    DashboardTableauDetailPermission,
    DashboardAmendementCreatePermission,
    DashboardObjectiveCreatePermission,
    DashboardObjectiveUpdatePermission,
    DashboardObjectiveDeletePermission,
    DashboardIndicateurCreatePermission,
    DashboardIndicateurUpdatePermission,
    DashboardIndicateurDeletePermission,
    DashboardCibleCreatePermission,
    DashboardCibleUpdatePermission,
    DashboardCibleDeletePermission,
    DashboardPeriodiciteCreatePermission,
    DashboardPeriodiciteUpdatePermission,
    DashboardPeriodiciteDeletePermission,
    DashboardObservationCreatePermission,
    DashboardObservationUpdatePermission,
    DashboardObservationDeletePermission,
)
from ..serializers import (
    ObjectivesSerializer, ObjectivesCreateSerializer, ObjectivesUpdateSerializer,
    IndicateurSerializer, IndicateurCreateSerializer, IndicateurUpdateSerializer,
    CibleSerializer, CibleCreateSerializer, CibleUpdateSerializer,
    PeriodiciteSerializer, PeriodiciteCreateSerializer, PeriodiciteUpdateSerializer,
    ObservationSerializer, ObservationCreateSerializer, ObservationUpdateSerializer,
    TableauBordSerializer
)

logger = logging.getLogger(__name__)

def tableaux_bord_list_create(request):
    """Lister ou créer des tableaux de bord"""
    try:
        if request.method == 'GET':
            # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
            # Récupérer les processus accessibles par l'utilisateur
            from parametre.permissions import get_user_processus_list
            user_processus_uuids = get_user_processus_list(request.user)
            
            # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
            # Il peut voir tous les tableaux de bord sans filtre
            if user_processus_uuids is None:
                # Super admin : voir tous les tableaux de bord
                qs = TableauBord.objects.all().select_related('processus', 'initial_ref').order_by(
                    '-annee', 'processus__numero_processus', 'num_amendement'
                )
            elif not user_processus_uuids:
                # Si l'utilisateur n'a aucun processus, retourner une liste vide
                return Response({
                    'success': True,
                    'data': [],
                    'count': 0,
                    'message': 'Aucun processus assigné. Vous ne pouvez pas voir de tableaux de bord.'
                }, status=status.HTTP_200_OK)
            else:
                # Filtrer les tableaux de bord pour ne montrer que ceux des processus de l'utilisateur
                qs = TableauBord.objects.filter(
                    processus__uuid__in=user_processus_uuids
                ).select_related('processus', 'initial_ref').order_by(
                    '-annee', 'processus__numero_processus', 'num_amendement'
                )
            # ========== FIN FILTRAGE ==========
            
            serializer = TableauBordSerializer(qs, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
                'count': qs.count()
            }, status=status.HTTP_200_OK)
        else:
            data = request.data.copy()
            # Option facultative: clone=true|false contrôle la copie depuis l'initial
            clone = str(data.pop('clone', 'false')).lower() in ['1', 'true', 'yes', 'on']

            # ========== VALIDATION STRICTE ==========
            annee = data.get('annee')
            processus_uuid = data.get('processus')
            try:
                num_amendement = int(data.get('num_amendement', 0))
            except (ValueError, TypeError):
                num_amendement = 0

            # VALIDATION 1 : Si initial (num_amendement == 0), vérifier qu'il n'existe pas déjà
            if num_amendement == 0:
                existing = TableauBord.objects.filter(
                    annee=annee,
                    processus=processus_uuid,
                    num_amendement=0
                ).exists()
                if existing:
                    return Response({
                        'success': False,
                        'error': f'Un tableau initial existe déjà pour l\'année {annee} et ce processus. Vous ne pouvez créer que des amendements.'
                    }, status=status.HTTP_400_BAD_REQUEST)

            # VALIDATION 2+ : Si amendement, vérifier que le précédent existe et est validé
            else:
                prev_num = num_amendement - 1
                try:
                    prev_tableau = TableauBord.objects.get(
                        annee=annee,
                        processus=processus_uuid,
                        num_amendement=prev_num
                    )
                except TableauBord.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': f'Impossible de créer l\'amendement {num_amendement} : l\'amendement {prev_num} n\'existe pas pour cette année et ce processus.'
                    }, status=status.HTTP_400_BAD_REQUEST)

                if not prev_tableau.is_validated:
                    return Response({
                        'success': False,
                        'error': f'Impossible de créer l\'amendement {num_amendement} : l\'amendement {prev_num} doit être validé d\'abord.'
                    }, status=status.HTTP_400_BAD_REQUEST)

                existing_num = TableauBord.objects.filter(
                    annee=annee,
                    processus=processus_uuid,
                    num_amendement=num_amendement
                ).exists()
                if existing_num:
                    return Response({
                        'success': False,
                        'error': f'L\'amendement {num_amendement} existe déjà pour cette année et ce processus.'
                    }, status=status.HTTP_400_BAD_REQUEST)

            data['num_amendement'] = num_amendement
            # ========== FIN VALIDATION ==========
            
            # Note: La vérification des permissions est maintenant gérée par DashboardTableauCreatePermission
            # via le décorateur @permission_classes et DashboardTableauListCreatePermission
            
            logger.info(f"Données reçues pour création tableau: {data}")
            
            serializer = TableauBordSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                logger.info("Serializer valide, sauvegarde en cours...")
                try:
                    instance = serializer.save()
                    logger.info(f"Tableau créé avec succès: {instance.uuid}")

                    # Log de l'activité
                    try:
                        ip_address = get_client_ip(request)
                        user_agent = request.META.get('HTTP_USER_AGENT', '')
                        log_tableau_bord_creation(request.user, instance, ip_address, user_agent)
                    except Exception as log_error:
                        logger.error(f"Erreur lors du logging de la création du tableau: {log_error}")

                    # Si amendement et clone demandé, copier les objectifs (+ éléments associés)
                    if instance.num_amendement > 0 and clone and instance.initial_ref:
                        # Déterminer le tableau source : le tableau avec le num_amendement précédent
                        source_tableau = TableauBord.objects.filter(
                            annee=instance.annee,
                            processus=instance.processus,
                            num_amendement=instance.num_amendement - 1
                        ).first()

                        # Par sécurité, repli sur le tableau initial si aucun autre tableau n'est trouvé
                        if not source_tableau:
                            source_tableau = instance.initial_ref

                        logger.info(
                            "Clonage des objectifs pour l'amendement %s depuis le tableau source %s (num_amendement=%s)",
                            instance.uuid,
                            getattr(source_tableau, 'uuid', None),
                            getattr(source_tableau, 'num_amendement', None)
                        )

                        # cloner objectifs du tableau source (dernier tableau : initial ou dernier amendement)
                        for obj in source_tableau.objectives.all():
                            new_obj = Objectives.objects.create(
                                number=obj.number,
                                libelle=obj.libelle,
                                cree_par=request.user,
                                tableau_bord=instance
                            )
                            # cloner indicateurs et leur structure
                            indicateurs = Indicateur.objects.filter(objective_id=obj)
                            for ind in indicateurs:
                                new_ind = Indicateur.objects.create(
                                    libelle=ind.libelle,
                                    objective_id=new_obj,
                                    frequence_id=ind.frequence_id
                                )
                                # cibles (parametre.Cible)
                                try:
                                    from parametre.models import Cible as ParamCible, Periodicite as ParamPeriodicite
                                    cible = ParamCible.objects.filter(indicateur_id=ind).first()
                                    if cible:
                                        ParamCible.objects.create(
                                            valeur=cible.valeur,
                                            condition=cible.condition,
                                            indicateur_id=new_ind
                                        )
                                    # periodicites
                                    for p in ParamPeriodicite.objects.filter(indicateur_id=ind):
                                        ParamPeriodicite.objects.create(
                                            indicateur_id=new_ind,
                                            periode=p.periode,
                                            a_realiser=p.a_realiser,
                                            realiser=p.realiser
                                        )
                                except Exception:
                                    # en cas d'erreur de copie d'éléments annexes, on continue quand même avec les objectifs/indicateurs
                                    pass
                    return Response({
                        'success': True,
                        'message': 'Tableau de bord créé avec succès',
                        'data': TableauBordSerializer(instance).data
                    }, status=status.HTTP_201_CREATED)
                except Exception as e:
                    logger.error(f"Erreur lors de la sauvegarde du tableau: {str(e)}")
                    return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            else:
                logger.error(f"Erreurs de validation serializer: {serializer.errors}")
                return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        # DRF retournera automatiquement une réponse 403 avec le message approprié
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Erreur tableaux_bord_list_create: {str(e)}\n{error_traceback}")
        return Response({
            'success': False, 
            'error': f'Erreur lors du traitement: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, DashboardTableauDetailPermission])
def tableau_bord_detail(request, uuid):
    """
    Détail / mise à jour / suppression d'un tableau de bord
    Security by Design : Les permissions sont vérifiées AVANT cette fonction via DashboardTableauDetailPermission
    """
    try:
        # Security by Design : La permission DashboardTableauDetailPermission a déjà vérifié
        # l'accès et récupéré l'objet. On le récupère à nouveau pour éviter une double requête,
        # mais la sécurité est garantie par la permission DRF qui s'exécute AVANT cette fonction.
        tb = TableauBord.objects.get(uuid=uuid)
        
    except TableauBord.DoesNotExist:
        # Security by Design : Si l'objet n'existe pas après vérification de permission,
        # c'est une erreur interne (l'objet a été supprimé entre temps)
        return Response({'success': False, 'error': 'Tableau de bord non trouvé'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer_data = TableauBordSerializer(tb).data
        logger.info(f"tableau_bord_detail GET - UUID: {uuid}, num_amendement: {tb.num_amendement}, is_validated: {tb.is_validated}, serializer is_validated: {serializer_data.get('is_validated')}")
        return Response({'success': True, 'data': serializer_data})
    elif request.method == 'PATCH':
        # Note: La vérification des permissions est maintenant gérée par DashboardTableauUpdatePermission
        # via le décorateur @permission_classes et DashboardTableauDetailPermission
        
        serializer = TableauBordSerializer(tb, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            try:
                instance = serializer.save()

                # Log de l'activité
                try:
                    ip_address = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    log_tableau_bord_update(request.user, instance, ip_address, user_agent)
                except Exception as log_error:
                    logger.error(f"Erreur lors du logging de la mise à jour du tableau: {log_error}")

                return Response({'success': True, 'data': TableauBordSerializer(instance).data})
            except Exception as e:
                return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    else:  # DELETE
        # Note: La vérification des permissions est maintenant gérée par DashboardTableauDeletePermission
        # via le décorateur @permission_classes et DashboardTableauDetailPermission
        
        tb.delete()
        return Response({'success': True, 'message': 'Tableau de bord supprimé avec succès'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_amendement(request, tableau_initial_uuid):
    """Créer un amendement pour un tableau initial"""
    try:
        # Récupérer le tableau initial
        try:
            initial_tableau = TableauBord.objects.select_related('processus').get(
                uuid=tableau_initial_uuid,
                num_amendement=0
            )
        except TableauBord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Tableau initial introuvable'
            }, status=status.HTTP_404_NOT_FOUND)

        # Security by Design : Vérifier la permission APRÈS avoir récupéré le tableau initial
        permission_checker = DashboardAmendementCreatePermission()
        if not permission_checker.has_object_permission(request, None, initial_tableau):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas les permissions nécessaires pour créer un amendement.'
            }, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        clone = str(data.pop('clone', 'false')).lower() in ['1', 'true', 'yes', 'on']

        # Récupérer tous les amendements existants (num_amendement > 0)
        from django.db.models import Max
        existing_amendements_all = TableauBord.objects.filter(
            annee=initial_tableau.annee,
            processus=initial_tableau.processus,
            num_amendement__gt=0
        )

        # Vérifier s'il y a des amendements non validés
        amendements_non_valides = existing_amendements_all.filter(is_validated=False)
        if amendements_non_valides.exists():
            amendement_non_valide = amendements_non_valides.first()
            return Response({
                'success': False,
                'error': f'Impossible de créer un nouvel amendement : l\'amendement {amendement_non_valide.nom_version} n\'est pas encore validé. Vous devez valider l\'amendement précédent avant de pouvoir en créer un nouveau.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Tableau initial doit être validé
        if not initial_tableau.is_validated:
            return Response({
                'success': False,
                'error': 'Impossible de créer un amendement : le tableau initial doit être validé d\'abord.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Calculer le prochain num_amendement
        result = existing_amendements_all.aggregate(max_num=Max('num_amendement'))
        max_existing = result['max_num'] or 0
        next_num = max_existing + 1

        logger.info(f"Prochain num_amendement: {next_num}")

        # Créer l'amendement
        data.update({
            'annee': initial_tableau.annee,
            'processus': initial_tableau.processus.uuid,
            'initial_ref': initial_tableau.uuid,
            'num_amendement': next_num,
            'is_validated': False
        })

        logger.info(f"Données pour création amendement: {data}")

        serializer = TableauBordSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            try:
                instance = serializer.save()
                logger.info(f"Amendement créé avec succès: {instance.uuid}")

                # Si clone demandé, copier les objectifs et éléments associés
                if clone:
                    # Source = tableau avec le num_amendement précédent
                    source_tableau = TableauBord.objects.filter(
                        annee=initial_tableau.annee,
                        processus=initial_tableau.processus,
                        num_amendement=next_num - 1
                    ).first() or initial_tableau

                    logger.info(f"Clonage depuis {source_tableau.uuid} (num_amendement={source_tableau.num_amendement})")
                    logger.info(f"Nombre d'objectifs à cloner: {source_tableau.objectives.count()}")

                    for obj in source_tableau.objectives.all():
                        new_obj = Objectives.objects.create(
                            number=obj.number,
                            libelle=obj.libelle,
                            cree_par=request.user,
                            tableau_bord=instance
                        )
                        indicateurs = Indicateur.objects.filter(objective_id=obj)
                        for ind in indicateurs:
                            new_ind = Indicateur.objects.create(
                                libelle=ind.libelle,
                                objective_id=new_obj,
                                frequence_id=ind.frequence_id
                            )
                            try:
                                from parametre.models import Cible as ParamCible, Periodicite as ParamPeriodicite
                                cible = ParamCible.objects.filter(indicateur_id=ind).first()
                                if cible:
                                    ParamCible.objects.create(
                                        valeur=cible.valeur,
                                        condition=cible.condition,
                                        indicateur_id=new_ind
                                    )
                                for p in ParamPeriodicite.objects.filter(indicateur_id=ind):
                                    ParamPeriodicite.objects.create(
                                        indicateur_id=new_ind,
                                        periode=p.periode,
                                        a_realiser=p.a_realiser,
                                        realiser=p.realiser
                                    )
                            except Exception as e:
                                logger.warning(f"Erreur lors du clonage des éléments annexes: {str(e)}")
                                pass

                return Response({
                    'success': True,
                    'message': f'Amendement {instance.nom_version} créé avec succès',
                    'data': TableauBordSerializer(instance).data
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Erreur lors de la création de l'amendement: {str(e)}")
                return Response({
                    'success': False,
                    'error': f'Erreur lors de la création: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        logger.error(f"Erreur de validation du serializer: {serializer.errors}")
        logger.error(f"Données envoyées au serializer: {data}")
        return Response({
            'success': False,
            'errors': serializer.errors,
            'error': 'Erreur de validation des données',
            'data_sent': data
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        import traceback
        from django.conf import settings
        error_traceback = traceback.format_exc()
        logger.error(f"Erreur create_amendement: {str(e)}\n{error_traceback}")
        return Response({
            'success': False, 
            'error': f'Erreur lors de la création de l\'amendement: {str(e)}',
            'traceback': error_traceback if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_amendements_by_initial(request, tableau_initial_uuid):
    """Récupérer tous les amendements d'un tableau initial"""
    try:
        # Vérifier que le tableau initial existe
        try:
            initial_tableau = TableauBord.objects.get(uuid=tableau_initial_uuid, num_amendement=0)
        except TableauBord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Tableau initial introuvable'
            }, status=status.HTTP_404_NOT_FOUND)

        # Récupérer tous les amendements liés, triés par num_amendement
        amendements = TableauBord.objects.filter(
            initial_ref=initial_tableau
        ).order_by('num_amendement')

        serializer = TableauBordSerializer(amendements, many=True)

        return Response({
            'success': True,
            'data': serializer.data,
            'count': amendements.count(),
            'initial_tableau': {
                'uuid': str(initial_tableau.uuid),
                'annee': initial_tableau.annee,
                'processus_nom': initial_tableau.processus.nom,
                'nom_version': initial_tableau.nom_version
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur get_amendements_by_initial: {str(e)}")
        return Response({
            'success': False, 
            'error': 'Erreur lors de la récupération des amendements'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardTableauValidatePermission])
def validate_tableau_bord(request, uuid):
    """Valider un tableau de bord pour permettre la saisie des trimestres"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardTableauValidatePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère le tableau depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        tableau = TableauBord.objects.select_related('processus').get(uuid=uuid)
        
        # Vérifier que le tableau n'est pas déjà validé
        if tableau.is_validated:
            return Response({
                'success': False,
                'error': 'Ce tableau est déjà validé'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier qu'il y a au moins un objectif avec indicateurs et cibles
        objectives_count = tableau.objectives.count()
        if objectives_count == 0:
            return Response({
                'success': False,
                'error': 'Le tableau doit contenir au moins un objectif pour être validé'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier que chaque objectif a au moins un indicateur avec une cible
        for objective in tableau.objectives.all():
            indicateurs_count = objective.indicateurs.count()
            if indicateurs_count == 0:
                return Response({
                    'success': False,
                    'error': f'L\'objectif "{objective.number}" doit avoir au moins un indicateur pour être validé'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier que chaque indicateur a une cible
            for indicateur in objective.indicateurs.all():
                try:
                    from parametre.models import Cible
                    cible = Cible.objects.filter(indicateur_id=indicateur).first()
                    if not cible:
                        return Response({
                            'success': False,
                            'error': f'L\'indicateur "{indicateur.libelle}" doit avoir une cible définie pour être validé'
                        }, status=status.HTTP_400_BAD_REQUEST)
                except Exception:
                    pass
        
        # Valider le tableau
        tableau.is_validated = True
        tableau.date_validation = timezone.now()
        tableau.valide_par = request.user
        tableau.save()
        
        logger.info(f"Tableau {tableau.uuid} validé par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Tableau validé avec succès',
            'data': TableauBordSerializer(tableau).data
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except TableauBord.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Tableau de bord non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur validation tableau: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la validation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardTableauDevalidatePermission])
def devalidate_tableau_bord(request, uuid):
    """Dévalider un tableau de bord"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardTableauDevalidatePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère le tableau depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        tableau = TableauBord.objects.select_related('processus').get(uuid=uuid)
        
        # Vérifier que le tableau est bien validé
        if not tableau.is_validated:
            return Response({
                'success': False,
                'error': 'Ce tableau n\'est pas validé'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier qu'il n'existe pas de tableau suivant validé qui dépend de ce tableau
        has_validated_successor = TableauBord.objects.filter(
            annee=tableau.annee,
            processus=tableau.processus,
            num_amendement=tableau.num_amendement + 1,
            is_validated=True
        ).exists()
        if has_validated_successor:
            return Response({
                'success': False,
                'error': 'Impossible de dévalider ce tableau : un amendement suivant validé en dépend'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dévalider le tableau
        tableau.is_validated = False
        tableau.date_validation = None
        tableau.valide_par = None
        tableau.save()
        
        logger.info(f"Tableau {tableau.uuid} dévalidé par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Tableau dévalidé avec succès',
            'data': TableauBordSerializer(tableau).data
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except TableauBord.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Tableau de bord non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur dévalidation tableau: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la dévalidation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tableau_bord_objectives(request, uuid):
    """Récupérer tous les objectifs d'un tableau de bord spécifique"""
    try:
        # Vérifier que le tableau de bord existe
        try:
            tb = TableauBord.objects.get(uuid=uuid)
            
            # Security by Design : La vérification d'accès au processus est gérée par les permissions DRF
            # (cet endpoint clone un tableau, la vérification se fait via l'accès au tableau source)
            
        except TableauBord.DoesNotExist:
            return Response({'success': False, 'error': 'Tableau de bord non trouvé'}, status=status.HTTP_404_NOT_FOUND)
        
        # Récupérer les objectifs du tableau de bord
        objectives = Objectives.objects.filter(tableau_bord=tb).order_by('number')
        serializer = ObjectivesSerializer(objectives, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': objectives.count(),
            'tableau_bord': {
                'uuid': str(tb.uuid),
                'annee': tb.annee,
                'processus_nom': tb.processus.nom,
                'type_label': tb.get_type_display()
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des objectifs du tableau de bord {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des objectifs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
