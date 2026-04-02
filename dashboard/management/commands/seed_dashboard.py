from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone

from parametre.models import Processus, Versions, Frequence, Cible, Periodicite
from dashboard.models import TableauBord, Objectives, Indicateur, Observation


# ---------------------------------------------------------------------------
# Données de seed
# ---------------------------------------------------------------------------

FREQUENCES = ['Trimestrielle', 'Semestrielle', 'Annuelle']

# Structure : liste de processus avec leurs objectifs / indicateurs
TABLEAU_DATA = [
    {
        'processus': 'PRS-DAAF',
        'objectifs': [
            {
                'libelle': 'Assurer la mise en oeuvre effective du systeme de management de la qualite',
                'indicateurs': [
                    {
                        'libelle': 'Taux de mise en oeuvre du plan annuel SMQ',
                        'frequence': 'Trimestrielle',
                        'cible': {'valeur': 80, 'condition': '>='},
                        'periodes': [
                            {'periode': 'T1', 'a_realiser': 10, 'realiser': 8},
                            {'periode': 'T2', 'a_realiser': 10, 'realiser': 9},
                            {'periode': 'T3', 'a_realiser': 10, 'realiser': 7},
                            {'periode': 'T4', 'a_realiser': 10, 'realiser': 10},
                        ],
                        'observation': 'Performance globale satisfaisante sur les 4 trimestres.',
                    },
                    {
                        'libelle': 'Taux de traitement des non-conformites detectees',
                        'frequence': 'Semestrielle',
                        'cible': {'valeur': 90, 'condition': '>='},
                        'periodes': [
                            {'periode': 'S1', 'a_realiser': 15, 'realiser': 14},
                            {'periode': 'S2', 'a_realiser': 12, 'realiser': 11},
                        ],
                        'observation': 'Quelques non-conformites residuelles en S2, plan de rattrapage prevu.',
                    },
                ],
            },
            {
                'libelle': 'Ameliorer en continu les processus internes',
                'indicateurs': [
                    {
                        'libelle': 'Nombre d audits internes realises',
                        'frequence': 'Annuelle',
                        'cible': {'valeur': 4, 'condition': '>='},
                        'periodes': [
                            {'periode': 'A1', 'a_realiser': 4, 'realiser': 4},
                        ],
                        'observation': 'Tous les audits planifies ont ete realises.',
                    },
                    {
                        'libelle': 'Taux de satisfaction des parties interessees',
                        'frequence': 'Semestrielle',
                        'cible': {'valeur': 75, 'condition': '>='},
                        'periodes': [
                            {'periode': 'S1', 'a_realiser': 100, 'realiser': 78},
                            {'periode': 'S2', 'a_realiser': 100, 'realiser': 82},
                        ],
                        'observation': 'Satisfaction en hausse sur les deux semestres.',
                    },
                ],
            },
        ],
    },
    {
        'processus': 'PRS-DSSC',
        'objectifs': [
            {
                'libelle': 'Garantir la delivrance des licences et certificats dans les delais reglementaires',
                'indicateurs': [
                    {
                        'libelle': 'Taux de dossiers traites dans le delai reglementaire',
                        'frequence': 'Trimestrielle',
                        'cible': {'valeur': 95, 'condition': '>='},
                        'periodes': [
                            {'periode': 'T1', 'a_realiser': 50, 'realiser': 48},
                            {'periode': 'T2', 'a_realiser': 55, 'realiser': 53},
                            {'periode': 'T3', 'a_realiser': 60, 'realiser': 57},
                            {'periode': 'T4', 'a_realiser': 45, 'realiser': 44},
                        ],
                        'observation': 'Taux conforme a la cible sur tous les trimestres.',
                    },
                    {
                        'libelle': 'Nombre de licences delivrees',
                        'frequence': 'Semestrielle',
                        'cible': {'valeur': 100, 'condition': '>='},
                        'periodes': [
                            {'periode': 'S1', 'a_realiser': 110, 'realiser': 105},
                            {'periode': 'S2', 'a_realiser': 100, 'realiser': 98},
                        ],
                        'observation': 'Volume de dossiers en legere hausse en S1.',
                    },
                ],
            },
            {
                'libelle': 'Renforcer les capacites de surveillance de la navigabilite',
                'indicateurs': [
                    {
                        'libelle': 'Taux d inspections de navigabilite realisees',
                        'frequence': 'Trimestrielle',
                        'cible': {'valeur': 85, 'condition': '>='},
                        'periodes': [
                            {'periode': 'T1', 'a_realiser': 20, 'realiser': 18},
                            {'periode': 'T2', 'a_realiser': 20, 'realiser': 17},
                            {'periode': 'T3', 'a_realiser': 20, 'realiser': 19},
                            {'periode': 'T4', 'a_realiser': 20, 'realiser': 20},
                        ],
                        'observation': 'Bonne progression sur T3 et T4 apres un debut d annee difficile.',
                    },
                ],
            },
        ],
    },
]

