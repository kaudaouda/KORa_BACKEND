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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Statistiques du tableau de bord"""
    try:
        # Paramètre de portée : 'tous' (défaut) ou 'dernier' (dernier tableau par processus)
        scope = request.query_params.get('scope', 'tous')

        # ========== FILTRAGE PAR PROCESSUS ET ANNÉE (Security by Design) ==========
        # Récupérer les processus accessibles par l'utilisateur
        user_processus_uuids = get_user_processus_list(request.user)

        # Filtre optionnel sur un seul processus (navigation multi-processus côté frontend)
        processus_uuid_filter = request.query_params.get('processus_uuid', None)
        # Vue globale = utilisateur normal sans filtre sur un processus précis
        is_global_view = (processus_uuid_filter is None and user_processus_uuids is not None)
        if processus_uuid_filter:
            if user_processus_uuids is None:
                # Super admin : autoriser le filtre unique
                user_processus_uuids = [processus_uuid_filter]
            elif str(processus_uuid_filter) in [str(u) for u in user_processus_uuids]:
                user_processus_uuids = [processus_uuid_filter]
            # Si l'utilisateur n'a pas accès au processus demandé, ignorer le filtre (sécurité)

        # Année en cours
        current_year = timezone.now().year

        # Déterminer l'année à utiliser pour les statistiques
        # Priorité : année en cours si des données existent, sinon année la plus récente avec des données
        if user_processus_uuids is None:
            # Super admin : vérifier d'abord l'année en cours
            year_to_use = current_year
            if not TableauBord.objects.filter(annee=current_year).exists():
                # Si pas de données pour l'année en cours, prendre l'année la plus récente
                latest_year = TableauBord.objects.aggregate(max_year=models.Max('annee'))['max_year']
                year_to_use = latest_year if latest_year else current_year
        elif user_processus_uuids:
            # Utilisateur normal : vérifier d'abord l'année en cours pour ses processus
            year_to_use = current_year
            if not TableauBord.objects.filter(
                processus__uuid__in=user_processus_uuids,
                annee=current_year
            ).exists():
                # Si pas de données pour l'année en cours, prendre l'année la plus récente pour ses processus
                latest_year = TableauBord.objects.filter(
                    processus__uuid__in=user_processus_uuids
                ).aggregate(max_year=models.Max('annee'))['max_year']
                year_to_use = latest_year if latest_year else current_year
        else:
            year_to_use = current_year

        # Filtrer les données selon les processus accessibles et l'année déterminée
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if user_processus_uuids is None:
            # Super admin : voir toutes les données de l'année déterminée sans filtre de processus
            objectives_filter = Objectives.objects.filter(tableau_bord__annee=year_to_use)
            indicateurs_filter = Indicateur.objects.filter(objective_id__tableau_bord__annee=year_to_use)
        elif user_processus_uuids:
            objectives_filter = Objectives.objects.filter(
                tableau_bord__processus__uuid__in=user_processus_uuids,
                tableau_bord__annee=year_to_use
            )
            indicateurs_filter = Indicateur.objects.filter(
                objective_id__tableau_bord__processus__uuid__in=user_processus_uuids,
                objective_id__tableau_bord__annee=year_to_use
            )
        else:
            objectives_filter = Objectives.objects.none()
            indicateurs_filter = Indicateur.objects.none()

        # ========== SCOPE : DERNIER TABLEAU PAR PROCESSUS ==========
        last_tableau_uuids = None
        if scope == 'dernier':
            from django.db.models import Max
            if user_processus_uuids is None:
                # Super admin : dernier tableau par processus sur l'année déterminée
                all_tb = TableauBord.objects.filter(annee=year_to_use)
                last_tableau_uuids = []
                for proc_uuid in all_tb.values_list('processus', flat=True).distinct():
                    max_num = all_tb.filter(processus=proc_uuid).aggregate(m=Max('num_amendement'))['m']
                    last_tb_obj = all_tb.filter(processus=proc_uuid, num_amendement=max_num).first()
                    if last_tb_obj:
                        last_tableau_uuids.append(last_tb_obj.uuid)
                objectives_filter = objectives_filter.filter(tableau_bord__uuid__in=last_tableau_uuids)
                indicateurs_filter = indicateurs_filter.filter(
                    objective_id__tableau_bord__uuid__in=last_tableau_uuids
                )
            elif is_global_view:
                # Vue globale : dernier tableau par processus toutes années confondues
                # (chaque processus peut avoir son tableau dans une année différente)
                all_tb = TableauBord.objects.filter(processus__uuid__in=user_processus_uuids)
                last_tableau_uuids = []
                for proc_uuid in user_processus_uuids:
                    proc_tb = all_tb.filter(processus__uuid=proc_uuid)
                    if not proc_tb.exists():
                        continue
                    max_yr = proc_tb.aggregate(m=Max('annee'))['m']
                    proc_tb_yr = proc_tb.filter(annee=max_yr)
                    max_num = proc_tb_yr.aggregate(m=Max('num_amendement'))['m']
                    last_tb_obj = proc_tb_yr.filter(num_amendement=max_num).first()
                    if last_tb_obj:
                        last_tableau_uuids.append(last_tb_obj.uuid)
                # Reconstruire les filtres sans contrainte d'année
                objectives_filter = Objectives.objects.filter(tableau_bord__uuid__in=last_tableau_uuids)
                indicateurs_filter = Indicateur.objects.filter(
                    objective_id__tableau_bord__uuid__in=last_tableau_uuids
                )
            elif user_processus_uuids:
                # Vue mono-processus : dernier tableau sur l'année déterminée
                all_tb = TableauBord.objects.filter(
                    processus__uuid__in=user_processus_uuids, annee=year_to_use
                )
                last_tableau_uuids = []
                for proc_uuid in all_tb.values_list('processus', flat=True).distinct():
                    max_num = all_tb.filter(processus=proc_uuid).aggregate(m=Max('num_amendement'))['m']
                    last_tb_obj = all_tb.filter(processus=proc_uuid, num_amendement=max_num).first()
                    if last_tb_obj:
                        last_tableau_uuids.append(last_tb_obj.uuid)
                objectives_filter = objectives_filter.filter(tableau_bord__uuid__in=last_tableau_uuids)
                indicateurs_filter = indicateurs_filter.filter(
                    objective_id__tableau_bord__uuid__in=last_tableau_uuids
                )
            else:
                last_tableau_uuids = []
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
        
        # Récupérer toutes les cibles avec leurs indicateurs (filtrées par processus et année déterminée)
        # Si user_processus_uuids est None, l'utilisateur est super admin (is_staff ET is_superuser)
        if is_global_view and last_tableau_uuids is not None:
            # Vue globale scope=dernier : cibles des derniers tableaux (toutes années)
            cibles_qs = Cible.objects.filter(
                indicateur_id__objective_id__tableau_bord__uuid__in=last_tableau_uuids
            ).select_related('indicateur_id', 'indicateur_id__frequence_id')
        elif user_processus_uuids is None:
            # Super admin : voir toutes les cibles de l'année déterminée sans filtre de processus
            cibles_qs = Cible.objects.filter(
                indicateur_id__objective_id__tableau_bord__annee=year_to_use
            ).select_related('indicateur_id', 'indicateur_id__frequence_id')
        elif user_processus_uuids:
            cibles_qs = Cible.objects.filter(
                indicateur_id__objective_id__tableau_bord__processus__uuid__in=user_processus_uuids,
                indicateur_id__objective_id__tableau_bord__annee=year_to_use
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
        
        # Récupérer toutes les périodicités des indicateurs concernés avec optimisation pour les preuves
        periodicites_qs = Periodicite.objects.filter(indicateur_id__in=indicateurs_ids).select_related('preuve').prefetch_related('preuve__medias')
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
        
        # ========== STATISTIQUES D'ANALYSE ==========
        # Filtrer les tableaux de bord selon les processus accessibles et l'année déterminée
        if is_global_view and last_tableau_uuids is not None:
            # Vue globale scope=dernier : derniers tableaux de chaque processus (toutes années)
            tableaux_bord_filter = TableauBord.objects.filter(uuid__in=last_tableau_uuids)
        elif user_processus_uuids is None:
            # Super admin : voir tous les tableaux de bord de l'année déterminée
            tableaux_bord_filter = TableauBord.objects.filter(annee=year_to_use)
        elif user_processus_uuids:
            # Filtrer par processus accessibles et année déterminée
            tableaux_bord_filter = TableauBord.objects.filter(
                processus__uuid__in=user_processus_uuids,
                annee=year_to_use
            )
        else:
            tableaux_bord_filter = TableauBord.objects.none()

        # Restreindre au dernier tableau par processus si scope='dernier' (hors vue globale déjà traitée)
        if scope == 'dernier' and last_tableau_uuids is not None and not is_global_view:
            tableaux_bord_filter = tableaux_bord_filter.filter(uuid__in=last_tableau_uuids)

        # Compter le nombre total d'analyses effectuées pour l'année déterminée
        if is_global_view and last_tableau_uuids is not None:
            # Vue globale : analyses sur les derniers tableaux de chaque processus
            total_analyses = AnalyseTableau.objects.filter(
                tableau_bord__uuid__in=last_tableau_uuids
            ).count()
        elif user_processus_uuids is None:
            total_analyses = AnalyseTableau.objects.filter(
                tableau_bord__annee=year_to_use
            ).count()
        elif user_processus_uuids:
            total_analyses = AnalyseTableau.objects.filter(
                tableau_bord__processus__uuid__in=user_processus_uuids,
                tableau_bord__annee=year_to_use
            ).count()
        else:
            total_analyses = 0
        
        # Compter le nombre de tableaux ayant une analyse
        # IMPORTANT: On doit compter le nombre de tableaux UNIQUES, pas le nombre d'AnalyseTableau
        # Si un tableau a plusieurs AnalyseTableau (ce qui ne devrait pas être possible avec OneToOneField),
        # on doit quand même le compter comme 1 tableau unique
        # Utiliser distinct() pour compter les tableaux uniques
        tableaux_avec_analyse = AnalyseTableau.objects.filter(
            tableau_bord__in=tableaux_bord_filter
        ).values('tableau_bord').distinct().count()
        
        # Compter le nombre total de tableaux (filtrés par processus)
        total_tableaux = tableaux_bord_filter.count()
        
        # Compter le nombre de tableaux sans analyse
        tableaux_sans_analyse = total_tableaux - tableaux_avec_analyse
        
        logger.info(
            "[DashboardStats] Statistiques d'analyse - total_analyses=%s, tableaux_avec_analyse=%s, "
            "tableaux_sans_analyse=%s, total_tableaux=%s",
            total_analyses, tableaux_avec_analyse, tableaux_sans_analyse, total_tableaux
        )
        # ========== FIN STATISTIQUES D'ANALYSE ==========
        
        stats = {
            'year_used': year_to_use,
            'is_current_year': year_to_use == current_year,
            'scope': scope,
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
            # Statistiques d'analyse
            'total_analyses': total_analyses,
            'tableaux_avec_analyse': tableaux_avec_analyse,
            'tableaux_sans_analyse': tableaux_sans_analyse,
        }
        
        return Response({
            'success': True,
            'data': stats
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur lors de la récupération des statistiques: %s", str(e))
        return Response({
            'success': False,
            'error': 'Erreur lors de la récupération des statistiques'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
