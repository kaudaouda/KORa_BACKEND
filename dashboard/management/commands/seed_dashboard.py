from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files import File
from datetime import date
import os

from parametre.models import (
    Processus, Frequence, Cible, Periodicite, Media, Preuve,
    EtatMiseEnOeuvre, Appreciation, Direction, SousDirection,
)
from dashboard.models import TableauBord, Objectives, Indicateur, Observation
from analyse_tableau.models import AnalyseTableau, AnalyseLigne, AnalyseAction

PREUVE_PDF_PATH = os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', '..', 'medias', 'preuve.pdf'
)

FREQUENCES = ['Trimestrielle', 'Semestrielle', 'Annuelle']

ETATS_MISE_EN_OEUVRE = [
    {'nom': 'Realisee',               'description': 'Action completement realisee'},
    {'nom': 'En cours',               'description': 'Action en cours de realisation'},
    {'nom': 'Partiellement realisee', 'description': 'Action realisee en partie'},
    {'nom': 'Non realisee',           'description': 'Action non encore entamee'},
    {'nom': 'Abandonnee',             'description': 'Action abandonnee'},
]

APPRECIATIONS = [
    {'nom': 'Satisfaisant',      'description': 'Resultat satisfaisant'},
    {'nom': 'Tres satisfaisant', 'description': 'Resultat tres satisfaisant'},
    {'nom': 'Insuffisant',       'description': 'Resultat insuffisant'},
    {'nom': 'A ameliorer',       'description': 'Des efforts supplementaires sont necessaires'},
]

