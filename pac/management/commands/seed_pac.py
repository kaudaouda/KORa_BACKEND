from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files import File
import os
import datetime

from parametre.models import (
    Processus, Annee, Direction, SousDirection,
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
    {'nom': 'Recommandation', 'description': 'Action recommandee suite a un audit ou une revue'},
    {'nom': 'Non-conformite', 'description': 'Ecart constate par rapport a une exigence'},
    {'nom': 'Observation',    'description': 'Remarque ou point d attention releve'},
]

CATEGORIES = [
    {'nom': 'Organisationnelle', 'description': 'Liee a l organisation ou aux processus'},
    {'nom': 'Documentaire',      'description': 'Liee a la documentation ou aux procedures'},
    {'nom': 'Technique',         'description': 'Liee aux equipements ou systemes techniques'},
    {'nom': 'Humaine',           'description': 'Liee aux competences ou au comportement humain'},
]

SOURCES = [
    {'nom': 'Audit interne', 'description': 'Audit realise par l equipe interne'},
    {'nom': 'Audit externe', 'description': 'Audit realise par un organisme externe'},
]

DYSFONCTIONNEMENTS_TYPES = [
    {'nom': 'Dysfonctionnement', 'description': 'Dysfonctionnement constate necessitant une action corrective'},
    {'nom': 'Recommandation',    'description': 'Recommandation emise suite a un audit ou une revue'},
]

ACTION_TYPES = [
    {'nom': 'Corrective',   'description': 'Action visant a corriger une non-conformite'},
    {'nom': 'Preventive',   'description': 'Action visant a prevenir une non-conformite potentielle'},
    {'nom': 'Amelioration', 'description': 'Action visant a ameliorer un processus existant'},
]

STATUTS = [
    {'nom': 'Ouverte',    'description': 'Action en cours, non encore close'},
    {'nom': 'Cloturee',   'description': 'Action terminee et validee'},
    {'nom': 'Suspendue',  'description': 'Action temporairement mise en attente'},
]

# Processus a seeder (noms de processus)
PROCESSUS_NOMS = ['PRS-DAAF', 'PRS-SDARH', 'PRS-DSSC', 'PRS-DSF', 'PRS-DSV']

# Traitements generiques pour les details PAC
TRAITEMENTS = [
    {'action': 'Elaborer et valider une procedure documentee conforme aux exigences reglementaires', 'type': 'Corrective',   'delai_mois': 3},
    {'action': 'Mettre en place un tableau de bord de suivi avec des indicateurs de performance',    'type': 'Preventive',   'delai_mois': 2},
    {'action': 'Organiser une session de formation et de sensibilisation pour le personnel',         'type': 'Amelioration', 'delai_mois': 1},
    {'action': 'Realiser un audit interne de conformite et corriger les ecarts identifies',          'type': 'Corrective',   'delai_mois': 4},
]


