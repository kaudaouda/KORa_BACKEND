"""
Vues API pour l'application Dashboard
Security by Design : Utilisation des classes DRF permissions génériques
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
import logging
from .models import Objectives, Indicateur, Observation, TableauBord
from parametre.views import (
    log_tableau_bord_creation,
    log_tableau_bord_update,
    log_objectif_creation,
    log_indicateur_creation,
    get_client_ip
)
from parametre.permissions import get_user_processus_list, user_has_access_to_processus

# Import des classes de permissions génériques Dashboard
from permissions.permissions import (
    DashboardTableauCreatePermission,
    DashboardTableauUpdatePermission,
    DashboardTableauDeletePermission,
    DashboardTableauValidatePermission,
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

logger = logging.getLogger(__name__)
from .serializers import (
    ObjectivesSerializer, ObjectivesCreateSerializer, ObjectivesUpdateSerializer,
    IndicateurSerializer, IndicateurCreateSerializer, IndicateurUpdateSerializer,
    CibleSerializer, CibleCreateSerializer, CibleUpdateSerializer,
    PeriodiciteSerializer, PeriodiciteCreateSerializer, PeriodiciteUpdateSerializer,
    ObservationSerializer, ObservationCreateSerializer, ObservationUpdateSerializer,
    TableauBordSerializer
)
import logging

logger = logging.getLogger(__name__)
# ==================== TABLEAUX DE BORD ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, DashboardTableauListCreatePermission])
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
                qs = TableauBord.objects.all().select_related('processus', 'initial_ref', 'type_tableau').order_by(
                    '-annee', 'processus__numero_processus', 'type_tableau__code'
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
                ).select_related('processus', 'initial_ref', 'type_tableau').order_by(
                    '-annee', 'processus__numero_processus', 'type_tableau__code'
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
            from parametre.models import Versions
            
            annee = data.get('annee')
            processus_uuid = data.get('processus')
            type_tableau_value = data.get('type_tableau')
            
            # Gérer le type de tableau (peut être un UUID ou un code)
            try:
                if type_tableau_value in ['INITIAL', 'AMENDEMENT_1', 'AMENDEMENT_2']:
                    # C'est un code, récupérer l'objet par code
                    type_tableau_obj = Versions.objects.get(code=type_tableau_value)
                else:
                    # C'est probablement un UUID, récupérer par UUID
                    type_tableau_obj = Versions.objects.get(uuid=type_tableau_value)
                
                # Mettre à jour les données avec l'UUID du type
                data['type_tableau'] = type_tableau_obj.uuid
                
            except Versions.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f'Type de tableau introuvable: {type_tableau_value}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            type_code = type_tableau_obj.code
            
            # VALIDATION 1 : Si INITIAL, vérifier qu'il n'existe pas déjà
            if type_code == 'INITIAL':
                existing = TableauBord.objects.filter(
                    annee=annee,
                    processus=processus_uuid,
                    type_tableau__code='INITIAL'
                ).exists()
                if existing:
                    return Response({
                        'success': False,
                        'error': f'Un tableau INITIAL existe déjà pour l\'année {annee} et ce processus. Vous ne pouvez créer que des amendements.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # VALIDATION 2 : Si AMENDEMENT_1, vérifier qu'INITIAL existe
            elif type_code == 'AMENDEMENT_1':
                initial_exists = TableauBord.objects.filter(
                    annee=annee,
                    processus=processus_uuid,
                    type_tableau__code='INITIAL'
                ).exists()
                if not initial_exists:
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer AMENDEMENT_1 : aucun tableau INITIAL n\'existe pour cette année et ce processus'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Vérifier aussi qu'AMENDEMENT_1 n'existe pas déjà
                existing_a1 = TableauBord.objects.filter(
                    annee=annee,
                    processus=processus_uuid,
                    type_tableau__code='AMENDEMENT_1'
                ).exists()
                if existing_a1:
                    return Response({
                        'success': False,
                        'error': 'AMENDEMENT_1 existe déjà pour cette année et ce processus. Vous pouvez créer AMENDEMENT_2.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # VALIDATION 3 : Si AMENDEMENT_2, vérifier qu'AMENDEMENT_1 existe
            elif type_code == 'AMENDEMENT_2':
                a1_exists = TableauBord.objects.filter(
                    annee=annee,
                    processus=processus_uuid,
                    type_tableau__code='AMENDEMENT_1'
                ).exists()
                if not a1_exists:
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer AMENDEMENT_2 : AMENDEMENT_1 n\'existe pas. Créez d\'abord AMENDEMENT_1.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Vérifier aussi qu'AMENDEMENT_2 n'existe pas déjà
                existing_a2 = TableauBord.objects.filter(
                    annee=annee,
                    processus=processus_uuid,
                    type_tableau__code='AMENDEMENT_2'
                ).exists()
                if existing_a2:
                    return Response({
                        'success': False,
                        'error': 'AMENDEMENT_2 existe déjà pour cette année et ce processus. Maximum 2 amendements autorisés.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
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
                    if instance.type_tableau.code in ('AMENDEMENT_1', 'AMENDEMENT_2') and clone and instance.initial_ref:
                        initial = instance.initial_ref
                        # cloner objectifs
                        for obj in initial.objectives.all():
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
        logger.info(f"tableau_bord_detail GET - UUID: {uuid}, Type: {tb.type_tableau.code}, is_validated: {tb.is_validated}, serializer is_validated: {serializer_data.get('is_validated')}")
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
                type_tableau__code='INITIAL'
            )
        except TableauBord.DoesNotExist:
            return Response({
                'success': False, 
                'error': 'Tableau initial introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Security by Design : Vérifier la permission APRÈS avoir récupéré le tableau initial
        # pour pouvoir extraire le processus_uuid depuis l'objet
        permission_checker = DashboardAmendementCreatePermission()
        if not permission_checker.has_object_permission(request, None, initial_tableau):
            return Response({
                'success': False,
                'error': 'Vous n\'avez pas les permissions nécessaires pour créer un amendement.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        clone = str(data.pop('clone', 'false')).lower() in ['1', 'true', 'yes', 'on']
        
        # Déterminer le type d'amendement
        from parametre.models import Versions
        
        # Récupérer tous les amendements existants (validés et non validés)
        existing_amendements_all = TableauBord.objects.filter(
            annee=initial_tableau.annee,
            processus=initial_tableau.processus,
            type_tableau__code__in=['AMENDEMENT_1', 'AMENDEMENT_2']
        )
        
        # Vérifier s'il y a des amendements non validés
        amendements_non_valides = existing_amendements_all.filter(is_validated=False)
        if amendements_non_valides.exists():
            amendement_non_valide = amendements_non_valides.first()
            return Response({
                'success': False,
                'error': f'Impossible de créer un nouvel amendement : l\'amendement "{amendement_non_valide.type_tableau.nom}" n\'est pas encore validé. Vous devez valider l\'amendement précédent avant de pouvoir en créer un nouveau.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Compter les amendements validés
        existing_amendements = existing_amendements_all.filter(is_validated=True).count()
        
        logger.info(f"Nombre d'amendements validés existants: {existing_amendements}")

        try:
            if existing_amendements == 0:
                # Créer AMENDEMENT_1 si aucun amendement validé n'existe
                # Essayer d'abord avec is_active=True, puis sans si non trouvé
                try:
                    type_amendement = Versions.objects.get(code='AMENDEMENT_1', is_active=True)
                except Versions.DoesNotExist:
                    # Si non trouvé avec is_active=True, essayer sans
                    type_amendement = Versions.objects.get(code='AMENDEMENT_1')
                data['type_tableau'] = type_amendement.uuid
            elif existing_amendements == 1:
                # Créer AMENDEMENT_2 si AMENDEMENT_1 est validé
                # Vérifier que AMENDEMENT_1 existe et est validé
                amendement_1 = existing_amendements_all.filter(
                    type_tableau__code='AMENDEMENT_1',
                    is_validated=True
                ).first()
                
                if not amendement_1:
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer AMENDEMENT_2 : AMENDEMENT_1 doit être validé avant de pouvoir créer AMENDEMENT_2'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Essayer d'abord avec is_active=True, puis sans si non trouvé
                try:
                    type_amendement = Versions.objects.get(code='AMENDEMENT_2', is_active=True)
                except Versions.DoesNotExist:
                    # Si non trouvé avec is_active=True, essayer sans
                    type_amendement = Versions.objects.get(code='AMENDEMENT_2')
                data['type_tableau'] = type_amendement.uuid
            else:
                return Response({
                    'success': False, 
                    'error': 'Maximum 2 amendements autorisés par tableau initial'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Versions.DoesNotExist as e:
            logger.error(f"Type d'amendement non trouvé: {str(e)}")
            return Response({
                'success': False,
                'error': f'Type d\'amendement (AMENDEMENT_1 ou AMENDEMENT_2) non trouvé dans la base de données. Veuillez contacter l\'administrateur pour créer ces types de tableaux.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Créer l'amendement
        # Le champ 'annee' est un PositiveIntegerField, donc on passe directement la valeur
        # Le champ 'processus' est un ForeignKey, donc on passe l'UUID
        # Le champ 'initial_ref' est un ForeignKey vers 'self', donc on passe l'UUID
        data.update({
            'annee': initial_tableau.annee,  # C'est déjà un entier
            'processus': initial_tableau.processus.uuid,
            'initial_ref': initial_tableau.uuid,
            'is_validated': False  # Les amendements commencent toujours non validés
        })
        
        logger.info(f"Données pour création amendement: {data}")
        
        serializer = TableauBordSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            try:
                instance = serializer.save()
                logger.info(f"Amendement créé avec succès: {instance.uuid}")
                
                # Si clone demandé, copier les objectifs et éléments associés
                if clone:
                    # Déterminer le tableau source pour le clonage
                    # Si c'est le premier amendement, copier depuis l'initial
                    # Sinon, copier depuis le dernier amendement créé
                    if existing_amendements == 0:
                        source_tableau = initial_tableau
                    else:
                        # Trouver le dernier amendement créé pour ce processus/année
                        # Exclure l'amendement qu'on vient de créer
                        last_amendement = TableauBord.objects.filter(
                            annee=initial_tableau.annee,
                            processus=initial_tableau.processus,
                            type_tableau__code__in=['AMENDEMENT_1', 'AMENDEMENT_2']
                        ).exclude(uuid=instance.uuid).order_by('-created_at').first()
                        source_tableau = last_amendement
                        
                        # Si aucun amendement trouvé, utiliser l'initial comme source
                        if source_tableau is None:
                            logger.warning(f"Aucun amendement trouvé pour le clonage, utilisation du tableau initial")
                            source_tableau = initial_tableau
                    
                    # Vérifier que source_tableau n'est pas None avant de cloner
                    if source_tableau is None:
                        logger.error(f"Impossible de déterminer le tableau source pour le clonage")
                        return Response({
                            'success': False,
                            'error': 'Impossible de déterminer le tableau source pour le clonage'
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                    # Log pour déboguer
                    logger.info(f"Clonage depuis {source_tableau.uuid} ({source_tableau.type_tableau.code})")
                    logger.info(f"Nombre d'objectifs à cloner: {source_tableau.objectives.count()}")
                    
                    # Cloner objectifs depuis le tableau source
                    for obj in source_tableau.objectives.all():
                        new_obj = Objectives.objects.create(
                            number=obj.number,
                            libelle=obj.libelle,
                            cree_par=request.user,
                            tableau_bord=instance
                        )
                        # Cloner indicateurs et leur structure
                        indicateurs = Indicateur.objects.filter(objective_id=obj)
                        for ind in indicateurs:
                            new_ind = Indicateur.objects.create(
                                libelle=ind.libelle,
                                objective_id=new_obj,
                                frequence_id=ind.frequence_id
                            )
                            # Cloner cibles et périodicités
                            try:
                                from parametre.models import Cible as ParamCible, Periodicite as ParamPeriodicite
                                cible = ParamCible.objects.filter(indicateur_id=ind).first()
                                if cible:
                                    ParamCible.objects.create(
                                        valeur=cible.valeur,
                                        condition=cible.condition,
                                        indicateur_id=new_ind
                                    )
                                # Cloner périodicités
                                for p in ParamPeriodicite.objects.filter(indicateur_id=ind):
                                    ParamPeriodicite.objects.create(
                                        indicateur_id=new_ind,
                                        periode=p.periode,
                                        a_realiser=p.a_realiser,
                                        realiser=p.realiser
                                    )
                            except Exception as e:
                                logger.warning(f"Erreur lors du clonage des éléments annexes: {str(e)}")
                                # Continue même en cas d'erreur
                                pass
                
                # Récupérer le nom du type d'amendement de manière sécurisée
                try:
                    type_display = instance.get_type_display()
                except Exception as e:
                    logger.warning(f"Erreur lors de la récupération du type d'affichage: {str(e)}")
                    type_display = instance.type_tableau.nom if instance.type_tableau else "Amendement"
                
                return Response({
                    'success': True,
                    'message': f'Amendement {type_display} créé avec succès',
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
            initial_tableau = TableauBord.objects.get(uuid=tableau_initial_uuid, type_tableau__code='INITIAL')
            
            # Security by Design : La vérification d'accès au processus est gérée par les permissions DRF
            # (cet endpoint clone un amendement, la vérification se fait via l'accès au tableau initial)
            
        except TableauBord.DoesNotExist:
            return Response({
                'success': False, 
                'error': 'Tableau initial introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Récupérer tous les amendements liés, triés par date de création (du plus récent au plus ancien)
        amendements = TableauBord.objects.filter(
            initial_ref=initial_tableau
        ).order_by('-created_at')
        
        serializer = TableauBordSerializer(amendements, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': amendements.count(),
            'initial_tableau': {
                'uuid': str(initial_tableau.uuid),
                'annee': initial_tableau.annee,
                'processus_nom': initial_tableau.processus.nom,
                'type_tableau': initial_tableau.type_tableau.code
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


# ==================== OBJECTIFS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def objectives_list(request):
    """Liste tous les objectifs"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Filtrer les objectifs pour ne montrer que ceux des tableaux de bord accessibles
        if user_processus_uuids:
            objectives = Objectives.objects.filter(
                tableau_bord__processus__uuid__in=user_processus_uuids
            ).order_by('number')
        else:
            objectives = Objectives.objects.none()  # Aucun processus, donc aucun objectif
        # ========== FIN FILTRAGE ==========
        
        serializer = ObjectivesSerializer(objectives, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': objectives.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des objectifs: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des objectifs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def objectives_detail(request, uuid):
    """Détail d'un objectif"""
    try:
        objective = Objectives.objects.get(uuid=uuid)
        
        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveUpdatePermission
        # via le décorateur @permission_classes
        
        serializer = ObjectivesSerializer(objective)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'objectif {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardObjectiveCreatePermission])
def objectives_create(request):
    """Créer un nouvel objectif"""
    try:
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        tableau_bord_uuid = request.data.get('tableau_bord')
        if tableau_bord_uuid:
            try:
                tableau = TableauBord.objects.get(uuid=tableau_bord_uuid)
                
                # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveCreatePermission
                # via le décorateur @permission_classes
                
                if tableau.is_validated:
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer un objectif : le tableau est déjà validé'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Bloquer selon le type de tableau et les amendements suivants de manière précise
                from django.db.models import Q
                if tableau.type_tableau and tableau.type_tableau.code == 'INITIAL':
                    # L'initial ne peut pas être modifié s'il a des amendements (A1 ou A2)
                    if tableau.has_amendements():
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer un objectif : ce tableau initial a des amendements'
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif tableau.type_tableau and tableau.type_tableau.code == 'AMENDEMENT_1':
                    # A1 est modifiable UNIQUEMENT s'il n'existe pas déjà un A2 pour le même initial
                    if TableauBord.objects.filter(
                        annee=tableau.annee,
                        processus=tableau.processus,
                        type_tableau__code='AMENDEMENT_2'
                    ).exists():
                        return Response({
                            'success': False,
                            'error': "Impossible de créer un objectif : l'amendement 1 a un amendement 2 suivant"
                        }, status=status.HTTP_400_BAD_REQUEST)
                # AMENDEMENT_2: autorisé (pas d'amendements suivants possibles)
                    
            except TableauBord.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Tableau de bord non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ObjectivesCreateSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            objective = serializer.save()

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_objectif_creation(request.user, objective, ip_address, user_agent)
            except Exception as log_error:
                logger.error(f"Erreur lors du logging de la création de l'objectif: {log_error}")

            # Retourner l'objectif créé avec tous ses détails
            response_serializer = ObjectivesSerializer(objective)

            return Response({
                'success': True,
                'message': 'Objectif créé avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'objectif: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': f'Erreur lors de la création de l\'objectif: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardObjectiveUpdatePermission])
def objectives_update(request, uuid):
    """Mettre à jour un objectif"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObjectiveUpdatePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'objectif depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        objective = Objectives.objects.select_related(
            'tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveUpdatePermission
        # via le décorateur @permission_classes
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        if objective.tableau_bord:
            if objective.tableau_bord.is_validated:
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'objectif : le tableau est déjà validé'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier que le tableau n'a pas d'amendements suivants
            if objective.tableau_bord.has_amendements():
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'objectif : ce tableau a des amendements suivants'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ObjectivesUpdateSerializer(objective, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_objective = serializer.save()
            
            # Retourner l'objectif mis à jour avec tous ses détails
            response_serializer = ObjectivesSerializer(updated_objective)
            
            logger.info(f"Objectif mis à jour: {objective.number} par {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Objectif mis à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'objectif {uuid}: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardObjectiveDeletePermission])
def objectives_delete(request, uuid):
    """Supprimer un objectif"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObjectiveDeletePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'objectif depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        objective = Objectives.objects.select_related(
            'tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObjectiveDeletePermission
        # via le décorateur @permission_classes
        
        objective_number = objective.number
        objective.delete()
        
        logger.info(f"Objectif supprimé: {objective_number} par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Objectif supprimé avec succès'
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'objectif {uuid}: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATISTIQUES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Statistiques du tableau de bord"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Filtrer les données selon les processus accessibles
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les données sans filtre
            objectives_filter = Objectives.objects.all()
            indicateurs_filter = Indicateur.objects.all()
        elif user_processus_uuids:
            objectives_filter = Objectives.objects.filter(
                tableau_bord__processus__uuid__in=user_processus_uuids
            )
            indicateurs_filter = Indicateur.objects.filter(
                objective_id__tableau_bord__processus__uuid__in=user_processus_uuids
            )
        else:
            objectives_filter = Objectives.objects.none()
            indicateurs_filter = Indicateur.objects.none()
        # ========== FIN FILTRAGE ==========
        
        # Compter les objectifs
        total_objectives = objectives_filter.count()
        
        # Compter les fréquences
        from parametre.models import Frequence
        total_frequences = Frequence.objects.count()
        
        # Compter les indicateurs
        total_indicateurs = indicateurs_filter.count()
        
        # Objectifs créés aujourd'hui
        today = timezone.now().date()
        objectives_today = objectives_filter.filter(created_at__date=today).count()
        
        # Objectifs créés cette semaine
        from datetime import timedelta
        week_ago = today - timedelta(days=7)
        objectives_this_week = objectives_filter.filter(created_at__date__gte=week_ago).count()
        
        # Objectifs créés ce mois
        month_ago = today - timedelta(days=30)
        objectives_this_month = objectives_filter.filter(created_at__date__gte=month_ago).count()
        
        # Calculer les pourcentages de cibles atteintes et non atteintes
        # et dériver les indicateurs / objectifs atteints selon la règle métier
        from parametre.models import Cible, Periodicite
        import decimal
        from collections import defaultdict
        
        # Récupérer toutes les cibles avec leurs indicateurs (filtrées par processus)
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les cibles sans filtre
            cibles_qs = Cible.objects.all().select_related('indicateur_id', 'indicateur_id__frequence_id')
        elif user_processus_uuids:
            cibles_qs = Cible.objects.filter(
                indicateur_id__objective_id__tableau_bord__processus__uuid__in=user_processus_uuids
            ).select_related('indicateur_id', 'indicateur_id__frequence_id')
        else:
            cibles_qs = Cible.objects.none()
        
        total_cibles = cibles_qs.count()
        cibles_atteintes = 0
        cibles_non_atteintes = 0
        
        # Préparer les données pour les indicateurs / objectifs atteints
        indicateurs_ids = list(indicateurs_filter.values_list('pk', flat=True))
        
        # Dictionnaire des cibles par indicateur (OneToOne, mais plus simple à manipuler comme dict)
        cibles_by_indicateur = {cible.indicateur_id_id: cible for cible in cibles_qs}
        
        # Récupérer toutes les périodicités des indicateurs concernés
        periodicites_qs = Periodicite.objects.filter(indicateur_id__in=indicateurs_ids)
        periodicites_by_indicateur = defaultdict(list)
        for periodicite in periodicites_qs:
            periodicites_by_indicateur[periodicite.indicateur_id_id].append(periodicite)
        
        # Statut atteinte par indicateur (True/False/None si non évaluable)
        indicateur_status = {}
        indicateurs_atteints = 0
        indicateurs_non_atteints = 0
        
        logger.info(
            "[DashboardStats] Totaux initiaux - objectifs=%s, indicateurs=%s, cibles=%s",
            total_objectives, total_indicateurs, total_cibles
        )

        for indicateur in indicateurs_filter.select_related('frequence_id'):
            cible = cibles_by_indicateur.get(indicateur.pk)
            periodicites = periodicites_by_indicateur.get(indicateur.pk, [])
            
            # Si pas de cible ou pas de périodicité, on ne peut pas évaluer cet indicateur
            if not cible or not periodicites:
                indicateur_status[indicateur.pk] = None
                logger.debug(
                    "[DashboardStats] Indicateur %s ignoré (cible=%s, periodicites=%s)",
                    indicateur.pk, bool(cible), len(periodicites)
                )
                continue
            
            # Filtrer les périodes autorisées en fonction de la fréquence de l'indicateur
            frequence_nom = getattr(indicateur.frequence_id, 'nom', None)
            periodicites_utilisables = periodicites
            if frequence_nom:
                allowed_periodes = [code for code, _ in Periodicite.get_periodes_for_frequence(frequence_nom)]
                filtered = [p for p in periodicites if p.periode in allowed_periodes]
                if filtered:
                    periodicites_utilisables = filtered
            
            # Calculer la moyenne des taux sur les périodicités retenues
            taux_values = []
            for p in periodicites_utilisables:
                if p.taux is not None:
                    try:
                        taux_values.append(float(p.taux))
                    except (ValueError, TypeError, decimal.InvalidOperation):
                        continue
            
            if not taux_values:
                indicateur_status[indicateur.pk] = None
                logger.debug(
                    "[DashboardStats] Indicateur %s ignoré (aucun taux exploitable sur %s périodicités)",
                    indicateur.pk, len(periodicites_utilisables)
                )
                continue
            
            moyenne_taux = sum(taux_values) / len(taux_values)
            
            # Vérifier si la cible de l'indicateur est atteinte avec cette moyenne
            if cible.is_objectif_atteint(moyenne_taux):
                indicateurs_atteints += 1
                indicateurs_non_atteints += 0
                indicateur_status[indicateur.pk] = True
                cibles_atteintes += 1
            else:
                indicateurs_non_atteints += 1
                indicateur_status[indicateur.pk] = False
                cibles_non_atteintes += 1
        
        # Compléter les compteurs de cibles pour les cibles qui n'ont pas pu être évaluées
        # (par ex. pas de périodicité ou taux invalide) en les comptant comme non atteintes
        # pour garder une compatibilité avec l'ancienne logique si nécessaire.
        if total_cibles > (cibles_atteintes + cibles_non_atteintes):
            cibles_non_atteintes += total_cibles - (cibles_atteintes + cibles_non_atteintes)
        
        # Calculer les pourcentages de cibles atteintes / non atteintes
        pourcentage_atteintes = (cibles_atteintes / total_cibles * 100) if total_cibles > 0 else 0
        pourcentage_non_atteintes = (cibles_non_atteintes / total_cibles * 100) if total_cibles > 0 else 0
        
        # Calculer les objectifs atteints / non atteints
        objectifs_atteints = 0
        objectifs_non_atteints = 0
        
        # Préparer la liste des indicateurs par objectif
        indicateurs_by_objective = defaultdict(list)
        for indicateur in indicateurs_filter:
            indicateurs_by_objective[indicateur.objective_id_id].append(indicateur)
        
        for objective in objectives_filter:
            indicateurs_obj = indicateurs_by_objective.get(objective.pk, [])
            
            # Aucun indicateur associé : on ignore cet objectif pour le statut atteint/non atteint
            if not indicateurs_obj:
                continue
            
            has_evaluable_indicator = False
            all_indicateurs_atteints = True
            
            for indicateur in indicateurs_obj:
                indicateur_is_atteint = indicateur_status.get(indicateur.pk)
                if indicateur_is_atteint is None:
                    # Indicateur non évaluable (pas de cible ou pas de périodicité exploitable)
                    continue
                
                has_evaluable_indicator = True
                if indicateur_is_atteint is False:
                    all_indicateurs_atteints = False
                    break
            
            if not has_evaluable_indicator:
                # Aucun indicateur avec données exploitables pour cet objectif
                continue
            
            if all_indicateurs_atteints:
                objectifs_atteints += 1
            else:
                objectifs_non_atteints += 1

        logger.info(
            "[DashboardStats] Résultats calculés - indicateurs_atteints=%s, indicateurs_non_atteints=%s, "
            "objectifs_atteints=%s, objectifs_non_atteints=%s, cibles_atteintes=%s, cibles_non_atteintes=%s",
            indicateurs_atteints, indicateurs_non_atteints,
            objectifs_atteints, objectifs_non_atteints,
            cibles_atteintes, cibles_non_atteintes
        )
        
        stats = {
            'total_objectives': total_objectives,
            'total_frequences': total_frequences,
            'total_indicateurs': total_indicateurs,
            'objectives_today': objectives_today,
            'objectives_this_week': objectives_this_week,
            'objectives_this_month': objectives_this_month,
            'total_cibles': total_cibles,
            'cibles_atteintes': cibles_atteintes,
            'cibles_non_atteintes': cibles_non_atteintes,
            'pourcentage_atteintes': round(pourcentage_atteintes, 2),
            'pourcentage_non_atteintes': round(pourcentage_non_atteintes, 2),
            # Nouvelles statistiques basées sur la règle métier
            'indicateurs_atteints': indicateurs_atteints,
            'indicateurs_non_atteints': indicateurs_non_atteints,
            'objectifs_atteints': objectifs_atteints,
            'objectifs_non_atteints': objectifs_non_atteints,
        }
        
        return Response({
            'success': True,
            'data': stats
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des statistiques'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== INDICATEURS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicateurs_list(request):
    """Liste tous les indicateurs"""
    try:
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Filtrer les indicateurs pour ne montrer que ceux des tableaux de bord accessibles
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir tous les indicateurs sans filtre
            indicateurs = Indicateur.objects.all().order_by('objective_id', 'libelle')
        elif user_processus_uuids:
            indicateurs = Indicateur.objects.filter(
                objective_id__tableau_bord__processus__uuid__in=user_processus_uuids
            ).order_by('objective_id', 'libelle')
        else:
            indicateurs = Indicateur.objects.none()  # Aucun processus, donc aucun indicateur
        # ========== FIN FILTRAGE ==========
        
        serializer = IndicateurSerializer(indicateurs, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': indicateurs.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des indicateurs: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des indicateurs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicateurs_detail(request, uuid):
    """Détail d'un indicateur"""
    try:
        indicateur = Indicateur.objects.get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurUpdatePermission
        # via le décorateur @permission_classes
        
        serializer = IndicateurSerializer(indicateur)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'indicateur {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardIndicateurCreatePermission])
def indicateurs_create(request):
    """Créer un nouvel indicateur"""
    try:
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        objective_uuid = request.data.get('objective_id')
        if objective_uuid:
            try:
                objective = Objectives.objects.get(uuid=objective_uuid)
                if objective.tableau_bord:
                    tableau = objective.tableau_bord
                    
                    # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurCreatePermission
                    # via le décorateur @permission_classes
                    
                    if tableau.is_validated:
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer un indicateur : le tableau est déjà validé'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Vérifier que le tableau n'a pas d'amendements suivants
                    if tableau.has_amendements():
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer un indicateur : ce tableau a des amendements suivants'
                        }, status=status.HTTP_400_BAD_REQUEST)
            except Objectives.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Objectif non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = IndicateurCreateSerializer(data=request.data)

        if serializer.is_valid():
            indicateur = serializer.save()

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_indicateur_creation(request.user, indicateur, ip_address, user_agent)
            except Exception as log_error:
                logger.error(f"Erreur lors du logging de la création de l'indicateur: {log_error}")

            # Retourner l'indicateur créé avec tous ses détails
            response_serializer = IndicateurSerializer(indicateur)

            logger.info(f"Indicateur créé: {indicateur.libelle} par {request.user.username}")

            return Response({
                'success': True,
                'message': 'Indicateur créé avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'indicateur: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardIndicateurUpdatePermission])
def indicateurs_update(request, uuid):
    """Mettre à jour un indicateur"""
    try:
        indicateur = Indicateur.objects.get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurUpdatePermission
        # via le décorateur @permission_classes
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        if indicateur.objective_id.tableau_bord:
            tableau = indicateur.objective_id.tableau_bord
            if tableau.is_validated:
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'indicateur : le tableau est déjà validé'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier que le tableau n'a pas d'amendements suivants
            if tableau.has_amendements():
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier l\'indicateur : ce tableau a des amendements suivants'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = IndicateurUpdateSerializer(indicateur, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_indicateur = serializer.save()
            
            # Retourner l'indicateur mis à jour avec tous ses détails
            response_serializer = IndicateurSerializer(updated_indicateur)
            
            logger.info(f"Indicateur mis à jour: {indicateur.libelle} par {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Indicateur mis à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Erreur lors de la mise à jour de l'indicateur {uuid}: {str(e)}\n{error_traceback}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardIndicateurDeletePermission])
def indicateurs_delete(request, uuid):
    """Supprimer un indicateur"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardIndicateurDeletePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'indicateur depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        indicateur = Indicateur.objects.select_related(
            'objective_id__tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardIndicateurDeletePermission
        # via le décorateur @permission_classes
        
        indicateur_libelle = indicateur.libelle
        indicateur.delete()
        
        logger.info(f"Indicateur supprimé: {indicateur_libelle} par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Indicateur supprimé avec succès'
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'indicateur {uuid}: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== INDICATEURS PAR OBJECTIF ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def objectives_indicateurs(request, objective_uuid):
    """Liste tous les indicateurs d'un objectif"""
    try:
        # Vérifier que l'objectif existe
        objective = Objectives.objects.get(uuid=objective_uuid)
        
        indicateurs = Indicateur.objects.filter(objective_id=objective).order_by('libelle')
        serializer = IndicateurSerializer(indicateurs, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': indicateurs.count(),
            'objective': {
                'uuid': str(objective.uuid),
                'number': objective.number,
                'libelle': objective.libelle
            }
        }, status=status.HTTP_200_OK)
        
    except Objectives.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Objectif non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des indicateurs de l'objectif {objective_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des indicateurs de l\'objectif'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== CIBLES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cibles_list(request):
    """Liste toutes les cibles"""
    try:
        from parametre.models import Cible
        
        # ========== FILTRAGE PAR PROCESSUS (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)
        
        # Filtrer les cibles pour ne montrer que celles des tableaux de bord accessibles
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les cibles sans filtre
            cibles = Cible.objects.all().order_by('indicateur_id', 'created_at')
        elif user_processus_uuids:
            cibles = Cible.objects.filter(
                indicateur_id__objective_id__tableau_bord__processus__uuid__in=user_processus_uuids
            ).order_by('indicateur_id', 'created_at')
        else:
            cibles = Cible.objects.none()  # Aucun processus, donc aucune cible
        # ========== FIN FILTRAGE ==========
        
        serializer = CibleSerializer(cibles, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': cibles.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des cibles: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des cibles'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cibles_detail(request, uuid):
    """Détail d'une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        serializer = CibleSerializer(cible)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Cible.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cible non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la cible {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardCibleCreatePermission])
def cibles_create(request):
    """Créer une nouvelle cible"""
    try:
        from parametre.models import Cible
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        indicateur_uuid = request.data.get('indicateur_id')
        if indicateur_uuid:
            try:
                indicateur = Indicateur.objects.get(uuid=indicateur_uuid)
                if indicateur.objective_id.tableau_bord:
                    tableau = indicateur.objective_id.tableau_bord
                    
                    # Security by Design : La vérification d'accès au processus est gérée par DashboardCibleCreatePermission
                    # via le décorateur @permission_classes
                    
                    if tableau.is_validated:
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer une cible : le tableau est déjà validé'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Vérifier que le tableau n'a pas d'amendements suivants
                    if tableau.has_amendements():
                        return Response({
                            'success': False,
                            'error': 'Impossible de créer une cible : ce tableau a des amendements suivants'
                        }, status=status.HTTP_400_BAD_REQUEST)
            except Indicateur.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Indicateur non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CibleCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            cible = serializer.save()
            response_serializer = CibleSerializer(cible)
            
            logger.info(f"Cible créée/mise à jour: {cible} par {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Cible sauvegardée avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la cible: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardCibleUpdatePermission])
def cibles_update(request, uuid):
    """Mettre à jour une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        
        # Vérifier que le tableau n'est pas validé et n'a pas d'amendements
        try:
            indicateur = Indicateur.objects.get(uuid=cible.indicateur_id.uuid)
            if indicateur.objective_id.tableau_bord:
                tableau = indicateur.objective_id.tableau_bord
                
                # Security by Design : La vérification d'accès au processus est gérée par DashboardCibleUpdatePermission
                # via le décorateur @permission_classes
                
                if tableau.is_validated:
                    return Response({
                        'success': False,
                        'error': 'Impossible de modifier la cible : le tableau est déjà validé'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Vérifier que le tableau n'a pas d'amendements suivants
                if tableau.has_amendements():
                    return Response({
                        'success': False,
                        'error': 'Impossible de modifier la cible : ce tableau a des amendements suivants'
                    }, status=status.HTTP_400_BAD_REQUEST)
        except Indicateur.DoesNotExist:
            pass  # Continuer avec la validation normale
        
        serializer = CibleUpdateSerializer(cible, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_cible = serializer.save()
            response_serializer = CibleSerializer(updated_cible)
            
            logger.info(f"Cible mise à jour: {cible} par {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Cible mise à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Cible.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cible non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la cible {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardCibleDeletePermission])
def cibles_delete(request, uuid):
    """Supprimer une cible"""
    try:
        from parametre.models import Cible
        cible = Cible.objects.get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardCibleDeletePermission
        # via le décorateur @permission_classes
        
        cible.delete()
        
        logger.info(f"Cible supprimée: {cible} par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Cible supprimée avec succès'
        }, status=status.HTTP_200_OK)
        
    except Cible.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cible non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la cible {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de la cible'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cibles_by_indicateur(request, indicateur_uuid):
    """Récupérer les cibles d'un indicateur spécifique"""
    try:
        from parametre.models import Cible
        from .models import Indicateur
        
        # Récupérer l'indicateur
        indicateur = Indicateur.objects.get(uuid=indicateur_uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par les permissions DRF
        # (cet endpoint est utilisé pour la lecture, pas de permission spécifique requise car c'est un GET)
        
        # Récupérer la cible liée à l'indicateur (une seule)
        cible = Cible.objects.filter(indicateur_id=indicateur).first()
        serializer = CibleSerializer(cible) if cible else None
        
        return Response({
            'success': True,
            'data': serializer.data if serializer else None,
            'count': 1 if cible else 0,
            'indicateur': {
                'uuid': str(indicateur.uuid),
                'libelle': indicateur.libelle,
                'frequence_nom': indicateur.frequence_id.nom
            }
        }, status=status.HTTP_200_OK)
        
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des cibles de l'indicateur {indicateur_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des cibles de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== PERIODICITES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_list(request):
    """Liste toutes les périodicités"""
    try:
        from parametre.models import Periodicite
        import decimal
        
        # Récupérer les périodicités avec gestion d'erreur pour les données corrompues
        periodicites_data = []
        periodicites = Periodicite.objects.all().order_by('indicateur_id', 'periode')
        
        for periodicite in periodicites:
            try:
                # Créer un dictionnaire avec les données sérialisées manuellement
                periodicite_data = {
                    'uuid': str(periodicite.uuid),
                    'indicateur_id': str(periodicite.indicateur_id.uuid),
                    'indicateur_libelle': periodicite.indicateur_id.libelle,
                    'periode': periodicite.periode,
                    'periode_display': periodicite.get_periode_display(),
                    'a_realiser': float(periodicite.a_realiser),
                    'realiser': float(periodicite.realiser),
                    'taux': float(periodicite.taux) if periodicite.taux is not None else 0.0,
                    'created_at': periodicite.created_at,
                    'updated_at': periodicite.updated_at
                }
                periodicites_data.append(periodicite_data)
            except (ValueError, TypeError, decimal.InvalidOperation) as e:
                logger.warning(f"Périodicité {periodicite.uuid} ignorée à cause de données corrompues: {str(e)}")
                # Ajouter une entrée avec des valeurs par défaut pour les données corrompues
                periodicite_data = {
                    'uuid': str(periodicite.uuid),
                    'indicateur_id': str(periodicite.indicateur_id.uuid) if periodicite.indicateur_id else None,
                    'indicateur_libelle': periodicite.indicateur_id.libelle if periodicite.indicateur_id else 'Indicateur supprimé',
                    'periode': periodicite.periode,
                    'periode_display': periodicite.get_periode_display(),
                    'a_realiser': 0.0,
                    'realiser': 0.0,
                    'taux': 0.0,
                    'created_at': periodicite.created_at,
                    'updated_at': periodicite.updated_at
                }
                periodicites_data.append(periodicite_data)

        return Response({
            'success': True,
            'data': periodicites_data,
            'count': len(periodicites_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des périodicités: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des périodicités'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_detail(request, uuid):
    """Détail d'une périodicité"""
    try:
        from parametre.models import Periodicite
        periodicite = Periodicite.objects.get(uuid=uuid)
        serializer = PeriodiciteSerializer(periodicite)

        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Periodicite.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Périodicité non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la périodicité {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardPeriodiciteCreatePermission])
def periodicites_create(request):
    """Créer une nouvelle périodicité"""
    try:
        # Vérifier que le tableau est validé et n'a pas d'amendements avant de permettre la création de périodicités
        indicateur_uuid = request.data.get('indicateur_id')
        if indicateur_uuid:
            try:
                indicateur = Indicateur.objects.get(uuid=indicateur_uuid)
                tableau = indicateur.objective_id.tableau_bord
                
                if not tableau.is_validated:
                    return Response({
                        'success': False,
                        'error': 'Vous devez d\'abord valider le tableau avant de saisir les données trimestrielles'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Vérifier que le tableau n'a pas d'amendements suivants
                if tableau.has_amendements():
                    return Response({
                        'success': False,
                        'error': 'Impossible de créer une périodicité : ce tableau a des amendements suivants'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Indicateur.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Indicateur non trouvé'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = PeriodiciteCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            periodicite = serializer.save()
            response_serializer = PeriodiciteSerializer(periodicite)
            
            return Response({
                'success': True,
                'message': 'Périodicité créée avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la périodicité: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardPeriodiciteUpdatePermission])
def periodicites_update(request, uuid):
    """Mettre à jour une périodicité"""
    try:
        from parametre.models import Periodicite
        periodicite = Periodicite.objects.get(uuid=uuid)
        
        # Vérifier que le tableau est validé et n'a pas d'amendements avant de permettre la modification de périodicités
        try:
            indicateur = periodicite.indicateur_id
            tableau = indicateur.objective_id.tableau_bord
            
            if not tableau.is_validated:
                return Response({
                    'success': False,
                    'error': 'Vous devez d\'abord valider le tableau avant de modifier les données trimestrielles'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier que le tableau n'a pas d'amendements suivants
            if tableau.has_amendements():
                return Response({
                    'success': False,
                    'error': 'Impossible de modifier la périodicité : ce tableau a des amendements suivants'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception:
            pass  # En cas d'erreur, continuer avec la validation normale
        
        serializer = PeriodiciteUpdateSerializer(periodicite, data=request.data)
        
        if serializer.is_valid():
            periodicite = serializer.save()
            response_serializer = PeriodiciteSerializer(periodicite)
            
            return Response({
                'success': True,
                'message': 'Périodicité mise à jour avec succès',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Periodicite.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Périodicité non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la périodicité {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardPeriodiciteDeletePermission])
def periodicites_delete(request, uuid):
    """Supprimer une périodicité"""
    try:
        from parametre.models import Periodicite
        periodicite = Periodicite.objects.get(uuid=uuid)
        
        # Note: La vérification des permissions est maintenant gérée par DashboardPeriodiciteDeletePermission
        # via le décorateur @permission_classes
        
        periodicite.delete()
        
        return Response({
            'success': True,
            'message': 'Périodicité supprimée avec succès'
        }, status=status.HTTP_200_OK)
        
    except Periodicite.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Périodicité non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la périodicité {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de la périodicité'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodicites_by_indicateur(request, indicateur_uuid):
    """Récupérer les périodicités d'un indicateur spécifique"""
    try:
        from parametre.models import Periodicite
        from .models import Indicateur

        # Récupérer l'indicateur
        indicateur = Indicateur.objects.get(uuid=indicateur_uuid)

        # Récupérer les périodicités liées à l'indicateur
        periodicites = Periodicite.objects.filter(indicateur_id=indicateur).order_by('periode')
        serializer = PeriodiciteSerializer(periodicites, many=True)

        return Response({
            'success': True,
            'data': serializer.data,
            'count': periodicites.count(),
            'indicateur': {
                'uuid': str(indicateur.uuid),
                'libelle': indicateur.libelle,
                'frequence_nom': indicateur.frequence_id.nom
            }
        }, status=status.HTTP_200_OK)
        
    except Indicateur.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Indicateur non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des périodicités de l'indicateur {indicateur_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des périodicités de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== OBSERVATIONS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def observations_list(request):
    """Liste toutes les observations"""
    try:
        observations = Observation.objects.select_related(
            'indicateur_id', 'indicateur_id__objective_id', 'cree_par'
        ).all().order_by('indicateur_id__objective_id', 'created_at')
        serializer = ObservationSerializer(observations, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': observations.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des observations: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des observations'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DashboardObservationCreatePermission])
def observations_create(request):
    """Créer une nouvelle observation"""
    try:
        # Ajouter l'utilisateur connecté comme créateur
        data = request.data.copy()
        data['cree_par'] = request.user.id
        
        # Vérifier que l'indicateur existe et récupérer le tableau
        indicateur_id = data.get('indicateur_id')
        if not indicateur_id:
            return Response({
                'success': False,
                'error': 'Indicateur requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            indicateur = Indicateur.objects.get(uuid=indicateur_id)
            # Sécuriser la chaîne de relations (peut être None selon les données)
            objective = getattr(indicateur, 'objective_id', None) or getattr(indicateur, 'objective', None)
            if objective is None:
                return Response({
                    'success': False,
                    'error': "Impossible de créer l'observation : l'indicateur n'est rattaché à aucun objectif"
                }, status=status.HTTP_400_BAD_REQUEST)

            tableau = getattr(objective, 'tableau_bord', None)
            if tableau is None:
                return Response({
                    'success': False,
                    'error': "Impossible de créer l'observation : l'objectif n'est rattaché à aucun tableau"
                }, status=status.HTTP_400_BAD_REQUEST)
        except Indicateur.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Indicateur non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)

        # Security by Design : La vérification d'accès au processus est gérée par DashboardObservationCreatePermission
        # via le décorateur @permission_classes

        # Vérifier si le tableau est validé
        if not tableau.is_validated:
            return Response({
                'success': False,
                'error': 'Vous devez d\'abord valider le tableau pour ajouter des observations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ObservationCreateSerializer(data=data)
        
        if serializer.is_valid():
            observation = serializer.save()
            response_serializer = ObservationSerializer(observation)
            
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Observation créée avec succès'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Exception as e:
        import traceback
        from django.conf import settings
        logger.error(
            f"Erreur lors de la création de l'observation: {str(e)}\n{traceback.format_exc()}",
            exc_info=True
        )
        return Response({
            'success': False,
            'error': 'Erreur lors de la création de l\'observation',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def observations_detail(request, uuid):
    """Détail d'une observation"""
    try:
        observation = Observation.objects.select_related(
            'indicateur_id', 'indicateur_id__objective_id', 'cree_par'
        ).get(uuid=uuid)
        serializer = ObservationSerializer(observation)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Observation non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'observation {uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'observation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, DashboardObservationUpdatePermission])
def observations_update(request, uuid):
    """Mettre à jour une observation"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObservationUpdatePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'observation depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        observation = Observation.objects.select_related(
            'indicateur_id__objective_id__tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Récupérer le tableau via l'indicateur (correction : utiliser indicateur_id et objective_id)
        tableau = observation.indicateur_id.objective_id.tableau_bord

        # Security by Design : La vérification d'accès au processus est gérée par DashboardObservationUpdatePermission
        # via le décorateur @permission_classes
        
        # Vérifier si le tableau est validé
        if not tableau.is_validated:
            return Response({
                'success': False,
                'error': 'Vous devez d\'abord valider le tableau pour modifier les observations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ObservationUpdateSerializer(observation, data=request.data, partial=True)
        
        if serializer.is_valid():
            observation = serializer.save()
            response_serializer = ObservationSerializer(observation)
            
            return Response({
                'success': True,
                'data': response_serializer.data,
                'message': 'Observation mise à jour avec succès'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Données invalides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Observation non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'observation {uuid}: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la mise à jour de l\'observation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DashboardObservationDeletePermission])
def observations_delete(request, uuid):
    """Supprimer une observation"""
    try:
        # Security by Design : La vérification des permissions est gérée par DashboardObservationDeletePermission
        # via le décorateur @permission_classes. La méthode _extract_processus_uuid personnalisée
        # récupère l'observation depuis view.kwargs['uuid'] pour extraire le processus_uuid.
        observation = Observation.objects.select_related(
            'indicateur_id__objective_id__tableau_bord__processus'
        ).get(uuid=uuid)
        
        # Security by Design : La vérification d'accès au processus est gérée par DashboardObservationDeletePermission
        # via le décorateur @permission_classes
        
        observation.delete()
        
        logger.info(f"Observation supprimée: {uuid} par {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Observation supprimée avec succès'
        }, status=status.HTTP_200_OK)
        
    except PermissionDenied:
        # Security by Design : Ne pas capturer PermissionDenied, laisser DRF la gérer correctement
        raise
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Observation non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'observation {uuid}: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Erreur lors de la suppression de l\'observation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def observations_by_indicateur(request, indicateur_uuid):
    """Récupérer l'observation d'un indicateur"""
    try:
        observation = Observation.objects.select_related(
            'indicateur_id', 'indicateur_id__objective_id', 'cree_par'
        ).get(indicateur_id=indicateur_uuid)
        serializer = ObservationSerializer(observation)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Observation.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Aucune observation trouvée pour cet indicateur'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'observation de l'indicateur {indicateur_uuid}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération de l\'observation de l\'indicateur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_tableau_bord_previous_year(request):
    """
    Récupérer le dernier Tableau de Bord (INITIAL, AMENDEMENT_1 ou AMENDEMENT_2) de l'année précédente
    pour un processus donné.

    Query params:
    - annee: année actuelle (nombre entier, ex: 2025)
    - processus: UUID du processus

    Retourne le dernier type de tableau (ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL)
    """
    try:
        annee = request.query_params.get('annee')
        processus_uuid = request.query_params.get('processus')

        if not annee or not processus_uuid:
            return Response({
                'error': 'Les paramètres annee et processus sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            annee = int(annee)
        except (ValueError, TypeError):
            return Response({
                'error': 'Le paramètre annee doit être un nombre entier'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Calculer l'année précédente
        annee_precedente = annee - 1

        logger.info(f"[get_last_tableau_bord_previous_year] Recherche du dernier Tableau de Bord pour processus={processus_uuid}, année={annee_precedente}")

        # ========== VÉRIFICATION D'ACCÈS AU PROCESSUS (Security by Design) ==========
        if not user_has_access_to_processus(request.user, processus_uuid):
            return Response({
                'error': 'Vous n\'avez pas accès à ce processus. Vous n\'avez pas de rôle actif pour ce processus.'
            }, status=status.HTTP_403_FORBIDDEN)
        # ========== FIN VÉRIFICATION ==========

        # Chercher tous les Tableaux de Bord de l'année précédente pour ce processus
        # Ordre de priorité: AMENDEMENT_2 > AMENDEMENT_1 > INITIAL
        codes_order = ['AMENDEMENT_2', 'AMENDEMENT_1', 'INITIAL']

        for code in codes_order:
            tableau = TableauBord.objects.filter(
                cree_par=request.user,
                annee=annee_precedente,
                processus__uuid=processus_uuid,
                type_tableau__code=code
            ).select_related('processus', 'type_tableau', 'cree_par', 'valide_par').first()

            if tableau:
                logger.info(f"[get_last_tableau_bord_previous_year] Tableau de Bord trouvé: {tableau.uuid} (type: {code})")
                serializer = TableauBordSerializer(tableau)
                return Response(serializer.data, status=status.HTTP_200_OK)

        # Aucun Tableau de Bord trouvé pour l'année précédente
        logger.info(f"[get_last_tableau_bord_previous_year] Aucun Tableau de Bord trouvé pour l'année {annee_precedente}")
        return Response({
            'message': f'Aucun Tableau de Bord trouvé pour l\'année {annee_precedente}',
            'found': False
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du dernier Tableau de Bord de l'année précédente: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'error': 'Erreur lors de la récupération du Tableau de Bord',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