# ---------------------------------------------------------------------------
# Analyses : objectifs atteints / non-atteints + actions correctives
# Couvre les tableaux Initial ET Amendements de chaque processus
# ---------------------------------------------------------------------------
ANALYSES_DATA = {
    'PRS-DAAF': [
        {
            'periode': 'T3',
            'objectif_non_atteint': "Taux d'execution du budget alloue insuffisant en T3 (84% vs cible 85%)",
            'cible': 'Taux >= 85%',
            'resultat': '84% — Ecart de 1 point du aux retards de marches publics',
            'causes': (
                'Retard dans la validation des marches de fournitures de bureau. '
                'Blocage administratif au niveau de la commission des marches.'
            ),
            'actions': [
                {
                    'action': 'Accelerer la procedure de passation des marches en cours',
                    'delai': date(2025, 10, 31),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 10, 15),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Tous les marches bloques ont ete valides avant fin octobre.',
                },
                {
                    'action': 'Mettre en place un tableau de bord de suivi des marches',
                    'delai': date(2025, 11, 30),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 11, 20),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Outil de suivi deploye et partage avec toutes les directions.',
                },
                {
                    'action': 'Former les responsables sur les procedures de passation des marches',
                    'delai': date(2025, 12, 15),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 12, 10),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Formation realisee pour 15 responsables.',
                },
            ],
        },
        {
            'periode': 'S1',
            'objectif_non_atteint': "Taux de realisation du plan de maintenance des equipements S1 (85% atteint — analyse de capitalisation)",
            'cible': 'Taux >= 80%',
            'resultat': '85% — Objectif depasse, analyse de capitalisation',
            'causes': (
                'Bonne planification et anticipation des besoins en maintenance. '
                'Equipe technique mobilisee et pieces de rechange disponibles.'
            ),
            'actions': [
                {
                    'action': 'Documenter les bonnes pratiques de maintenance pour replication',
                    'delai': date(2025, 8, 31),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 8, 25),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Guide de bonnes pratiques produit et distribue.',
                },
                {
                    'action': 'Etendre le programme de maintenance preventive a tous les equipements',
                    'delai': date(2025, 9, 30),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'A ameliorer',
                    'commentaire': 'Extension en cours, 60% des equipements couverts.',
                },
            ],
        },
    ],
    'PRS-SDARH': [
        {
            'periode': 'S2',
            'objectif_non_atteint': "Taux de postes pourvus en S2 (87.5% vs cible 85%) — Objectif atteint, analyse de performance",
            'cible': 'Taux >= 85%',
            'resultat': '87.5% — Objectif atteint',
            'causes': (
                'Effort particulier sur les recrutements urgents en S2. '
                'Collaboration renforcee avec les partenaires de formation.'
            ),
            'actions': [
                {
                    'action': 'Consolider le vivier de candidats pour les profils rares',
                    'delai': date(2025, 12, 31),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Base de donnees candidats en cours de constitution.',
                },
                {
                    'action': 'Renforcer les partenariats avec les ecoles de formation aeronautique',
                    'delai': date(2026, 3, 31),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'A ameliorer',
                    'commentaire': '3 partenariats en negociation avec des ecoles specialisees.',
                },
            ],
        },
        {
            'periode': 'T2',
            'objectif_non_atteint': "Taux d'absenteisme T2 proche de la limite (4% vs cible <= 5%)",
            'cible': 'Taux <= 5%',
            'resultat': '4% — Dans la cible, surveillance maintenue',
            'causes': (
                'Periode de conges scolaires et augmentation des conges annuels en T2. '
                'Quelques absences pour maladie enregistrees.'
            ),
            'actions': [
                {
                    'action': 'Mettre en place un programme de bien-etre au travail',
                    'delai': date(2025, 9, 30),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 9, 15),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Programme QVT lance avec 3 activites collectives.',
                },
                {
                    'action': 'Optimiser la gestion des conges pour eviter les pics d absence',
                    'delai': date(2025, 10, 15),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 10, 10),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Planning des conges restructure, resultat visible des T3.',
                },
            ],
        },
    ],
    'PRS-DSSC': [
        {
            'periode': 'S1',
            'objectif_non_atteint': "Taux de numerisation des dossiers de certification S1 insuffisant (65% vs cible 70%)",
            'cible': 'Taux >= 70%',
            'resultat': '65% — Retard de 5 points sur l objectif semestriel',
            'causes': (
                'Sous-effectif dans l equipe chargee de la numerisation. '
                'Panne du scanner principal pendant 3 semaines. '
                'Priorite donnee aux dossiers urgents de certification.'
            ),
            'actions': [
                {
                    'action': 'Acquerir un scanner de remplacement haute capacite',
                    'delai': date(2025, 8, 31),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 8, 20),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Nouveau scanner installe, capacite doublee.',
                },
                {
                    'action': 'Recruter deux agents contractuels pour la numerisation',
                    'delai': date(2025, 9, 15),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 9, 1),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Agents recrutes et operationnels, rattrapage en cours.',
                },
                {
                    'action': 'Definir un plan de numerisation prioritaire pour les dossiers en retard',
                    'delai': date(2025, 9, 30),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 9, 25),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Plan etabli, 80% atteint en S2 confirmant le rattrapage.',
                },
            ],
        },
        {
            'periode': 'A1',
            'objectif_non_atteint': "Taux de certification des inspecteurs 85% vs cible 80% — Objectif depasse, capitalisation",
            'cible': 'Taux >= 80%',
            'resultat': '85% — Objectif largement depasse',
            'causes': (
                'Programme de formation OACI additionnel mis en place en S1. '
                'Forte motivation des inspecteurs pour la certification internationale.'
            ),
            'actions': [
                {
                    'action': 'Planifier la certification des 15% d inspecteurs restants',
                    'delai': date(2026, 3, 31),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'A ameliorer',
                    'commentaire': 'Sessions de formation programmees pour Q1 2026.',
                },
                {
                    'action': 'Mettre en place un suivi individualise des certifications',
                    'delai': date(2025, 12, 31),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 12, 15),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Tableau de suivi individuel deploye pour chaque inspecteur.',
                },
            ],
        },
    ],
    'PRS-DSF': [
        {
            'periode': 'T3',
            'objectif_non_atteint': "Taux de disponibilite equipements T3 en dessous de la cible (97% vs 98%)",
            'cible': 'Taux >= 98%',
            'resultat': '97% — Panne VOR enregistree en semaine 32',
            'causes': (
                'Panne inattendue du VOR principal due a un composant electronique defaillant. '
                'Delai d approvisionnement de la piece de rechange plus long que prevu (72h vs 24h habituel).'
            ),
            'actions': [
                {
                    'action': 'Constituer un stock de pieces de rechange critiques pour les equipements VOR/ILS',
                    'delai': date(2025, 10, 31),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 10, 28),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Stock constitue pour 15 types de composants critiques.',
                },
                {
                    'action': 'Reviser le contrat de maintenance avec le fournisseur pour inclure SLA 24h',
                    'delai': date(2025, 11, 30),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'A ameliorer',
                    'commentaire': 'Negociation en cours avec le fournisseur principal.',
                },
                {
                    'action': 'Former une equipe d astreinte pour les pannes critiques',
                    'delai': date(2025, 12, 15),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 12, 5),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Equipe de 4 techniciens formes et en rotation d astreinte.',
                },
            ],
        },
        {
            'periode': 'T1',
            'objectif_non_atteint': "Taux maintenance preventive T1 depasse la cible (90% vs 85%) — Analyse de capitalisation",
            'cible': 'Taux >= 85%',
            'resultat': '90% — Objectif depasse en T1',
            'causes': (
                'Planification optimisee en debut d annee. '
                'Bonne disponibilite des techniciens en dehors des periodes de conges.'
            ),
            'actions': [
                {
                    'action': 'Documenter et standardiser la methode de planification T1 pour les autres trimestres',
                    'delai': date(2025, 6, 30),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 6, 20),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Guide de planification produit et partage avec les equipes.',
                },
            ],
        },
    ],
    'PRS-DSV': [
        {
            'periode': 'S1',
            'objectif_non_atteint': "Taux de realisation plan formation technique S1 (90% vs cible 80%) — Objectif depasse",
            'cible': 'Taux >= 80%',
            'resultat': '90% — Depassement significatif de l objectif',
            'causes': (
                'Programme de formation intensif mis en place grace au soutien du programme IACO. '
                'Forte implication de la direction dans le suivi des formations.'
            ),
            'actions': [
                {
                    'action': 'Maintenir le rythme de formation et etendre aux ingenieurs junior',
                    'delai': date(2025, 12, 31),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Programme etendu, 5 ingenieurs junior en cours de formation.',
                },
                {
                    'action': 'Solliciter un nouveau financement IACO pour 2026',
                    'delai': date(2025, 11, 30),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 11, 10),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Demande soumise et accord de principe obtenu.',
                },
            ],
        },
        {
            'periode': 'S2',
            'objectif_non_atteint': "Taux de mise en conformite apres inspection S2 (92% vs cible 85%) — Objectif atteint",
            'cible': 'Taux >= 85%',
            'resultat': '92% — Bon niveau de conformite en progression',
            'causes': (
                'Renforcement du suivi post-inspection. '
                'Compagnies aeriennes plus repondantes suite aux reunions de sensibilisation.'
            ),
            'actions': [
                {
                    'action': 'Poursuivre les reunions de sensibilisation avec les exploitants',
                    'delai': date(2025, 12, 31),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'Satisfaisant',
                    'commentaire': '2 reunions supplementaires programmees en Q4.',
                },
                {
                    'action': 'Mettre en place un systeme de relance automatique pour les non-conformites',
                    'delai': date(2025, 10, 31),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 10, 25),
                    'evaluation': 'Tres satisfaisant',
                    'commentaire': 'Systeme operationnel, 15 relances envoyees depuis le lancement.',
                },
            ],
        },
        {
            'periode': 'T4',
            'objectif_non_atteint': "Nombre de reunions de coordination T4 exactement atteint (2 vs cible 2) — Analyse de cloture annuelle",
            'cible': 'Nombre >= 2',
            'resultat': '2 reunions — Objectif exactement atteint',
            'causes': (
                'Planning serre en fin d annee. '
                'Certains partenaires OACI en periode de fermeture en decembre.'
            ),
            'actions': [
                {
                    'action': 'Planifier les reunions 2026 avec les partenaires des janvier',
                    'delai': date(2026, 1, 31),
                    'etat': 'En cours',
                    'date_realisation': None,
                    'evaluation': 'A ameliorer',
                    'commentaire': 'Calendrier previsionnel 2026 en cours de preparation.',
                },
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Données communes réutilisées dans plusieurs tableaux
# ---------------------------------------------------------------------------
OBJECTIFS_PAR_PROCESSUS = {
    'PRS-DAAF': [
        {
            'libelle': 'Assurer la gestion rigoureuse des ressources financieres',
            'indicateurs': [
                {
                    'libelle': "Taux d'execution du budget alloue",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 85, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 25, 'realiser': 22},
                        {'periode': 'T2', 'a_realiser': 25, 'realiser': 24},
                        {'periode': 'T3', 'a_realiser': 25, 'realiser': 21},
                        {'periode': 'T4', 'a_realiser': 25, 'realiser': 25},
                    ],
                    'observation': 'Execution conforme aux previsions sauf T3 impacte par des retards de marches.',
                },
                {
                    'libelle': 'Taux de mandatement des depenses dans les delais',
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 90, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 30, 'realiser': 28},
                        {'periode': 'T2', 'a_realiser': 30, 'realiser': 27},
                        {'periode': 'T3', 'a_realiser': 30, 'realiser': 29},
                        {'periode': 'T4', 'a_realiser': 30, 'realiser': 30},
                    ],
                    'observation': 'Amelioration progressive sur les 4 trimestres.',
                },
                {
                    'libelle': 'Nombre de rapports financiers produits dans les delais',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 2, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 1, 'realiser': 1},
                        {'periode': 'S2', 'a_realiser': 1, 'realiser': 1},
                    ],
                    'observation': 'Rapports produits dans les delais aux deux semestres.',
                },
            ],
        },
        {
            'libelle': 'Optimiser la gestion du patrimoine et de la logistique',
            'indicateurs': [
                {
                    'libelle': 'Taux de realisation du plan de maintenance des equipements',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 80, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 20, 'realiser': 17},
                        {'periode': 'S2', 'a_realiser': 20, 'realiser': 19},
                    ],
                    'observation': 'S1 affecte par manque de pieces de rechange. S2 en nette amelioration.',
                },
                {
                    'libelle': 'Taux de traitement des requetes logistiques',
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 95, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 40, 'realiser': 38},
                        {'periode': 'T2', 'a_realiser': 45, 'realiser': 44},
                        {'periode': 'T3', 'a_realiser': 42, 'realiser': 40},
                        {'periode': 'T4', 'a_realiser': 38, 'realiser': 38},
                    ],
                    'observation': 'Tres bon niveau de service maintenu sur toute l annee.',
                },
            ],
        },
        {
            'libelle': 'Garantir la conformite des procedures administratives',
            'indicateurs': [
                {
                    'libelle': 'Taux de conformite des actes administratifs',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 98, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 50, 'realiser': 49},
                        {'periode': 'S2', 'a_realiser': 55, 'realiser': 55},
                    ],
                    'observation': 'Quasi-conformite totale maintenue grace aux revisions procedurales.',
                },
                {
                    'libelle': 'Delai moyen de traitement des dossiers administratifs (jours)',
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 5, 'condition': '<='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 5, 'realiser': 4},
                        {'periode': 'T2', 'a_realiser': 5, 'realiser': 5},
                        {'periode': 'T3', 'a_realiser': 5, 'realiser': 4},
                        {'periode': 'T4', 'a_realiser': 5, 'realiser': 3},
                    ],
                    'observation': 'Delais tenus et en reduction sur T4 grace a la numerisation.',
                },
            ],
        },
        {
            'libelle': 'Developper et valoriser les competences du personnel',
            'indicateurs': [
                {
                    'libelle': 'Taux de realisation du plan de formation annuel',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 80, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 15, 'realiser': 13},
                        {'periode': 'S2', 'a_realiser': 15, 'realiser': 14},
                    ],
                    'observation': 'Quelques formations reportees en S1 pour contraintes budgetaires.',
                },
                {
                    'libelle': "Nombre d'agents formes sur les nouvelles procedures",
                    'frequence': 'Annuelle',
                    'cible': {'valeur': 30, 'condition': '>='},
                    'periodes': [
                        {'periode': 'A1', 'a_realiser': 30, 'realiser': 34},
                    ],
                    'observation': 'Objectif depasse grace au programme de formation intensif.',
                },
            ],
        },
    ],
    'PRS-SDARH': [
        {
            'libelle': 'Assurer une gestion efficiente des ressources humaines',
            'indicateurs': [
                {
                    'libelle': 'Taux de postes pourvus dans les delais reglementaires',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 85, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 10, 'realiser': 9},
                        {'periode': 'S2', 'a_realiser': 8, 'realiser': 7},
                    ],
                    'observation': 'Recrutements globalement dans les delais malgre la rarete de certains profils.',
                },
                {
                    'libelle': 'Taux de satisfaction du personnel (enquete annuelle)',
                    'frequence': 'Annuelle',
                    'cible': {'valeur': 70, 'condition': '>='},
                    'periodes': [
                        {'periode': 'A1', 'a_realiser': 100, 'realiser': 74},
                    ],
                    'observation': 'Score de 74% - satisfaction en hausse de 4 points vs annee precedente.',
                },
            ],
        },
        {
            'libelle': 'Renforcer la gestion previsionnelle des emplois et competences',
            'indicateurs': [
                {
                    'libelle': 'Taux de couverture du plan GPEC',
                    'frequence': 'Annuelle',
                    'cible': {'valeur': 75, 'condition': '>='},
                    'periodes': [
                        {'periode': 'A1', 'a_realiser': 100, 'realiser': 78},
                    ],
                    'observation': 'Plan GPEC bien avance, quelques fiches de poste en attente de validation.',
                },
                {
                    'libelle': 'Nombre de bilans de competences realises',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 5, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 5, 'realiser': 6},
                        {'periode': 'S2', 'a_realiser': 5, 'realiser': 5},
                    ],
                    'observation': 'Bilan positif sur les deux semestres.',
                },
            ],
        },
        {
            'libelle': 'Ameliorer le bien-etre et les conditions de travail',
            'indicateurs': [
                {
                    'libelle': 'Taux d absenteisme',
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 5, 'condition': '<='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 5, 'realiser': 3},
                        {'periode': 'T2', 'a_realiser': 5, 'realiser': 4},
                        {'periode': 'T3', 'a_realiser': 5, 'realiser': 4},
                        {'periode': 'T4', 'a_realiser': 5, 'realiser': 2},
                    ],
                    'observation': 'Taux d absenteisme bien maitrise sur toute l annee.',
                },
                {
                    'libelle': 'Nombre de sessions de sensibilisation QVT organisees',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 2, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 2, 'realiser': 2},
                        {'periode': 'S2', 'a_realiser': 2, 'realiser': 3},
                    ],
                    'observation': 'Session supplementaire organisee en S2 suite aux resultats de l enquete.',
                },
            ],
        },
        {
            'libelle': 'Assurer la conformite juridique et reglementaire RH',
            'indicateurs': [
                {
                    'libelle': 'Taux de mise a jour des dossiers administratifs du personnel',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 95, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 100, 'realiser': 96},
                        {'periode': 'S2', 'a_realiser': 100, 'realiser': 98},
                    ],
                    'observation': 'Dossiers bien tenus, effort final sur les retraites en cours.',
                },
            ],
        },
    ],
    'PRS-DSSC': [
        {
            'libelle': 'Assurer la surveillance de la securite du systeme de certification',
            'indicateurs': [
                {
                    'libelle': 'Taux de dossiers de certification traites dans les delais',
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 95, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 50, 'realiser': 48},
                        {'periode': 'T2', 'a_realiser': 55, 'realiser': 54},
                        {'periode': 'T3', 'a_realiser': 60, 'realiser': 58},
                        {'periode': 'T4', 'a_realiser': 45, 'realiser': 45},
                    ],
                    'observation': 'Tres bon niveau sur toute l annee. T4 a 100%.',
                },
                {
                    'libelle': 'Nombre de controles de surveillance realises',
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 10, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 10, 'realiser': 11},
                        {'periode': 'T2', 'a_realiser': 10, 'realiser': 10},
                        {'periode': 'T3', 'a_realiser': 10, 'realiser': 12},
                        {'periode': 'T4', 'a_realiser': 10, 'realiser': 10},
                    ],
                    'observation': 'Objectif atteint ou depasse chaque trimestre.',
                },
                {
                    'libelle': 'Taux de resolution des ecarts de securite detectes',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 90, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 20, 'realiser': 19},
                        {'periode': 'S2', 'a_realiser': 18, 'realiser': 17},
                    ],
                    'observation': 'Ecarts resolus rapidement grace au suivi renforce.',
                },
            ],
        },
        {
            'libelle': 'Renforcer les capacites techniques de surveillance',
            'indicateurs': [
                {
                    'libelle': 'Nombre d inspecteurs formes sur les nouvelles normes OACI',
                    'frequence': 'Annuelle',
                    'cible': {'valeur': 8, 'condition': '>='},
                    'periodes': [
                        {'periode': 'A1', 'a_realiser': 8, 'realiser': 10},
                    ],
                    'observation': 'Formation elargie a 10 inspecteurs grace au soutien du programme OACI.',
                },
                {
                    'libelle': 'Taux de certification des inspecteurs selon les normes en vigueur',
                    'frequence': 'Annuelle',
                    'cible': {'valeur': 80, 'condition': '>='},
                    'periodes': [
                        {'periode': 'A1', 'a_realiser': 100, 'realiser': 85},
                    ],
                    'observation': '85% des inspecteurs certifies, plan de rattrapage pour les 15% restants.',
                },
            ],
        },
        {
            'libelle': 'Ameliorer la gestion documentaire de la certification',
            'indicateurs': [
                {
                    'libelle': 'Taux de numerisation des dossiers de certification',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 70, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 100, 'realiser': 65},
                        {'periode': 'S2', 'a_realiser': 100, 'realiser': 80},
                    ],
                    'observation': 'S1 en dessous de la cible, fort rattrapage realise en S2.',
                },
                {
                    'libelle': 'Delai moyen de mise a jour des manuels de procedures (jours)',
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 30, 'condition': '<='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 30, 'realiser': 25},
                        {'periode': 'S2', 'a_realiser': 30, 'realiser': 22},
                    ],
                    'observation': 'Mises a jour realisees bien en deca du delai maximal.',
                },
            ],
        },
        {
            'libelle': 'Coordonner efficacement avec les organismes internationaux',
            'indicateurs': [
                {
                    'libelle': "Nombre de reunions de coordination OACI/UEMOA realisees",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 2, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 2, 'realiser': 2},
                        {'periode': 'T2', 'a_realiser': 2, 'realiser': 3},
                        {'periode': 'T3', 'a_realiser': 2, 'realiser': 2},
                        {'periode': 'T4', 'a_realiser': 2, 'realiser': 2},
                    ],
                    'observation': 'Coordination soutenue, reunion supplementaire en T2 pour revue USOAP.',
                },
            ],
        },
    ],
    'PRS-DSF': [
        {
            'libelle': 'Assurer la disponibilite et la fiabilite des infrastructures de navigation aerienne',
            'indicateurs': [
                {
                    'libelle': "Taux de disponibilite des equipements de navigation",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 98, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 98, 'realiser': 99},
                        {'periode': 'T2', 'a_realiser': 98, 'realiser': 98},
                        {'periode': 'T3', 'a_realiser': 98, 'realiser': 97},
                        {'periode': 'T4', 'a_realiser': 98, 'realiser': 99},
                    ],
                    'observation': 'Legerement en dessous en T3 suite a panne VOR, reparee sous 48h.',
                },
                {
                    'libelle': "Nombre d'incidents techniques enregistres",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 3, 'condition': '<='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 3, 'realiser': 2},
                        {'periode': 'T2', 'a_realiser': 3, 'realiser': 1},
                        {'periode': 'T3', 'a_realiser': 3, 'realiser': 3},
                        {'periode': 'T4', 'a_realiser': 3, 'realiser': 1},
                    ],
                    'observation': 'Tres bon bilan sur l annee, objectif globalement respecte.',
                },
            ],
        },
        {
            'libelle': 'Renforcer la securite des infrastructures aeroportuaires',
            'indicateurs': [
                {
                    'libelle': "Taux de realisation des inspections de securite aeroport",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 90, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 12, 'realiser': 11},
                        {'periode': 'T2', 'a_realiser': 12, 'realiser': 12},
                        {'periode': 'T3', 'a_realiser': 12, 'realiser': 11},
                        {'periode': 'T4', 'a_realiser': 12, 'realiser': 12},
                    ],
                    'observation': 'Taux superieur a 90% sur toute l annee.',
                },
                {
                    'libelle': "Nombre d'exercices de gestion de crise realises",
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 1, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 1, 'realiser': 1},
                        {'periode': 'S2', 'a_realiser': 1, 'realiser': 2},
                    ],
                    'observation': 'Exercice supplementaire en S2 suite a recommandation OACI.',
                },
            ],
        },
        {
            'libelle': 'Mettre en oeuvre le programme de maintenance preventive',
            'indicateurs': [
                {
                    'libelle': "Taux de realisation du programme de maintenance preventive",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 85, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 20, 'realiser': 18},
                        {'periode': 'T2', 'a_realiser': 22, 'realiser': 20},
                        {'periode': 'T3', 'a_realiser': 20, 'realiser': 19},
                        {'periode': 'T4', 'a_realiser': 18, 'realiser': 17},
                    ],
                    'observation': 'Programme bien respecte malgre contraintes de disponibilite des techniciens.',
                },
                {
                    'libelle': "Delai moyen de resolution des pannes critiques (heures)",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 4, 'condition': '<='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 4, 'realiser': 3},
                        {'periode': 'T2', 'a_realiser': 4, 'realiser': 2},
                        {'periode': 'T3', 'a_realiser': 4, 'realiser': 4},
                        {'periode': 'T4', 'a_realiser': 4, 'realiser': 2},
                    ],
                    'observation': 'Excellent temps de reponse, objectif largement atteint.',
                },
            ],
        },
    ],
    'PRS-DSV': [
        {
            'libelle': 'Assurer la surveillance continue de la navigabilite des aeronefs',
            'indicateurs': [
                {
                    'libelle': "Taux d'inspections de navigabilite realisees",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 90, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 20, 'realiser': 19},
                        {'periode': 'T2', 'a_realiser': 22, 'realiser': 21},
                        {'periode': 'T3', 'a_realiser': 20, 'realiser': 20},
                        {'periode': 'T4', 'a_realiser': 18, 'realiser': 17},
                    ],
                    'observation': 'Surveillance maintenue a un niveau satisfaisant tout au long de l annee.',
                },
                {
                    'libelle': "Nombre de certificats de navigabilite delivres",
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 15, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 15, 'realiser': 18},
                        {'periode': 'S2', 'a_realiser': 15, 'realiser': 16},
                    ],
                    'observation': 'Volume superieur a la cible sur les deux semestres.',
                },
                {
                    'libelle': "Taux de traitement des rapports d'anomalie techniques",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 95, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 10, 'realiser': 10},
                        {'periode': 'T2', 'a_realiser': 12, 'realiser': 12},
                        {'periode': 'T3', 'a_realiser': 11, 'realiser': 10},
                        {'periode': 'T4', 'a_realiser': 9, 'realiser': 9},
                    ],
                    'observation': 'Traitement quasi-integral, seul un rapport en cours en T3.',
                },
            ],
        },
        {
            'libelle': 'Renforcer la formation et qualification du personnel technique',
            'indicateurs': [
                {
                    'libelle': "Nombre d'ingenieurs navigabilite qualifies selon normes PART-66",
                    'frequence': 'Annuelle',
                    'cible': {'valeur': 10, 'condition': '>='},
                    'periodes': [
                        {'periode': 'A1', 'a_realiser': 10, 'realiser': 12},
                    ],
                    'observation': '12 ingenieurs qualifies, depassement de l objectif grace au programme IACO.',
                },
                {
                    'libelle': "Taux de realisation du plan de formation technique",
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 80, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 10, 'realiser': 9},
                        {'periode': 'S2', 'a_realiser': 10, 'realiser': 8},
                    ],
                    'observation': 'Formations realisees dans les deux semestres conformement au plan.',
                },
            ],
        },
        {
            'libelle': 'Ameliorer la coordination avec les compagnies aeriennes',
            'indicateurs': [
                {
                    'libelle': "Nombre de reunions de coordination avec les exploitants",
                    'frequence': 'Trimestrielle',
                    'cible': {'valeur': 3, 'condition': '>='},
                    'periodes': [
                        {'periode': 'T1', 'a_realiser': 3, 'realiser': 3},
                        {'periode': 'T2', 'a_realiser': 3, 'realiser': 4},
                        {'periode': 'T3', 'a_realiser': 3, 'realiser': 3},
                        {'periode': 'T4', 'a_realiser': 3, 'realiser': 3},
                    ],
                    'observation': 'Reunion supplementaire en T2 pour clarification sur nouvelles directives.',
                },
                {
                    'libelle': "Taux de mise en conformite apres inspection",
                    'frequence': 'Semestrielle',
                    'cible': {'valeur': 85, 'condition': '>='},
                    'periodes': [
                        {'periode': 'S1', 'a_realiser': 100, 'realiser': 88},
                        {'periode': 'S2', 'a_realiser': 100, 'realiser': 92},
                    ],
                    'observation': 'Taux en progression, compagnies de plus en plus repondantes.',
                },
            ],
        },
    ],
}

