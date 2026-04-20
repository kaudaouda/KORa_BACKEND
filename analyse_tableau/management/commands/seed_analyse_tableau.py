from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import date, timedelta

from parametre.models import (
    EtatMiseEnOeuvre, Appreciation, Cible, Periodicite, Preuve, Direction, SousDirection
)
from dashboard.models import TableauBord, Indicateur, Objectives
from analyse_tableau.models import AnalyseTableau, AnalyseLigne, AnalyseAction


# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------
ETATS_MISE_EN_OEUVRE = [
    {'nom': 'Realisee',              'description': 'Action completement realisee'},
    {'nom': 'En cours',              'description': 'Action en cours de realisation'},
    {'nom': 'Partiellement realisee','description': 'Action realisee en partie'},
    {'nom': 'Non realisee',          'description': 'Action non encore entamee'},
    {'nom': 'Abandonnee',            'description': 'Action abandonnee'},
]

APPRECIATIONS = [
    {'nom': 'Satisfaisant',          'description': 'Resultat satisfaisant'},
    {'nom': 'Tres satisfaisant',     'description': 'Resultat tres satisfaisant'},
    {'nom': 'Insuffisant',           'description': 'Resultat insuffisant'},
    {'nom': 'A ameliorer',           'description': 'Des efforts supplementaires sont necessaires'},
]

