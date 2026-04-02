from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files import File
import os
import datetime

from parametre.models import (
    Processus, Versions, Annee, Direction, SousDirection,
    Nature, Categorie, Source, ActionType, Statut,
    EtatMiseEnOeuvre, Appreciation,
    DysfonctionnementRecommandation, Media, Preuve,
)
from pac.models import Pac, DetailsPac, TraitementPac, PacSuivi

PREUVE_PDF_PATH = os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', '..', 'medias', 'preuve.pdf'
)

# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------
NATURES = [
    {'nom': 'Recommandation', 'description': 'Action recommandée suite à un audit ou une revue'},
    {'nom': 'Non-conformite', 'description': 'Ecart constaté par rapport à une exigence'},
    {'nom': 'Observation', 'description': 'Remarque ou point d attention relevé'},
]

CATEGORIES = [
    {'nom': 'Organisationnelle', 'description': 'Liée à l organisation ou aux processus'},
    {'nom': 'Documentaire', 'description': 'Liée à la documentation ou aux procédures'},
    {'nom': 'Technique', 'description': 'Liée aux équipements ou systèmes techniques'},
    {'nom': 'Humaine', 'description': 'Liée aux compétences ou au comportement humain'},
]

SOURCES = [
    {'nom': 'Audit interne', 'description': 'Audit réalisé par l équipe interne'},
    {'nom': 'Revue de processus', 'description': 'Revue périodique des processus'},
    {'nom': 'Audit externe', 'description': 'Audit réalisé par un organisme externe'},
    {'nom': 'Inspection OACI', 'description': 'Inspection réalisée par l OACI'},
    {'nom': 'Auto-evaluation', 'description': 'Evaluation réalisée par le responsable du processus'},
]

ACTION_TYPES = [
    {'nom': 'Corrective', 'description': 'Action visant à corriger une non-conformité'},
    {'nom': 'Preventive', 'description': 'Action visant à prévenir une non-conformité potentielle'},
    {'nom': 'Amelioration', 'description': 'Action visant à améliorer un processus existant'},
]

STATUTS = [
    {'nom': 'Ouverte', 'description': 'Action en cours, non encore close'},
    {'nom': 'Cloturee', 'description': 'Action terminée et validée'},
    {'nom': 'Suspendue', 'description': 'Action temporairement mise en attente'},
]

# ---------------------------------------------------------------------------
# Dysfonctionnements / recommandations par processus
# ---------------------------------------------------------------------------
DYSFUNCTIONS_PAR_PROCESSUS = {
    'PRS-DAAF': [
        'Absence de procedure documentee pour le suivi budgetaire',
        'Delais de traitement des factures non respectes',
        'Lacunes dans la gestion des archives comptables',
        'Formation insuffisante du personnel sur les outils financiers',
    ],
    'PRS-SDARH': [
        'Plan de formation annuel non etabli dans les delais',
        'Evaluation du personnel non realisee de facon systematique',
        'Absence de criteres objectifs pour les promotions internes',
        'Gestion des conges non informatisee',
    ],
    'PRS-DSSC': [
        'Procedure de surveillance non mise a jour',
        'Rapports de supervision remis hors delai',
        'Defaillances dans le suivi des ecarts de securite',
        'Manque de coordination avec les compagnies aeriennes',
    ],
    'PRS-DSF': [
        'Inspection des infrastructures aeroportuaires insuffisante',
        'Procedure de certification non conforme aux normes OACI',
        'Manque de personnel qualifie pour les inspections techniques',
        'Documentation technique obsolete',
    ],
    'PRS-DSV': [
        'Absence de procedure de validation des navigateurs',
        'Retards dans le traitement des demandes de licence',
        'Systeme de suivi des licences non informatise',
        'Formation theorique insuffisante pour les examinateurs',
    ],
}

# Traitements associés aux dysfonctionnements (par type)
TRAITEMENTS = [
    {
        'action': 'Elaborer et valider une procedure documentee conforme aux exigences reglementaires',
        'type': 'Corrective',
        'delai_mois': 3,
    },
    {
        'action': 'Mettre en place un tableau de bord de suivi avec des indicateurs de performance cles',
        'type': 'Preventive',
        'delai_mois': 2,
    },
    {
        'action': 'Organiser une session de formation et de sensibilisation pour le personnel concerne',
        'type': 'Amelioration',
        'delai_mois': 1,
    },
    {
        'action': 'Realiser un audit interne de conformite et corriger les ecarts identifies',
        'type': 'Corrective',
        'delai_mois': 4,
    },
]