# Amendements : revision des cibles pour certains processus
AMENDEMENTS = {
    'PRS-DAAF': {
        'amendement_1': {
            'raison': 'Revision des cibles budgetaires suite a la loi de finances rectificative du S1.',
            'mises_a_jour': {
                "Taux d'execution du budget alloue": {'cible': {'valeur': 88, 'condition': '>='}},
                'Taux de mandatement des depenses dans les delais': {'cible': {'valeur': 92, 'condition': '>='}},
            },
        },
        'amendement_2': {
            'raison': 'Mise a jour finale post-audit de la Cour des Comptes.',
            'mises_a_jour': {
                "Taux d'execution du budget alloue": {'cible': {'valeur': 90, 'condition': '>='}},
            },
        },
    },
    'PRS-DSSC': {
        'amendement_1': {
            'raison': 'Ajustement suite aux nouvelles exigences OACI - Doc 9734 revise.',
            'mises_a_jour': {
                'Taux de dossiers de certification traites dans les delais': {'cible': {'valeur': 97, 'condition': '>='}},
                'Taux de resolution des ecarts de securite detectes': {'cible': {'valeur': 95, 'condition': '>='}},
            },
        },
        'amendement_2': {
            'raison': 'Revision post-audit USOAP - recommandations integrees.',
            'mises_a_jour': {
                "Nombre d'inspecteurs formes sur les nouvelles normes OACI": {'cible': {'valeur': 12, 'condition': '>='}},
            },
        },
    },
    'PRS-DSF': {
        'amendement_1': {
            'raison': "Extension du programme de maintenance suite a l acquisition de nouveaux equipements.",
            'mises_a_jour': {
                "Taux de disponibilite des equipements de navigation": {'cible': {'valeur': 99, 'condition': '>='}},
            },
        },
    },
    'PRS-DSV': {
        'amendement_1': {
            'raison': 'Revision suite a la mise en vigueur des nouvelles normes PART-145.',
            'mises_a_jour': {
                "Taux d'inspections de navigabilite realisees": {'cible': {'valeur': 92, 'condition': '>='}},
                "Taux de mise en conformite apres inspection": {'cible': {'valeur': 90, 'condition': '>='}},
            },
        },
        'amendement_2': {
            'raison': 'Ajustement final apres revue annuelle de performance.',
            'mises_a_jour': {
                "Taux de traitement des rapports d'anomalie techniques": {'cible': {'valeur': 98, 'condition': '>='}},
            },
        },
    },
    'PRS-SDARH': {
        'amendement_1': {
            'raison': 'Actualisation suite aux nouvelles orientations du plan strategique RH.',
            'mises_a_jour': {
                'Taux de realisation du plan de formation annuel': {'cible': {'valeur': 85, 'condition': '>='}},
            },
        },
    },
}