# ---------------------------------------------------------------------------
# Données des analyses par processus
# Chaque entrée correspond à un trimestre/semestre non atteint
# ---------------------------------------------------------------------------
ANALYSES_DATA = {
    'PRS-DAAF': [
        {
            'periode': 'T3',
            'objectif_non_atteint': "Taux d'execution du budget alloue insuffisant en T3 (84% vs cible 85%)",
            'cible': 'Taux >= 85%',
            'resultat': '84% — Ecart de 1 point due aux retards de marches publics',
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
            'objectif_non_atteint': "Taux de realisation du plan de maintenance des equipements en S1 (85% vs cible 80%) — Objectif ATTEINT mais analyse preventive effectuee",
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
            'objectif_non_atteint': "Taux de postes pourvus en S2 insuffisant (87.5% vs cible 85%) — Objectif atteint, analyse de performance",
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
            'resultat': '4% — Dans la cible mais surveillance maintenue',
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
                {
                    'action': 'Sensibiliser les managers sur la gestion des absences',
                    'delai': date(2025, 11, 30),
                    'etat': 'Realisee',
                    'date_realisation': date(2025, 11, 22),
                    'evaluation': 'Satisfaisant',
                    'commentaire': 'Atelier de sensibilisation realise pour 12 managers.',
                },
            ],
        },
    ],
    'PRS-DSSC': [
        {
            'periode': 'T2',
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
            'periode': 'T3',
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
                    'action': 'Mettre en place un suivi individualisé des certifications',
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
            'objectif_non_atteint': "Taux de disponibilite equipements T3 en dessous de cible (97% vs 98%)",
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
            'objectif_non_atteint': "Taux maintenance preventive T1 dans la cible (90% vs 85%) — Analyse de capitalisation",
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
            'periode': 'T2',
            'objectif_non_atteint': "Taux de mise en conformite apres inspection S1 (88% vs cible 85%) — Objectif atteint",
            'cible': 'Taux >= 85%',
            'resultat': '88% — Bon niveau de conformite',
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
                {
                    'action': 'Renforcer les sanctions pour les non-conformites repetees',
                    'delai': date(2025, 12, 15),
                    'etat': 'Partiellement realisee',
                    'date_realisation': None,
                    'evaluation': 'A ameliorer',
                    'commentaire': 'Projet de texte en cours de validation par la direction juridique.',
                },
            ],
        },
        {
            'periode': 'T4',
            'objectif_non_atteint': "Nombre de reunions de coordination T4 atteint (2 vs cible 2) — Analyse de cloture annuelle",
            'cible': 'Nombre >= 2',
            'resultat': '2 reunions — Objectif exactement atteint',
            'causes': (
                'Planning serré en fin d annee. '
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


class Command(BaseCommand):
    help = 'Seed les analyses de tableau de bord avec objectifs atteints/non-atteints et actions correctives'

    def handle(self, *args, **options):
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('Aucun superuser trouve.'))
            return

        self._ensure_referentiels()

        preuve_media = self._get_preuve_media()
        etats = {e.nom: e for e in EtatMiseEnOeuvre.objects.all()}
        appreciations = {a.nom: a for a in Appreciation.objects.all()}
        directions = list(Direction.objects.all()[:3])
        sous_directions = list(SousDirection.objects.all()[:2])

        stats = {'analyses': 0, 'lignes': 0, 'actions': 0}

        from parametre.models import Processus
        for processus_nom, lignes_data in ANALYSES_DATA.items():
            processus = Processus.objects.filter(nom=processus_nom).first()
            if not processus:
                self.stdout.write(self.style.WARNING(f'  [SKIP] Processus non trouve: {processus_nom}'))
                continue

            tableaux = TableauBord.objects.filter(processus=processus, annee=2025)
            if not tableaux.exists():
                self.stdout.write(self.style.WARNING(f'  [SKIP] Aucun tableau pour {processus_nom}'))
                continue

            self.stdout.write(f'\n[PROCESSUS] {processus}')

            for tableau in tableaux:
                analyse, created = AnalyseTableau.objects.get_or_create(
                    tableau_bord=tableau,
                    defaults={'cree_par': user},
                )
                if created:
                    stats['analyses'] += 1
                    self.stdout.write(self.style.SUCCESS(f'  + Analyse creee: {tableau.processus.nom}'))
                else:
                    self.stdout.write(f'  o Analyse existante: {tableau.processus.nom}')

                for ligne_data in lignes_data:
                    ligne, created = AnalyseLigne.objects.get_or_create(
                        analyse_tableau=analyse,
                        periode=ligne_data['periode'],
                        defaults={
                            'objectif_non_atteint': ligne_data['objectif_non_atteint'],
                            'cible': ligne_data['cible'],
                            'resultat': ligne_data['resultat'],
                            'causes': ligne_data['causes'],
                        },
                    )
                    if created:
                        stats['lignes'] += 1

                    for action_data in ligne_data['actions']:
                        etat = etats.get(action_data['etat'])
                        appreciation = appreciations.get(action_data['evaluation'])

                        preuve = None
                        if preuve_media:
                            preuve = Preuve.objects.create(
                                titre=f"Preuve action: {action_data['action'][:60]}"
                            )
                            preuve.medias.add(preuve_media)

                        action, created = AnalyseAction.objects.get_or_create(
                            ligne=ligne,
                            action=action_data['action'],
                            defaults={
                                'delai_realisation': action_data['delai'],
                                'etat_mise_en_oeuvre': etat,
                                'date_realisation': action_data['date_realisation'],
                                'evaluation': appreciation,
                                'commentaire': action_data['commentaire'],
                                'preuve': preuve,
                            },
                        )
                        if created:
                            stats['actions'] += 1
                            if directions:
                                action.responsables_directions.set(directions[:2])
                            if sous_directions:
                                action.responsables_sous_directions.set(sous_directions[:1])

        # Mettre a jour les periodicites pour rendre plusieurs indicateurs "atteints"
        self._marquer_indicateurs_atteints()

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Resume:'))
        self.stdout.write(self.style.SUCCESS(f'  Analyses creees : {stats["analyses"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Lignes creees   : {stats["lignes"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Actions creees  : {stats["actions"]}'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

    def _ensure_referentiels(self):
        for data in ETATS_MISE_EN_OEUVRE:
            EtatMiseEnOeuvre.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
        for data in APPRECIATIONS:
            Appreciation.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})

    def _get_preuve_media(self):
        from parametre.models import Media
        return Media.objects.filter(description='Preuve de realisation - rapport PDF').first()

    def _marquer_indicateurs_atteints(self):
        """
        Pour chaque indicateur ayant une cible, ajuste les periodicites
        de facon a ce qu un bon nombre soient "atteints" (taux >= cible).
        """
        from decimal import Decimal
        from parametre.models import Cible, Periodicite
        count = 0
        for cible in Cible.objects.select_related('indicateur_id').all():
            indicateur = cible.indicateur_id
            periodicites = Periodicite.objects.filter(indicateur_id=indicateur)
            total = periodicites.count()
            if total == 0:
                continue
            # On marque les 2/3 des periodicites comme "atteintes"
            nb_atteints = max(1, int(total * 2 / 3))
            for periodicite in periodicites[:nb_atteints]:
                valeur_cible = float(cible.valeur)
                a_realiser = float(periodicite.a_realiser)
                if a_realiser == 0:
                    continue
                # Calculer une valeur realisee qui satisfait la cible
                if cible.condition in ('>=', '>'):
                    realiser = round(a_realiser * (valeur_cible / 100) * 1.05, 2)
                    realiser = min(realiser, a_realiser)
                elif cible.condition in ('<=', '<'):
                    realiser = round(a_realiser * (valeur_cible / 100) * 0.90, 2)
                else:
                    realiser = round(a_realiser * valeur_cible / 100, 2)

                taux = round((realiser / a_realiser) * 100, 2)
                periodicite.realiser = Decimal(str(realiser))
                periodicite.taux = Decimal(str(taux))
                periodicite.save(update_fields=['realiser', 'taux'])
                count += 1

        self.stdout.write(self.style.SUCCESS(f'  Periodicites marquees atteintes : {count}'))
