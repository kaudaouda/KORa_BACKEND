from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

from parametre.models import (
    Processus, Annee, Mois, Frequence,
    Direction, SousDirection, EtatMiseEnOeuvre,
)
from activite_periodique.models import ActivitePeriodique, DetailsAP, SuivisAP

# ---------------------------------------------------------------------------
# Référentiel Mois
# ---------------------------------------------------------------------------
MOIS_DATA = [
    {'numero': 1,  'nom': 'Janvier',   'abreviation': 'Jan'},
    {'numero': 2,  'nom': 'Fevrier',   'abreviation': 'Fev'},
    {'numero': 3,  'nom': 'Mars',      'abreviation': 'Mar'},
    {'numero': 4,  'nom': 'Avril',     'abreviation': 'Avr'},
    {'numero': 5,  'nom': 'Mai',       'abreviation': 'Mai'},
    {'numero': 6,  'nom': 'Juin',      'abreviation': 'Jun'},
    {'numero': 7,  'nom': 'Juillet',   'abreviation': 'Jul'},
    {'numero': 8,  'nom': 'Aout',      'abreviation': 'Aou'},
    {'numero': 9,  'nom': 'Septembre', 'abreviation': 'Sep'},
    {'numero': 10, 'nom': 'Octobre',   'abreviation': 'Oct'},
    {'numero': 11, 'nom': 'Novembre',  'abreviation': 'Nov'},
    {'numero': 12, 'nom': 'Decembre',  'abreviation': 'Dec'},
]

# ---------------------------------------------------------------------------
# Activités périodiques par processus
# Chaque activité a : libelle, frequence, mois de réalisation prévus
# ---------------------------------------------------------------------------
ACTIVITES_PAR_PROCESSUS = {
    'PRS-DAAF': [
        {
            'libelle': 'Elaboration et suivi du budget annuel',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Rapport de suivi budgetaire trimestriel',
        },
        {
            'libelle': 'Revue des marches et contrats en cours',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'Rapport de revue des marches',
        },
        {
            'libelle': 'Inventaire du patrimoine et des equipements',
            'frequence': 'Annuelle',
            'mois_prevus': [12],
            'livrable': 'Rapport d inventaire annuel',
        },
        {
            'libelle': 'Elaboration du rapport financier mensuel',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Rapport financier consolide',
        },
        {
            'libelle': 'Audit interne de la gestion comptable',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'Rapport d audit interne comptable',
        },
    ],
    'PRS-SDARH': [
        {
            'libelle': 'Elaboration et suivi du plan de formation',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Rapport de suivi du plan de formation',
        },
        {
            'libelle': 'Evaluation annuelle des performances du personnel',
            'frequence': 'Annuelle',
            'mois_prevus': [12],
            'livrable': 'Rapport d evaluation annuelle du personnel',
        },
        {
            'libelle': 'Suivi des effectifs et des mouvements du personnel',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Tableau de bord RH trimestriel',
        },
        {
            'libelle': 'Organisation des sessions de formation reglementaire',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'PV de session de formation',
        },
        {
            'libelle': 'Elaboration du bilan social annuel',
            'frequence': 'Annuelle',
            'mois_prevus': [3],
            'livrable': 'Bilan social annuel',
        },
    ],
    'PRS-DSSC': [
        {
            'libelle': 'Inspections de surveillance des operateurs aeriens',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Rapport d inspection de surveillance',
        },
        {
            'libelle': 'Revue du programme de surveillance',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'Rapport de revue du programme de surveillance',
        },
        {
            'libelle': 'Analyse des rapports de securite recus',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Synthese des rapports de securite',
        },
        {
            'libelle': 'Reunion de coordination securite avec les operateurs',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'PV de reunion de coordination securite',
        },
        {
            'libelle': 'Publication du bulletin de securite aeronautique',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Bulletin de securite aeronautique',
        },
    ],
    'PRS-DSF': [
        {
            'libelle': 'Inspections des infrastructures aeroportuaires',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Rapport d inspection des infrastructures',
        },
        {
            'libelle': 'Revue du programme de certification',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'Rapport de revue du programme de certification',
        },
        {
            'libelle': 'Audit de conformite des operateurs certifies',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'Rapport d audit de conformite',
        },
        {
            'libelle': 'Mise a jour de la documentation technique reglementaire',
            'frequence': 'Annuelle',
            'mois_prevus': [12],
            'livrable': 'Documentation technique mise a jour',
        },
    ],
    'PRS-DSV': [
        {
            'libelle': 'Traitement des dossiers de delivrance de licences',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Rapport de suivi des dossiers de licences',
        },
        {
            'libelle': 'Sessions d examens theoriques pour navigants',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'PV et resultats des sessions d examens',
        },
        {
            'libelle': 'Mise a jour du registre des licences navigants',
            'frequence': 'Trimestrielle',
            'mois_prevus': [3, 6, 9, 12],
            'livrable': 'Registre des licences mis a jour',
        },
        {
            'libelle': 'Rapport annuel sur les licences delivrees et renouvellees',
            'frequence': 'Annuelle',
            'mois_prevus': [12],
            'livrable': 'Rapport annuel licences navigants',
        },
        {
            'libelle': 'Formation des examinateurs de vol',
            'frequence': 'Semestrielle',
            'mois_prevus': [6, 12],
            'livrable': 'Attestation de formation des examinateurs',
        },
    ],
}