class Command(BaseCommand):
    help = 'Seed les tableaux de bord avec des donnees realistes (plusieurs processus, Initial + Amendements, preuves PDF)'

    def handle(self, *args, **options):
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('Aucun superuser trouve. Creez-en un d abord.'))
            return

        self._ensure_frequences()
        self._ensure_referentiels_analyse()
        preuve_media = self._get_or_create_preuve_media()

        annee = 2025
        stats = {'tableaux': 0, 'objectifs': 0, 'indicateurs': 0, 'amendements': 0, 'preuves': 0,
                 'analyses': 0, 'lignes': 0, 'actions': 0}

        for processus_nom, objectifs_data in OBJECTIFS_PAR_PROCESSUS.items():
            processus = Processus.objects.filter(nom=processus_nom).first()
            if not processus:
                self.stdout.write(self.style.WARNING(f'  [SKIP] Processus non trouve: {processus_nom}'))
                continue

            self.stdout.write(f'\n[PROCESSUS] {processus}')

            # ---- Tableau Initial ----
            tableau_initial, created = TableauBord.objects.get_or_create(
                annee=annee,
                processus=processus,
                num_amendement=0,
                defaults={
                    'cree_par': user,
                    'is_validated': True,
                    'date_validation': timezone.now(),
                    'valide_par': user,
                },
            )
            if created:
                stats['tableaux'] += 1
                self.stdout.write(self.style.SUCCESS(f'  + Tableau Initial cree'))
            else:
                self.stdout.write(f'  o Tableau Initial existant')

            self._seed_objectifs(
                tableau_initial, objectifs_data, user, stats,
                preuve_media=preuve_media,
            )

            # ---- Amendements ----
            amend_data = AMENDEMENTS.get(processus_nom, {})

            for amend_num, amend_info in [
                (1, amend_data.get('amendement_1')),
                (2, amend_data.get('amendement_2')),
            ]:
                if not amend_info:
                    continue
                tableau_amend, created = TableauBord.objects.get_or_create(
                    annee=annee,
                    processus=processus,
                    num_amendement=amend_num,
                    defaults={
                        'cree_par': user,
                        'initial_ref': tableau_initial,
                        'raison_amendement': amend_info['raison'],
                    },
                )
                if created:
                    stats['amendements'] += 1
                    self.stdout.write(self.style.SUCCESS(f'  + Amendement {amend_num} cree'))
                else:
                    self.stdout.write(f'  o Amendement {amend_num} existant')

                self._seed_objectifs(
                    tableau_amend, objectifs_data, user, stats,
                    preuve_media=preuve_media,
                    cible_overrides=amend_info.get('mises_a_jour', {}),
                )

        # ---- Analyses + marquage indicateurs atteints ----
        self.stdout.write(self.style.SUCCESS('\n[ANALYSES]'))
        self._seed_analyses(user, annee, preuve_media, stats)
        self._marquer_indicateurs_atteints()

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Resume:'))
        self.stdout.write(self.style.SUCCESS(f'  Tableaux crees    : {stats["tableaux"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Amendements crees : {stats["amendements"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Objectifs crees   : {stats["objectifs"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Indicateurs crees : {stats["indicateurs"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Preuves attachees : {stats["preuves"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Analyses creees   : {stats["analyses"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Lignes analyses   : {stats["lignes"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Actions creees    : {stats["actions"]}'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _ensure_frequences(self):
        for nom in FREQUENCES:
            Frequence.objects.get_or_create(nom=nom)

    def _get_or_create_preuve_media(self):
        """Cree (ou recupere) le Media associe au fichier preuve.pdf."""
        existing = Media.objects.filter(description='Preuve de realisation - rapport PDF').first()
        if existing:
            return existing

        pdf_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'medias', 'preuve.pdf'))
        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.WARNING(f'  [WARN] Fichier preuve.pdf introuvable: {pdf_path}'))
            return None

        with open(pdf_path, 'rb') as f:
            media = Media(description='Preuve de realisation - rapport PDF')
            media.fichier.save('preuve.pdf', File(f), save=True)

        self.stdout.write(self.style.SUCCESS('  + Media preuve.pdf cree'))
        return media

    def _seed_objectifs(self, tableau, objectifs_data, user, stats, preuve_media=None, cible_overrides=None):
        cible_overrides = cible_overrides or {}

        for obj_data in objectifs_data:
            obj, created = Objectives.objects.get_or_create(
                tableau_bord=tableau,
                libelle=obj_data['libelle'],
                defaults={'cree_par': user},
            )
            if created:
                stats['objectifs'] += 1

            for ind_data in obj_data['indicateurs']:
                self._seed_indicateur(
                    obj, ind_data, user, stats,
                    preuve_media=preuve_media,
                    cible_override=cible_overrides.get(ind_data['libelle']),
                )

    def _seed_indicateur(self, objectif, ind_data, user, stats, preuve_media=None, cible_override=None):
        frequence = Frequence.objects.filter(nom=ind_data['frequence']).first()

        ind, created = Indicateur.objects.get_or_create(
            objective_id=objectif,
            libelle=ind_data['libelle'],
            defaults={'frequence_id': frequence},
        )
        if created:
            stats['indicateurs'] += 1

        # Cible (override si amendement)
        cible_data = (cible_override or {}).get('cible') or ind_data.get('cible')
        if cible_data:
            Cible.objects.update_or_create(
                indicateur_id=ind,
                defaults={
                    'valeur': cible_data['valeur'],
                    'condition': cible_data['condition'],
                },
            )

        # Periodicites avec preuve attachee
        for p in ind_data.get('periodes', []):
            taux = round((p['realiser'] / p['a_realiser']) * 100, 2) if p['a_realiser'] else 0

            preuve = None
            if preuve_media:
                preuve = Preuve.objects.create(
                    titre=f"Preuve de realisation - {ind_data['libelle']} - {p['periode']}"
                )
                preuve.medias.add(preuve_media)
                stats['preuves'] += 1

            Periodicite.objects.update_or_create(
                indicateur_id=ind,
                periode=p['periode'],
                defaults={
                    'a_realiser': p['a_realiser'],
                    'realiser': p['realiser'],
                    'taux': taux,
                    'preuve': preuve,
                },
            )

        # Observation
        obs_text = ind_data.get('observation')
        if obs_text:
            Observation.objects.get_or_create(
                indicateur_id=ind,
                defaults={'libelle': obs_text, 'cree_par': user},
            )

    # -----------------------------------------------------------------------
    # Référentiels analyse
    # -----------------------------------------------------------------------

    def _ensure_referentiels_analyse(self):
        for data in ETATS_MISE_EN_OEUVRE:
            EtatMiseEnOeuvre.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
        for data in APPRECIATIONS:
            Appreciation.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})

    # -----------------------------------------------------------------------
    # Analyses
    # -----------------------------------------------------------------------

    def _seed_analyses(self, user, annee, preuve_media, stats):
        etats        = {e.nom: e for e in EtatMiseEnOeuvre.objects.all()}
        appreciations = {a.nom: a for a in Appreciation.objects.all()}
        directions    = list(Direction.objects.all()[:3])
        sous_dirs     = list(SousDirection.objects.all()[:2])

        for processus_nom, lignes_data in ANALYSES_DATA.items():
            processus = Processus.objects.filter(nom=processus_nom).first()
            if not processus:
                continue

            tableaux = TableauBord.objects.filter(processus=processus, annee=annee)
            if not tableaux.exists():
                continue

            self.stdout.write(f'  [{processus_nom}]')

            for tableau in tableaux:
                analyse, created = AnalyseTableau.objects.get_or_create(
                    tableau_bord=tableau,
                    defaults={'cree_par': user},
                )
                if created:
                    stats['analyses'] += 1
                    self.stdout.write(self.style.SUCCESS(f'    + Analyse: {tableau.nom_version}'))
                else:
                    self.stdout.write(f'    o Analyse existante: {tableau.nom_version}')

                for ligne_data in lignes_data:
                    ligne, created = AnalyseLigne.objects.get_or_create(
                        analyse_tableau=analyse,
                        periode=ligne_data['periode'],
                        defaults={
                            'objectif_non_atteint': ligne_data['objectif_non_atteint'],
                            'cible':    ligne_data['cible'],
                            'resultat': ligne_data['resultat'],
                            'causes':   ligne_data['causes'],
                        },
                    )
                    if created:
                        stats['lignes'] += 1

                    for action_data in ligne_data['actions']:
                        etat        = etats.get(action_data['etat'])
                        appreciation = appreciations.get(action_data['evaluation'])

                        preuve = None
                        if preuve_media:
                            preuve = Preuve.objects.create(
                                titre=f"Preuve action: {action_data['action'][:60]}"
                            )
                            preuve.medias.add(preuve_media)
                            stats['preuves'] += 1

                        action, created = AnalyseAction.objects.get_or_create(
                            ligne=ligne,
                            action=action_data['action'],
                            defaults={
                                'delai_realisation':    action_data['delai'],
                                'etat_mise_en_oeuvre':  etat,
                                'date_realisation':     action_data['date_realisation'],
                                'evaluation':           appreciation,
                                'commentaire':          action_data['commentaire'],
                                'preuve':               preuve,
                            },
                        )
                        if created:
                            stats['actions'] += 1
                            if directions:
                                action.responsables_directions.set(directions[:2])
                            if sous_dirs:
                                action.responsables_sous_directions.set(sous_dirs[:1])

    # -----------------------------------------------------------------------
    # Marquage indicateurs atteints (2/3 des periodicites)
    # -----------------------------------------------------------------------

    def _marquer_indicateurs_atteints(self):
        from decimal import Decimal
        count = 0
        for cible in Cible.objects.select_related('indicateur_id').all():
            indicateur  = cible.indicateur_id
            periodicites = list(Periodicite.objects.filter(indicateur_id=indicateur))
            total = len(periodicites)
            if total == 0:
                continue
            # On marque les 2/3 des periodicites comme "atteintes"
            nb_atteints = max(1, int(total * 2 / 3))
            for periodicite in periodicites[:nb_atteints]:
                valeur_cible = float(cible.valeur)
                a_realiser   = float(periodicite.a_realiser)
                if a_realiser == 0:
                    continue
                if cible.condition in ('>=', '>'):
                    # realiser doit donner un taux >= valeur_cible
                    realiser = round(a_realiser * (valeur_cible / 100) * 1.05, 2)
                    realiser = min(realiser, a_realiser)
                elif cible.condition in ('<=', '<'):
                    # realiser doit donner un taux <= valeur_cible
                    realiser = round(a_realiser * (valeur_cible / 100) * 0.90, 2)
                else:
                    realiser = round(a_realiser * valeur_cible / 100, 2)

                taux = round((realiser / a_realiser) * 100, 2)
                periodicite.realiser = Decimal(str(realiser))
                periodicite.taux     = Decimal(str(taux))
                periodicite.save(update_fields=['realiser', 'taux'])
                count += 1

        self.stdout.write(self.style.SUCCESS(f'  Periodicites marquees atteintes : {count}'))