# Données de l'Amendement 1 : modifications légères sur les cibles et periodicités
AMENDEMENT_1_UPDATES = {
    'PRS-DAAF': {
        'raison': 'Revision des cibles suite a la revue de mi-annee et ajout d un indicateur supplementaire.',
        'objectifs_modifies': [
            {
                'libelle': 'Assurer la mise en oeuvre effective du systeme de management de la qualite',
                'indicateurs': [
                    {
                        'libelle': 'Taux de mise en oeuvre du plan annuel SMQ',
                        'cible': {'valeur': 85, 'condition': '>='},
                        'periodes': [
                            {'periode': 'T1', 'a_realiser': 10, 'realiser': 8},
                            {'periode': 'T2', 'a_realiser': 10, 'realiser': 10},
                            {'periode': 'T3', 'a_realiser': 10, 'realiser': 9},
                            {'periode': 'T4', 'a_realiser': 10, 'realiser': 10},
                        ],
                    },
                ],
            },
        ],
    },
    'PRS-DSSC': {
        'raison': 'Ajustement des objectifs suite aux nouveaux reglements OACI en vigueur.',
        'objectifs_modifies': [
            {
                'libelle': 'Garantir la delivrance des licences et certificats dans les delais reglementaires',
                'indicateurs': [
                    {
                        'libelle': 'Taux de dossiers traites dans le delai reglementaire',
                        'cible': {'valeur': 97, 'condition': '>='},
                        'periodes': [
                            {'periode': 'T1', 'a_realiser': 50, 'realiser': 49},
                            {'periode': 'T2', 'a_realiser': 55, 'realiser': 54},
                            {'periode': 'T3', 'a_realiser': 60, 'realiser': 59},
                            {'periode': 'T4', 'a_realiser': 45, 'realiser': 45},
                        ],
                    },
                ],
            },
        ],
    },
}

# Données de l'Amendement 2
AMENDEMENT_2_UPDATES = {
    'PRS-DAAF': {
        'raison': 'Mise a jour finale apres audit externe de certification.',
        'objectifs_modifies': [
            {
                'libelle': 'Assurer la mise en oeuvre effective du systeme de management de la qualite',
                'indicateurs': [
                    {
                        'libelle': 'Taux de mise en oeuvre du plan annuel SMQ',
                        'cible': {'valeur': 90, 'condition': '>='},
                        'periodes': [
                            {'periode': 'T1', 'a_realiser': 10, 'realiser': 9},
                            {'periode': 'T2', 'a_realiser': 10, 'realiser': 10},
                            {'periode': 'T3', 'a_realiser': 10, 'realiser': 10},
                            {'periode': 'T4', 'a_realiser': 10, 'realiser': 10},
                        ],
                    },
                ],
            },
        ],
    },
}