# Etats cycliques pour les suivis — pour paraître réaliste
# Realisee pour la plupart, quelques En cours / Partiellement realisee
ETATS_CYCLE = [
    'Realisee', 'Realisee', 'Realisee', 'Partiellement realisee',
    'Realisee', 'Realisee', 'En cours', 'Realisee',
    'Realisee', 'Non realisee', 'Realisee', 'Realisee',
]

LIVRABLES_COMPLEMENTS = [
    'Valide et diffuse aux parties prenantes.',
    'Soumis a la direction pour approbation.',
    'Archive dans le systeme documentaire.',
    'Transmis aux autorites competentes.',
    'En attente de validation hiearchique.',
    'Approuve lors de la reunion de direction.',
]


class Command(BaseCommand):
    help = 'Seed les Activites Periodiques avec details et suivis mensuels'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed Activites Periodiques'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('Aucun superutilisateur trouve.'))
            return

        self._seed_mois()
        self._seed_activites(user)

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed Activites Periodiques termine.'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

    # -----------------------------------------------------------------------
    # Mois
    # -----------------------------------------------------------------------

    def _seed_mois(self):
        self.stdout.write(self.style.SUCCESS('\n[MOIS]'))
        for data in MOIS_DATA:
            obj, created = Mois.objects.get_or_create(
                numero=data['numero'],
                defaults={'nom': data['nom'], 'abreviation': data['abreviation']}
            )
            self.stdout.write(f'  {"+" if created else "o"} {obj.numero:02d} - {obj.nom}')

    # -----------------------------------------------------------------------
    # Activités périodiques
    # -----------------------------------------------------------------------

    def _seed_activites(self, user):
        annees = list(Annee.objects.filter(annee__in=[2024, 2025]).order_by('annee'))
        processus_list = list(Processus.objects.filter(nom__in=ACTIVITES_PAR_PROCESSUS.keys()))
        directions = list(Direction.objects.all())
        sous_directions = list(SousDirection.objects.all())
        frequences = {f.nom: f for f in Frequence.objects.all()}
        etats = {e.nom: e for e in EtatMiseEnOeuvre.objects.all()}
        mois_map = {m.numero: m for m in Mois.objects.all()}

        if not processus_list:
            self.stdout.write(self.style.ERROR('Aucun processus trouve.'))
            return
        if not annees:
            self.stdout.write(self.style.ERROR('Aucune annee 2024/2025 trouvee.'))
            return
        if not mois_map:
            self.stdout.write(self.style.ERROR('Aucun mois trouve. Probleme dans _seed_mois.'))
            return

        for processus in processus_list:
            self.stdout.write(self.style.SUCCESS(f'\n[PROCESSUS] {processus.numero_processus} - {processus.nom}'))
            activites_data = ACTIVITES_PAR_PROCESSUS.get(processus.nom, [])

            for annee in annees:
                # AP Initiale
                ap_initial, created = ActivitePeriodique.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    num_amendement=0,
                    cree_par=user,
                    defaults={
                        'is_validated': True,
                        'validated_by': user,
                        'validated_at': timezone.now(),
                    }
                )
                self.stdout.write(f'  {"+" if created else "o"} AP Initiale {annee.annee}')
                self._seed_details_ap(ap_initial, activites_data, annee.annee, directions, sous_directions, frequences, etats, mois_map)

                # AP Amendement 1 — subset d'activités révisées
                ap_amend, created_a = ActivitePeriodique.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    num_amendement=1,
                    cree_par=user,
                    defaults={
                        'is_validated': True,
                        'validated_by': user,
                        'validated_at': timezone.now(),
                        'initial_ref': ap_initial,
                        'raison_amendement': f'Revision du programme d activites suite au bilan de mi-annee {annee.annee}',
                    }
                )
                self.stdout.write(f'  {"+" if created_a else "o"} AP Amendement 1 {annee.annee}')
                # Pour l'amendement : on reprend les 2-3 premières activités avec fréquence révisée
                self._seed_details_ap(
                    ap_amend,
                    activites_data[:3],
                    annee.annee,
                    directions,
                    sous_directions,
                    frequences,
                    etats,
                    mois_map,
                    is_amendement=True,
                )

    def _seed_details_ap(self, ap, activites_data, annee, directions, sous_directions,
                         frequences, etats, mois_map, is_amendement=False):
        count_details = count_suivis = 0

        for i, data in enumerate(activites_data):
            direction = directions[i % len(directions)] if directions else None
            sous_dir = next(
                (s for s in sous_directions if direction and s.direction == direction),
                sous_directions[i % len(sous_directions)] if sous_directions else None
            )
            freq_obj = frequences.get(data['frequence'])
            numero = f'{ap.processus.numero_processus}-{annee}-{"A1-" if is_amendement else ""}{i + 1:02d}'

            libelle = data['libelle']

            detail, created = DetailsAP.objects.get_or_create(
                activite_periodique=ap,
                numero_ap=numero,
                defaults={
                    'activites_periodiques': libelle,
                    'frequence': freq_obj,
                    'responsabilite_direction': direction,
                    'responsabilite_sous_direction': sous_dir,
                }
            )
            if created:
                count_details += 1
                if direction:
                    detail.responsables_directions.set([direction])
                if sous_dir:
                    detail.responsables_sous_directions.set([sous_dir])

            # Suivis par mois de réalisation prévus
            mois_prevus = data['mois_prevus']
            livrable_base = data['livrable']

            for j, mois_num in enumerate(mois_prevus):
                mois_obj = mois_map.get(mois_num)
                if not mois_obj:
                    continue

                # Etat : cycle réaliste — la plupart réalisées, quelques exceptions
                idx = (i * 4 + j) % len(ETATS_CYCLE)
                etat_nom = ETATS_CYCLE[idx]
                etat = etats.get(etat_nom)

                is_done = etat_nom == 'Realisee'
                date_real = datetime.date(annee, mois_num, 28) if is_done else (
                    datetime.date(annee, mois_num, 15) if etat_nom == 'Partiellement realisee' else None
                )

                complement = LIVRABLES_COMPLEMENTS[(i + j) % len(LIVRABLES_COMPLEMENTS)]
                livrable_suffixes = {
                    'Realisee': complement,
                    'Partiellement realisee': 'Partiellement finalise. Reste a completer avant la prochaine echeance.',
                    'En cours': 'En cours de finalisation. Soumission prevue avant la fin du mois.',
                    'Non realisee': 'Non produit ce cycle. Report prevu au prochain mois de realisation.',
                    'Abandonnee': 'Activite abandonnee. Un rapport de cloture sera etabli.',
                }
                livrable = f'{livrable_base} — {livrable_suffixes.get(etat_nom, complement)}'

                suivi, s_created = SuivisAP.objects.get_or_create(
                    details_ap=detail,
                    mois=mois_obj,
                    defaults={
                        'etat_mise_en_oeuvre': etat,
                        'livrable': livrable,
                        'date_realisation': date_real,
                    }
                )
                if s_created:
                    count_suivis += 1

        self.stdout.write(f'    -> {count_details} details, {count_suivis} suivis')