class Command(BaseCommand):
    help = 'Seed les donnees PAC (Plans d Action Corrective) avec referentiels, details et suivis'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed PAC'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('Aucun superutilisateur trouve. Creez-en un d abord.'))
            return

        # 1. Referentiels
        self._seed_referentiels(user)

        # 2. PAC
        self._seed_pacs(user)

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed PAC termine.'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

    # -----------------------------------------------------------------------
    # Référentiels
    # -----------------------------------------------------------------------

    def _seed_referentiels(self, user):
        self.stdout.write(self.style.SUCCESS('\n[REFERENTIELS]'))

        for data in NATURES:
            obj, created = Nature.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            prefix = '+' if created else 'o'
            self.stdout.write(f'  {prefix} Nature: {obj.nom}')

        for data in CATEGORIES:
            obj, created = Categorie.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            prefix = '+' if created else 'o'
            self.stdout.write(f'  {prefix} Categorie: {obj.nom}')

        for data in SOURCES:
            obj, created = Source.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            prefix = '+' if created else 'o'
            self.stdout.write(f'  {prefix} Source: {obj.nom}')

        for data in ACTION_TYPES:
            obj, created = ActionType.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            prefix = '+' if created else 'o'
            self.stdout.write(f'  {prefix} ActionType: {obj.nom}')

        for data in STATUTS:
            obj, created = Statut.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            prefix = '+' if created else 'o'
            self.stdout.write(f'  {prefix} Statut: {obj.nom}')

        # Dysfonctionnements/Recommandations
        all_dysfs = [d for dysfuncs in DYSFUNCTIONS_PAR_PROCESSUS.values() for d in dysfuncs]
        for nom in all_dysfs:
            obj, created = DysfonctionnementRecommandation.objects.get_or_create(
                nom=nom,
                defaults={'cree_par': user}
            )
            if created:
                self.stdout.write(f'  + DysfonctionnementRecommandation: {obj.nom[:60]}')

    # -----------------------------------------------------------------------
    # PAC
    # -----------------------------------------------------------------------

    def _seed_pacs(self, user):
        processus_list = list(Processus.objects.filter(nom__in=DYSFUNCTIONS_PAR_PROCESSUS.keys()))
        version_initial = Versions.objects.get(code='INITIAL')
        version_amend1 = Versions.objects.get(code='AMENDEMENT_1')
        annees = list(Annee.objects.filter(annee__in=[2024, 2025]).order_by('annee'))

        if not processus_list:
            self.stdout.write(self.style.ERROR('Aucun processus trouve. Lancez d abord seed_anac_structure.'))
            return
        if not annees:
            self.stdout.write(self.style.ERROR('Aucune annee 2024/2025 trouvee. Lancez d abord seed_annees.'))
            return

        for processus in processus_list:
            self.stdout.write(self.style.SUCCESS(f'\n[PROCESSUS] {processus.numero_processus} - {processus.nom}'))
            dysfuncs = DYSFUNCTIONS_PAR_PROCESSUS.get(processus.nom, [])

            for annee in annees:
                # PAC Initial
                pac_initial, created = Pac.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    type_tableau=version_initial,
                    defaults={
                        'cree_par': user,
                        'is_validated': True,
                        'validated_by': user,
                        'validated_at': timezone.now(),
                    }
                )
                prefix = '+' if created else 'o'
                self.stdout.write(f'  {prefix} PAC Initial {annee.annee}')

                if created:
                    self._seed_details_pac(pac_initial, dysfuncs, user, annee.annee)

                # PAC Amendement 1
                pac_amend, created_a = Pac.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    type_tableau=version_amend1,
                    defaults={
                        'cree_par': user,
                        'is_validated': True,
                        'validated_by': user,
                        'validated_at': timezone.now(),
                        'initial_ref': pac_initial,
                        'raison_amendement': f'Revision suite aux nouvelles constatations du suivi {annee.annee}',
                    }
                )
                prefix = '+' if created_a else 'o'
                self.stdout.write(f'  {prefix} PAC Amendement 1 {annee.annee}')

                if created_a and len(dysfuncs) > 2:
                    self._seed_details_pac(pac_amend, dysfuncs[2:], user, annee.annee)

    def _seed_details_pac(self, pac, dysfuncs, user, annee):
        """Crée les DetailsPac, TraitementPac et PacSuivi pour un PAC."""
        natures = list(Nature.objects.all())
        categories = list(Categorie.objects.all())
        sources = list(Source.objects.all())
        action_types = {at.nom: at for at in ActionType.objects.all()}
        etats = {e.nom: e for e in EtatMiseEnOeuvre.objects.all()}
        appreciations = list(Appreciation.objects.all())
        statuts = {s.nom: s for s in Statut.objects.all()}
        directions = list(Direction.objects.all())
        sous_directions = list(SousDirection.objects.all())

        preuve_obj = self._get_or_create_preuve()

        count_details = 0
        count_traitements = 0
        count_suivis = 0

        for i, dysf_nom in enumerate(dysfuncs[:4]):  # max 4 details par PAC
            try:
                dysf = DysfonctionnementRecommandation.objects.get(nom=dysf_nom)
            except DysfonctionnementRecommandation.DoesNotExist:
                continue

            nature = natures[i % len(natures)] if natures else None
            categorie = categories[i % len(categories)] if categories else None
            source = sources[i % len(sources)] if sources else None

            # Période de réalisation : dans l'année (trimestre i+1)
            mois = (i + 1) * 3  # 3, 6, 9, 12
            periode = datetime.date(annee, mois, 30 if mois in [6, 9] else 31 if mois == 12 else 31)

            detail, created = DetailsPac.objects.get_or_create(
                pac=pac,
                dysfonctionnement_recommandation=dysf,
                defaults={
                    'numero_pac': f'{pac.processus.numero_processus}-{annee}-{i + 1:02d}',
                    'libelle': dysf_nom,
                    'nature': nature,
                    'categorie': categorie,
                    'source': source,
                    'periode_de_realisation': periode,
                }
            )
            if created:
                count_details += 1

            # Traitement
            traitement_data = TRAITEMENTS[i % len(TRAITEMENTS)]
            action_type = action_types.get(traitement_data['type'])
            delai = datetime.date(annee, min(mois + traitement_data['delai_mois'], 12), 28)

            direction = directions[i % len(directions)] if directions else None
            sous_dir = next(
                (s for s in sous_directions if direction and s.direction == direction),
                sous_directions[i % len(sous_directions)] if sous_directions else None
            )

            traitement, t_created = TraitementPac.objects.get_or_create(
                details_pac=detail,
                defaults={
                    'action': traitement_data['action'],
                    'type_action': action_type,
                    'responsable_direction': direction,
                    'responsable_sous_direction': sous_dir,
                    'preuve': preuve_obj,
                    'delai_realisation': delai,
                }
            )
            if t_created:
                if direction:
                    traitement.responsables_directions.set([direction])
                if sous_dir:
                    traitement.responsables_sous_directions.set([sous_dir])
                count_traitements += 1

            # Suivi — uniquement pour les PAC validés
            if pac.is_validated and not hasattr(traitement, 'suivi') or not PacSuivi.objects.filter(traitement=traitement).exists():
                # Alterner les états : Realisee, En cours, Partiellement realisee, Realisee
                etats_cycle = ['Realisee', 'En cours', 'Partiellement realisee', 'Realisee']
                appre_cycle = ['Satisfaisant', 'A ameliorer', 'Insuffisant', 'Tres satisfaisant']

                etat_nom = etats_cycle[i % len(etats_cycle)]
                appre_nom = appre_cycle[i % len(appre_cycle)]

                etat = etats.get(etat_nom)
                appre = next((a for a in appreciations if a.nom == appre_nom), appreciations[0] if appreciations else None)
                statut_cloture = statuts.get('Cloturee') if etat_nom == 'Realisee' else statuts.get('Ouverte')

                date_effective = datetime.date(annee, min(mois + 1, 12), 15) if etat_nom == 'Realisee' else None
                date_cloture = datetime.date(annee, min(mois + 1, 12), 28) if etat_nom == 'Realisee' else None

                if etat and appre:
                    suivi, s_created = PacSuivi.objects.get_or_create(
                        traitement=traitement,
                        defaults={
                            'etat_mise_en_oeuvre': etat,
                            'resultat': (
                                'Action realisee avec succes. Les objectifs sont atteints.'
                                if etat_nom == 'Realisee'
                                else 'Action en cours de realisation. Des progres sont constates.'
                                if etat_nom == 'En cours'
                                else 'Action partiellement realisee. Des points restent a traiter.'
                            ),
                            'appreciation': appre,
                            'preuve': preuve_obj,
                            'statut': statut_cloture,
                            'date_mise_en_oeuvre_effective': date_effective,
                            'date_cloture': date_cloture,
                            'cree_par': user,
                        }
                    )
                    if s_created:
                        count_suivis += 1

        self.stdout.write(
            f'    -> {count_details} details, {count_traitements} traitements, {count_suivis} suivis'
        )

    # -----------------------------------------------------------------------
    # Preuve PDF helper
    # -----------------------------------------------------------------------

    def _get_or_create_preuve(self):
        """Retourne une Preuve existante ou en crée une nouvelle avec le PDF."""
        existing = Preuve.objects.filter(medias__fichier__icontains='preuve').first()
        if existing:
            return existing

        if not os.path.exists(PREUVE_PDF_PATH):
            self.stdout.write(self.style.WARNING(f'  ! Fichier preuve.pdf introuvable: {PREUVE_PDF_PATH}'))
            return None

        with open(PREUVE_PDF_PATH, 'rb') as f:
            media = Media()
            media.fichier.save('preuve.pdf', File(f), save=True)

        preuve = Preuve.objects.create(description='Preuve PDF seed PAC')
        preuve.medias.add(media)
        return preuve