class Command(BaseCommand):
    help = 'Seed les tableaux de bord avec des donnees realistes (Initial + Amendements)'

    def handle(self, *args, **options):
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('Aucun superuser trouve. Creez-en un d abord.'))
            return

        self._ensure_frequences()

        version_initial = Versions.objects.get(code='INITIAL')
        version_a1 = Versions.objects.get(code='AMENDEMENT_1')
        version_a2 = Versions.objects.get(code='AMENDEMENT_2')

        annee = 2025

        stats = {'tableaux': 0, 'objectives': 0, 'indicateurs': 0, 'amendements': 0}

        for item in TABLEAU_DATA:
            processus = Processus.objects.filter(nom=item['processus']).first()
            if not processus:
                self.stdout.write(self.style.WARNING(f'  Processus non trouve: {item["processus"]} - ignore'))
                continue

            self.stdout.write(f'\n[PROCESSUS] {processus}')

            # ---- Tableau Initial ----
            tableau_initial, created = TableauBord.objects.get_or_create(
                annee=annee,
                processus=processus,
                type_tableau=version_initial,
                defaults={
                    'cree_par': user,
                    'is_validated': True,
                    'date_validation': timezone.now(),
                    'valide_par': user,
                },
            )
            if created:
                stats['tableaux'] += 1
                self.stdout.write(self.style.SUCCESS(f'  + Tableau Initial cree: {tableau_initial}'))
            else:
                self.stdout.write(f'  o Tableau Initial existant: {tableau_initial}')

            self._seed_objectives(tableau_initial, item['objectifs'], user, stats)

            # ---- Amendement 1 ----
            updates_a1 = AMENDEMENT_1_UPDATES.get(item['processus'])
            if updates_a1:
                tableau_a1, created = TableauBord.objects.get_or_create(
                    annee=annee,
                    processus=processus,
                    type_tableau=version_a1,
                    defaults={
                        'cree_par': user,
                        'initial_ref': tableau_initial,
                        'raison_amendement': updates_a1['raison'],
                    },
                )
                if created:
                    stats['amendements'] += 1
                    self.stdout.write(self.style.SUCCESS(f'  + Amendement 1 cree'))
                else:
                    self.stdout.write(f'  o Amendement 1 existant')
                self._seed_objectives(tableau_a1, item['objectifs'], user, stats,
                                      updates=updates_a1.get('objectifs_modifies', []))

            # ---- Amendement 2 ----
            updates_a2 = AMENDEMENT_2_UPDATES.get(item['processus'])
            if updates_a2:
                tableau_a2, created = TableauBord.objects.get_or_create(
                    annee=annee,
                    processus=processus,
                    type_tableau=version_a2,
                    defaults={
                        'cree_par': user,
                        'initial_ref': tableau_initial,
                        'raison_amendement': updates_a2['raison'],
                    },
                )
                if created:
                    stats['amendements'] += 1
                    self.stdout.write(self.style.SUCCESS(f'  + Amendement 2 cree'))
                else:
                    self.stdout.write(f'  o Amendement 2 existant')
                self._seed_objectives(tableau_a2, item['objectifs'], user, stats,
                                      updates=updates_a2.get('objectifs_modifies', []))

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Resume:'))
        self.stdout.write(self.style.SUCCESS(f'  Tableaux crees    : {stats["tableaux"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Amendements crees : {stats["amendements"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Objectifs crees   : {stats["objectives"]}'))
        self.stdout.write(self.style.SUCCESS(f'  Indicateurs crees : {stats["indicateurs"]}'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _ensure_frequences(self):
        for nom in FREQUENCES:
            Frequence.objects.get_or_create(nom=nom)

    def _seed_objectives(self, tableau, objectifs_data, user, stats, updates=None):
        """
        Cree les objectifs + indicateurs pour un tableau.
        Si `updates` est fourni, ecrase les valeurs des indicateurs concernes.
        """
        updates_map = {}
        if updates:
            for upd_obj in updates:
                for upd_ind in upd_obj.get('indicateurs', []):
                    updates_map[upd_ind['libelle']] = upd_ind

        for obj_data in objectifs_data:
            obj, created = Objectives.objects.get_or_create(
                tableau_bord=tableau,
                libelle=obj_data['libelle'],
                defaults={'cree_par': user},
            )
            if created:
                stats['objectives'] += 1

            for ind_data in obj_data['indicateurs']:
                override = updates_map.get(ind_data['libelle'], {})
                self._seed_indicateur(obj, ind_data, user, stats, override)

    def _seed_indicateur(self, objectif, ind_data, user, stats, override):
        frequence = Frequence.objects.filter(nom=ind_data['frequence']).first()

        ind, created = Indicateur.objects.get_or_create(
            objective_id=objectif,
            libelle=ind_data['libelle'],
            defaults={'frequence_id': frequence},
        )
        if created:
            stats['indicateurs'] += 1

        # Cible
        cible_data = override.get('cible', ind_data.get('cible'))
        if cible_data:
            Cible.objects.update_or_create(
                indicateur_id=ind,
                defaults={
                    'valeur': cible_data['valeur'],
                    'condition': cible_data['condition'],
                },
            )

        # Periodicites
        periodes = override.get('periodes', ind_data.get('periodes', []))
        for p in periodes:
            taux = round((p['realiser'] / p['a_realiser']) * 100, 2) if p['a_realiser'] else 0
            Periodicite.objects.update_or_create(
                indicateur_id=ind,
                periode=p['periode'],
                defaults={
                    'a_realiser': p['a_realiser'],
                    'realiser': p['realiser'],
                    'taux': taux,
                },
            )

        # Observation
        obs_text = ind_data.get('observation')
        if obs_text:
            Observation.objects.get_or_create(
                indicateur_id=ind,
                defaults={'libelle': obs_text, 'cree_par': user},
            )