class Command(BaseCommand):
    help = 'Seed les donnees PAC (referentiels, details et suivis)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed PAC'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('Aucun superutilisateur trouve. Creez-en un d abord.'))
            return

        self._seed_referentiels(user)
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
            self.stdout.write(f'  {"+" if created else "o"} Nature: {obj.nom}')

        for data in CATEGORIES:
            obj, created = Categorie.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            self.stdout.write(f'  {"+" if created else "o"} Categorie: {obj.nom}')

        for data in SOURCES:
            obj, created = Source.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            self.stdout.write(f'  {"+" if created else "o"} Source: {obj.nom}')

        for data in DYSFONCTIONNEMENTS_TYPES:
            obj, created = DysfonctionnementRecommandation.objects.get_or_create(
                nom=data['nom'],
                defaults={'cree_par': user, 'description': data['description']}
            )
            self.stdout.write(f'  {"+" if created else "o"} DysfonctionnementRecommandation: {obj.nom}')

        for data in ACTION_TYPES:
            obj, created = ActionType.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            self.stdout.write(f'  {"+" if created else "o"} ActionType: {obj.nom}')

        for data in STATUTS:
            obj, created = Statut.objects.get_or_create(nom=data['nom'], defaults={'description': data['description']})
            self.stdout.write(f'  {"+" if created else "o"} Statut: {obj.nom}')

    # -----------------------------------------------------------------------
    # PAC
    # -----------------------------------------------------------------------

    def _seed_pacs(self, user):
        processus_list = list(Processus.objects.filter(nom__in=PROCESSUS_NOMS))
        annees = list(Annee.objects.filter(annee__in=[2024, 2025]).order_by('annee'))

        if not processus_list:
            self.stdout.write(self.style.ERROR('Aucun processus trouve. Lancez d abord seed_anac_structure.'))
            return
        if not annees:
            self.stdout.write(self.style.ERROR('Aucune annee 2024/2025 trouvee. Lancez d abord seed_annees.'))
            return

        for processus in processus_list:
            self.stdout.write(self.style.SUCCESS(f'\n[PROCESSUS] {processus.numero_processus} - {processus.nom}'))

            for annee in annees:
                # PAC Initial
                pac_initial, created = Pac.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    num_amendement=0,
                    defaults={
                        'cree_par': user,
                        'is_validated': True,
                        'validated_by': user,
                        'validated_at': timezone.now(),
                    }
                )
                self.stdout.write(f'  {"+" if created else "o"} PAC Initial {annee.annee}')
                if created:
                    self._seed_details_pac(pac_initial, user, annee.annee)

                # PAC Amendement 1
                pac_amend, created_a = Pac.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    num_amendement=1,
                    defaults={
                        'cree_par': user,
                        'is_validated': True,
                        'validated_by': user,
                        'validated_at': timezone.now(),
                        'initial_ref': pac_initial,
                        'raison_amendement': f'Revision suite aux nouvelles constatations du suivi {annee.annee}',
                    }
                )
                self.stdout.write(f'  {"+" if created_a else "o"} PAC Amendement 1 {annee.annee}')
                if created_a:
                    self._seed_details_pac(pac_amend, user, annee.annee)

    def _seed_details_pac(self, pac, user, annee):
        """Cree les DetailsPac, TraitementPac et PacSuivi pour un PAC (4 details)."""
        natures       = list(Nature.objects.all())
        categories    = list(Categorie.objects.all())
        sources       = list(Source.objects.filter(is_active=True))
        action_types  = {at.nom: at for at in ActionType.objects.all()}
        etats         = {e.nom: e for e in EtatMiseEnOeuvre.objects.all()}
        appreciations = list(Appreciation.objects.all())
        statuts       = {s.nom: s for s in Statut.objects.all()}
        directions    = list(Direction.objects.all())
        sous_directions = list(SousDirection.objects.all())
        preuve_obj    = self._get_or_create_preuve()

        dysf_types = list(
            DysfonctionnementRecommandation.objects.filter(
                nom__in=['Dysfonctionnement', 'Recommandation'],
                is_active=True
            )
        )
        if not dysf_types:
            self.stdout.write(self.style.WARNING('  ! Aucun type Dysfonctionnement/Recommandation actif — details ignores'))
            return

        count_details = count_traitements = count_suivis = 0

        for i in range(4):
            dysf     = dysf_types[i % len(dysf_types)]
            nature   = natures[i % len(natures)]     if natures     else None
            categorie= categories[i % len(categories)] if categories else None
            source   = sources[i % len(sources)]     if sources     else None
            mois     = (i + 1) * 3  # 3, 6, 9, 12
            periode  = datetime.date(annee, mois, 28)

            detail, created = DetailsPac.objects.get_or_create(
                pac=pac,
                numero_pac=f'{pac.processus.numero_processus}-{annee}-{i + 1:02d}',
                defaults={
                    'libelle': f'{dysf.nom} #{i + 1} — {pac.processus.numero_processus}',
                    'dysfonctionnement_recommandation': dysf,
                    'nature':    nature,
                    'categorie': categorie,
                    'source':    source,
                    'periode_de_realisation': periode,
                }
            )
            if created:
                count_details += 1

            traitement_data = TRAITEMENTS[i % len(TRAITEMENTS)]
            action_type = action_types.get(traitement_data['type'])
            delai = datetime.date(annee, min(mois + traitement_data['delai_mois'], 12), 28)
            direction = directions[i % len(directions)] if directions else None
            sous_dir  = next(
                (s for s in sous_directions if direction and s.direction == direction),
                sous_directions[i % len(sous_directions)] if sous_directions else None
            )

            traitement, t_created = TraitementPac.objects.get_or_create(
                details_pac=detail,
                defaults={
                    'action':                    traitement_data['action'],
                    'type_action':               action_type,
                    'responsable_direction':     direction,
                    'responsable_sous_direction':sous_dir,
                    'preuve':                    preuve_obj,
                    'delai_realisation':         delai,
                }
            )
            if t_created:
                if direction:  traitement.responsables_directions.set([direction])
                if sous_dir:   traitement.responsables_sous_directions.set([sous_dir])
                count_traitements += 1

            # Suivi — uniquement pour les PAC valides
            if pac.is_validated and not PacSuivi.objects.filter(traitement=traitement).exists():
                etats_cycle  = ['Realisee', 'En cours', 'Partiellement realisee', 'Realisee']
                appre_cycle  = ['Satisfaisant', 'A ameliorer', 'Insuffisant', 'Tres satisfaisant']
                etat_nom     = etats_cycle[i % len(etats_cycle)]
                appre_nom    = appre_cycle[i % len(appre_cycle)]
                etat  = etats.get(etat_nom)
                appre = next((a for a in appreciations if a.nom == appre_nom), appreciations[0] if appreciations else None)
                statut_obj   = statuts.get('Cloturee' if etat_nom == 'Realisee' else 'Ouverte')
                date_eff     = datetime.date(annee, min(mois + 1, 12), 15) if etat_nom == 'Realisee' else None
                date_clo     = datetime.date(annee, min(mois + 1, 12), 28) if etat_nom == 'Realisee' else None

                if etat and appre:
                    _, s_created = PacSuivi.objects.get_or_create(
                        traitement=traitement,
                        defaults={
                            'etat_mise_en_oeuvre': etat,
                            'resultat': (
                                'Action realisee avec succes.'
                                if etat_nom == 'Realisee'
                                else 'Action en cours de realisation.'
                                if etat_nom == 'En cours'
                                else 'Action partiellement realisee.'
                            ),
                            'appreciation':                appre,
                            'preuve':                      preuve_obj,
                            'statut':                      statut_obj,
                            'date_mise_en_oeuvre_effective': date_eff,
                            'date_cloture':                date_clo,
                            'cree_par':                    user,
                        }
                    )
                    if s_created:
                        count_suivis += 1

        self.stdout.write(f'    -> {count_details} details, {count_traitements} traitements, {count_suivis} suivis')

    # -----------------------------------------------------------------------
    # Preuve PDF helper
    # -----------------------------------------------------------------------

    def _get_or_create_preuve(self):
        existing = Preuve.objects.filter(medias__fichier__icontains='preuve').first()
        if existing:
            return existing
        if not os.path.exists(PREUVE_PDF_PATH):
            self.stdout.write(self.style.WARNING(f'  ! Fichier preuve.pdf introuvable: {PREUVE_PDF_PATH}'))
            return None
        with open(PREUVE_PDF_PATH, 'rb') as f:
            media = Media()
            media.fichier.save('preuve.pdf', File(f), save=True)
        preuve = Preuve.objects.create(titre='Preuve PDF seed PAC')
        preuve.medias.add(media)
        return preuve
