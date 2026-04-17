from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.files import File
import os
import datetime

from parametre.models import (
    Processus, Direction, SousDirection,
    FrequenceRisque, GraviteRisque, CriticiteRisque, Risque,
    VersionEvaluationCDR, StatutActionCDR,
    Media, Preuve,
)
from cartographie_risque.models import (
    CDR, DetailsCDR, EvaluationRisque, PlanAction,
    PlanActionResponsable, SuiviAction,
)

PREUVE_PDF_PATH = os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', '..', 'medias', 'preuve.pdf'
)

# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------
FREQUENCES = [
    {'libelle': 'Rare', 'valeur': '1'},
    {'libelle': 'Occasionnel', 'valeur': '2'},
    {'libelle': 'Frequent', 'valeur': '3'},
    {'libelle': 'Tres frequent', 'valeur': '4'},
]

GRAVITES = [
    {'libelle': 'Negligeable', 'code': 'N'},
    {'libelle': 'Mineur', 'code': 'M'},
    {'libelle': 'Modere', 'code': 'MO'},
    {'libelle': 'Majeur', 'code': 'MJ'},
    {'libelle': 'Critique', 'code': 'C'},
]

CRITICITES = [
    {'libelle': 'Faible'},
    {'libelle': 'Moyenne'},
    {'libelle': 'Elevee'},
    {'libelle': 'Tres elevee'},
]

RISQUES = [
    {'libelle': 'Risque operationnel', 'description': 'Risque lie aux operations quotidiennes'},
    {'libelle': 'Risque reglementaire', 'description': 'Risque de non-conformite aux reglements'},
    {'libelle': 'Risque financier', 'description': 'Risque impactant les ressources financieres'},
    {'libelle': 'Risque securite', 'description': 'Risque impactant la securite aeronautique'},
    {'libelle': 'Risque RH', 'description': 'Risque lie aux ressources humaines'},
]

STATUTS_ACTION = [
    {'nom': 'En cours', 'description': 'Action en cours de realisation'},
    {'nom': 'Termine', 'description': 'Action completement realisee'},
    {'nom': 'Suspendu', 'description': 'Action temporairement suspendue'},
    {'nom': 'Annule', 'description': 'Action annulee'},
]

# ---------------------------------------------------------------------------
# Données CDR par processus
# ---------------------------------------------------------------------------
DETAILS_PAR_PROCESSUS = {
    'PRS-DAAF': [
        {
            'activites': 'Gestion budgetaire et comptable',
            'objectifs': 'Assurer une execution budgetaire conforme aux previsions',
            'risque': 'Depassement du budget alloue par sous-estimation des depenses reelles',
            'causes': 'Previsions insuffisantes, depenses imprevisibles, manque de suivi',
            'consequences': 'Blocage des operations, deficit budgetaire, sanctions administratives',
            'actions': [
                'Mettre en place un suivi mensuel des depenses avec alertes automatiques',
                'Renforcer la procedure de validation des engagements financiers',
            ],
        },
        {
            'activites': 'Gestion des ressources materielles',
            'objectifs': 'Optimiser l utilisation des ressources materielles de la direction',
            'risque': 'Deterioration prematuree des equipements par manque d entretien',
            'causes': 'Absence de plan d entretien preventif, budget insuffisant',
            'consequences': 'Pannes frequentes, couts de maintenance eleves, baisse de productivite',
            'actions': [
                'Elaborer un plan d entretien preventif annuel pour tous les equipements critiques',
                'Creer un inventaire informatise avec suivi des dates de maintenance',
            ],
        },
        {
            'activites': 'Gestion des marches et contrats',
            'objectifs': 'Assurer la conformite et la transparence des marches publics',
            'risque': 'Non-respect des procedures de passation des marches publics',
            'causes': 'Meconnaissance des textes reglementaires, urgence des besoins',
            'consequences': 'Risque juridique, sanctions, mauvaise utilisation des fonds',
            'actions': [
                'Former le personnel sur les procedures de marches publics',
                'Mettre en place une check-list de conformite pour chaque marche',
            ],
        },
    ],
    'PRS-SDARH': [
        {
            'activites': 'Gestion du personnel et des carrieres',
            'objectifs': 'Assurer une gestion transparente et equitable des carrieres',
            'risque': 'Depart de personnel cle non anticipe impactant la continuite du service',
            'causes': 'Absence de plan de succession, manque de retention des talents',
            'consequences': 'Perte de competences critiques, baisse de performance',
            'actions': [
                'Elaborer un plan de succession pour les postes cles',
                'Mettre en place un programme de fidelisation des talents',
            ],
        },
        {
            'activites': 'Formation et developpement des competences',
            'objectifs': 'Maintenir et ameliorer les competences du personnel ANAC',
            'risque': 'Obsolescence des competences par absence de formation continue',
            'causes': 'Budget formation insuffisant, manque de planification',
            'consequences': 'Degradation de la qualite du service, non-conformite aux exigences OACI',
            'actions': [
                'Elaborer un plan de formation annuel base sur les besoins identifies',
                'Developper un partenariat avec des organismes de formation certifies',
            ],
        },
        {
            'activites': 'Gestion des conflits et discipline',
            'objectifs': 'Maintenir un environnement de travail sain et productif',
            'risque': 'Augmentation des conflits internes non resolus perturbant le service',
            'causes': 'Absence de procedures de gestion des conflits, management inadequat',
            'consequences': 'Degradation du climat social, absenteisme, perte de productivite',
            'actions': [
                'Former les responsables aux techniques de mediation et gestion des conflits',
                'Mettre en place une procedure formelle de traitement des plaintes',
            ],
        },
    ],
    'PRS-DSSC': [
        {
            'activites': 'Surveillance de la securite des operations aeriennes',
            'objectifs': 'Assurer la conformite des operateurs aux exigences de securite',
            'risque': 'Defaillance dans la detection precoce des ecarts de securite',
            'causes': 'Insuffisance des inspections, outils de surveillance inadequats',
            'consequences': 'Accidents potentiels, suspension des operations, atteinte a la reputation',
            'actions': [
                'Augmenter la frequence des inspections de surveillance',
                'Developper un systeme de signalement proactif des defaillances',
            ],
        },
        {
            'activites': 'Gestion des rapports de securite',
            'objectifs': 'Traiter efficacement les rapports de securite dans les delais',
            'risque': 'Accumulation de rapports de securite non traites dans les delais',
            'causes': 'Sous-effectif, procedures de traitement inefficaces',
            'consequences': 'Risques securite non traites, non-conformite avec les normes OACI',
            'actions': [
                'Revoir les procedures de traitement des rapports pour reduire les delais',
                'Recruter du personnel supplementaire pour le traitement des rapports',
            ],
        },
        {
            'activites': 'Coordination avec les parties prenantes',
            'objectifs': 'Maintenir une coordination efficace avec les operateurs aeriens',
            'risque': 'Rupture de communication avec les compagnies aeriennes lors d une crise',
            'causes': 'Absence de protocoles de communication de crise, canaux inadaptes',
            'consequences': 'Retard dans la gestion de crise, escalade des incidents',
            'actions': [
                'Elaborer un protocole de communication de crise avec toutes les parties prenantes',
                'Organiser des exercices de simulation de crise annuels',
            ],
        },
    ],
    'PRS-DSF': [
        {
            'activites': 'Certification des aeronefs et des operateurs',
            'objectifs': 'Assurer la conformite des certifications aux normes en vigueur',
            'risque': 'Delivrance de certifications non conformes aux exigences OACI',
            'causes': 'Procedures de certification obsoletes, manque de formation des inspecteurs',
            'consequences': 'Risques pour la securite aerienne, sanctions internationales',
            'actions': [
                'Mettre a jour les procedures de certification conformement aux annexes OACI',
                'Former et habiliter les inspecteurs sur les nouvelles exigences',
            ],
        },
        {
            'activites': 'Inspection des infrastructures aeroportuaires',
            'objectifs': 'Maintenir la conformite des infrastructures aux normes de securite',
            'risque': 'Degradation des infrastructures non detectee lors des inspections',
            'causes': 'Frequence d inspection insuffisante, outils d evaluation inadequats',
            'consequences': 'Incidents aeroportuaires, fermeture d aeroport, penalites',
            'actions': [
                'Etablir un calendrier d inspection regulier avec des criteres precis',
                'Doter les equipes d inspection d outils modernes d evaluation',
            ],
        },
    ],
    'PRS-DSV': [
        {
            'activites': 'Delivrance et renouvellement des licences navigants',
            'objectifs': 'Assurer la conformite des licences aux standards internationaux',
            'risque': 'Delivrance de licences a des navigants ne remplissant pas toutes les conditions',
            'causes': 'Verification insuffisante des dossiers, pression des operateurs',
            'consequences': 'Mise en danger de la securite aerienne, responsabilite juridique',
            'actions': [
                'Mettre en place une double verification systematique des dossiers de licences',
                'Informatiser le processus de delivrance pour reduire les erreurs manuelles',
            ],
        },
        {
            'activites': 'Formation et evaluation des navigants',
            'objectifs': 'Garantir le niveau de competence des navigants en activite',
            'risque': 'Maintien en activite de navigants dont les competences sont inadequates',
            'causes': 'Evaluations insuffisamment rigoureuses, biais dans les evaluations',
            'consequences': 'Degradation de la securite des vols, incidents et accidents',
            'actions': [
                'Renforcer les criteres et procedures d evaluation des competences',
                'Former les examinateurs sur les methodes d evaluation objectives',
            ],
        },
        {
            'activites': 'Gestion du registre des licences',
            'objectifs': 'Maintenir un registre fiable et a jour de toutes les licences',
            'risque': 'Registre des licences incomplet ou contenant des erreurs',
            'causes': 'Systeme d information obsolete, saisie manuelle des donnees',
            'consequences': 'Erreurs dans les verifications, impossibilite de tracking',
            'actions': [
                'Deployer un systeme informatise de gestion des licences',
                'Mettre en place des procedures de verification periodique du registre',
            ],
        },
    ],
}


class Command(BaseCommand):
    help = 'Seed les donnees CDR (Cartographie des Risques) avec referentiels, details, evaluations et suivis'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed CDR - Cartographie des Risques'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('Aucun superutilisateur trouve.'))
            return

        self._seed_referentiels()
        self._seed_cdrs(user)

        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS('Seed CDR termine.'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}\n'))

    # -----------------------------------------------------------------------
    # Référentiels
    # -----------------------------------------------------------------------

    def _seed_referentiels(self):
        self.stdout.write(self.style.SUCCESS('\n[REFERENTIELS]'))

        for data in FREQUENCES:
            obj, created = FrequenceRisque.objects.get_or_create(
                libelle=data['libelle'], defaults={'valeur': data['valeur']}
            )
            self.stdout.write(f'  {"+" if created else "o"} FrequenceRisque: {obj.libelle}')

        for data in GRAVITES:
            obj, created = GraviteRisque.objects.get_or_create(
                libelle=data['libelle'], defaults={'code': data['code']}
            )
            self.stdout.write(f'  {"+" if created else "o"} GraviteRisque: {obj.libelle}')

        for data in CRITICITES:
            obj, created = CriticiteRisque.objects.get_or_create(libelle=data['libelle'])
            self.stdout.write(f'  {"+" if created else "o"} CriticiteRisque: {obj.libelle}')

        for data in RISQUES:
            obj, created = Risque.objects.get_or_create(
                libelle=data['libelle'], defaults={'description': data['description']}
            )
            self.stdout.write(f'  {"+" if created else "o"} Risque: {obj.libelle}')

        for data in STATUTS_ACTION:
            obj, created = StatutActionCDR.objects.get_or_create(
                nom=data['nom'], defaults={'description': data['description']}
            )
            self.stdout.write(f'  {"+" if created else "o"} StatutActionCDR: {obj.nom}')

    # -----------------------------------------------------------------------
    # CDR
    # -----------------------------------------------------------------------

    def _seed_cdrs(self, user):
        processus_list = list(Processus.objects.filter(nom__in=DETAILS_PAR_PROCESSUS.keys()))

        if not processus_list:
            self.stdout.write(self.style.ERROR('Aucun processus trouve.'))
            return

        for processus in processus_list:
            self.stdout.write(self.style.SUCCESS(f'\n[PROCESSUS] {processus.numero_processus} - {processus.nom}'))

            for annee in [2024, 2025]:
                # CDR Initial
                cdr_initial, created = CDR.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    num_amendement=0,
                    defaults={
                        'cree_par': user,
                        'is_validated': True,
                        'valide_par': user,
                        'date_validation': timezone.now(),
                    }
                )
                self.stdout.write(f'  {"+" if created else "o"} CDR Initial {annee}')
                self._seed_details_cdr(cdr_initial, processus.nom, annee, user)

                # CDR Amendement 1
                cdr_amend, created_a = CDR.objects.get_or_create(
                    processus=processus,
                    annee=annee,
                    num_amendement=1,
                    defaults={
                        'cree_par': user,
                        'is_validated': True,
                        'valide_par': user,
                        'date_validation': timezone.now(),
                        'initial_ref': cdr_initial,
                        'raison_amendement': f'Reevaluation des risques suite aux inspections du S2 {annee}',
                    }
                )
                self.stdout.write(f'  {"+" if created_a else "o"} CDR Amendement 1 {annee}')
                self._seed_reevaluations(cdr_amend, processus.nom, annee, user)

    def _seed_details_cdr(self, cdr, processus_nom, annee, user):
        """Crée les DetailsCDR avec evaluations et plans d'action pour un CDR."""
        details_data = DETAILS_PAR_PROCESSUS.get(processus_nom, [])
        frequences = list(FrequenceRisque.objects.all())
        gravites = list(GraviteRisque.objects.all())
        criticites = list(CriticiteRisque.objects.all())
        risques = list(Risque.objects.all())
        statuts = list(StatutActionCDR.objects.all())
        directions = list(Direction.objects.all())
        preuve = self._get_or_create_preuve()

        version_initiale = VersionEvaluationCDR.objects.filter(nom='Evaluation Initiale').first()
        if not version_initiale:
            version_initiale = VersionEvaluationCDR.objects.first()

        count_details = count_evals = count_plans = count_suivis = 0

        for i, data in enumerate(details_data):
            detail, created = DetailsCDR.objects.get_or_create(
                cdr=cdr,
                numero_cdr=f'{cdr.processus.numero_processus}-{annee}-{i + 1:02d}',
                defaults={
                    'activites': data['activites'],
                    'objectifs': data['objectifs'],
                    'evenements_indesirables_risques': data['risque'],
                    'causes': data['causes'],
                    'consequences': data['consequences'],
                }
            )
            if created:
                count_details += 1

            # Évaluation initiale
            if version_initiale and frequences and gravites and criticites and risques:
                freq = frequences[i % len(frequences)]
                grav = gravites[i % len(gravites)]
                crit = criticites[i % len(criticites)]
                risque = risques[i % len(risques)]

                eval_obj, e_created = EvaluationRisque.objects.get_or_create(
                    details_cdr=detail,
                    version_evaluation=version_initiale,
                    defaults={
                        'frequence': freq,
                        'gravite': grav,
                        'criticite': crit,
                        'risque': risque,
                    }
                )
                if e_created:
                    count_evals += 1

            # Plans d'action
            direction = directions[i % len(directions)] if directions else None
            delai = datetime.date(annee, min((i + 1) * 3, 12), 28)

            for j, action_text in enumerate(data.get('actions', [])):
                plan, p_created = PlanAction.objects.get_or_create(
                    details_cdr=detail,
                    actions_mesures=action_text,
                    defaults={
                        'responsable': direction,
                        'delai_realisation': delai,
                    }
                )
                if p_created:
                    count_plans += 1
                    # Responsable via GenericFK
                    if direction:
                        ct = ContentType.objects.get_for_model(Direction)
                        PlanActionResponsable.objects.get_or_create(
                            plan_action=plan,
                            content_type=ct,
                            object_id=direction.uuid,
                        )

                # Suivi de l'action
                if statuts:
                    statut_cycle = ['Termine', 'En cours', 'Termine', 'Suspendu']
                    statut = next(
                        (s for s in statuts if s.nom == statut_cycle[i % len(statut_cycle)]),
                        statuts[0]
                    )
                    is_done = statut.nom == 'Termine'
                    date_real = datetime.date(annee, min((i + 1) * 3, 12), 15) if is_done else datetime.date(annee, min((i + 1) * 3 + 1, 12), 10)
                    date_clo = datetime.date(annee, min((i + 1) * 3, 12), 28) if is_done else None

                    resultats_map = {
                        'Termine': 'Action realisee avec succes. Les criteres d efficacite sont satisfaits et la conformite a ete verifiee par inspection.',
                        'En cours': 'Action en cours de realisation. Les premieres etapes ont ete franchies avec succes. Finalisation prevue dans les delais.',
                        'Suspendu': 'Action temporairement suspendue en attente de ressources complementaires. Reprise prevue apres validation budgetaire.',
                        'Annule': 'Action annulee suite a un changement de contexte reglementaire. Une nouvelle action de remplacement a ete definie.',
                    }

                    suivi, s_created = SuiviAction.objects.get_or_create(
                        plan_action=plan,
                        defaults={
                            'statut_action': statut,
                            'date_realisation': date_real,
                            'date_cloture': date_clo,
                            'element_preuve': preuve,
                            'critere_efficacite_objectif_vise': (
                                f'{data["objectifs"]} — Verification par audit interne et revue documentaire.'
                            ),
                            'resultats_mise_en_oeuvre': resultats_map.get(statut.nom, 'Action en cours.'),
                        }
                    )
                    if s_created:
                        count_suivis += 1

        self.stdout.write(
            f'    -> {count_details} details, {count_evals} evaluations, '
            f'{count_plans} plans action, {count_suivis} suivis'
        )

    def _seed_reevaluations(self, cdr_amend, processus_nom, annee, user):
        """Crée de nouvelles évaluations (réévaluations) pour les détails d'un CDR amendement."""
        details_data = DETAILS_PAR_PROCESSUS.get(processus_nom, [])
        frequences = list(FrequenceRisque.objects.all())
        gravites = list(GraviteRisque.objects.all())
        criticites = list(CriticiteRisque.objects.all())
        risques = list(Risque.objects.all())
        statuts = list(StatutActionCDR.objects.all())
        directions = list(Direction.objects.all())
        preuve = self._get_or_create_preuve()

        version_reeval = VersionEvaluationCDR.objects.filter(nom='Reevaluation 1').first()
        if not version_reeval:
            version_reeval = VersionEvaluationCDR.objects.exclude(nom='Evaluation Initiale').first()

        count_details = count_evals = count_plans = count_suivis = 0

        resultats_map = {
            'Termine': 'Action realisee avec succes apres reevaluation. Criticite reduite, conformite verifiee.',
            'En cours': 'Action d amendement en cours. Les mesures correctives montrent des resultats positifs.',
            'Suspendu': 'Action suspendue temporairement. Reevaluation du plan d action en cours.',
            'Annule': 'Action annulee. Une approche alternative a ete retenue.',
        }

        for i, data in enumerate(details_data):
            detail, created = DetailsCDR.objects.get_or_create(
                cdr=cdr_amend,
                numero_cdr=f'{cdr_amend.processus.numero_processus}-{annee}-A1-{i + 1:02d}',
                defaults={
                    'activites': data['activites'],
                    'objectifs': data['objectifs'],
                    'evenements_indesirables_risques': data['risque'],
                    'causes': data['causes'],
                    'consequences': data['consequences'],
                }
            )
            if created:
                count_details += 1

            # Réévaluation — criticité généralement réduite après les actions
            if version_reeval and frequences and gravites and criticites and risques:
                crit_idx = max(0, (i % len(criticites)) - 1)
                freq = frequences[max(0, (i % len(frequences)) - 1)]
                grav = gravites[max(0, (i % len(gravites)) - 1)]
                crit = criticites[crit_idx]
                risque = risques[i % len(risques)]

                eval_obj, e_created = EvaluationRisque.objects.get_or_create(
                    details_cdr=detail,
                    version_evaluation=version_reeval,
                    defaults={
                        'frequence': freq,
                        'gravite': grav,
                        'criticite': crit,
                        'risque': risque,
                    }
                )
                if e_created:
                    count_evals += 1

            # Plan d'action amendé
            direction = directions[i % len(directions)] if directions else None
            delai = datetime.date(annee, min((i + 1) * 3, 12), 28)
            action_text = data["actions"][0]

            plan, p_created = PlanAction.objects.get_or_create(
                details_cdr=detail,
                actions_mesures=action_text,
                defaults={
                    'responsable': direction,
                    'delai_realisation': delai,
                }
            )
            if p_created:
                count_plans += 1
                if direction:
                    ct = ContentType.objects.get_for_model(Direction)
                    PlanActionResponsable.objects.get_or_create(
                        plan_action=plan,
                        content_type=ct,
                        object_id=direction.uuid,
                    )

            # Suivi de l'action d'amendement
            if statuts:
                statut_cycle = ['Termine', 'Termine', 'En cours', 'Termine']
                statut = next(
                    (s for s in statuts if s.nom == statut_cycle[i % len(statut_cycle)]),
                    statuts[0]
                )
                is_done = statut.nom == 'Termine'
                date_real = datetime.date(annee, min((i + 1) * 3, 12), 20) if is_done else datetime.date(annee, min((i + 1) * 3 + 1, 12), 10)
                date_clo = datetime.date(annee, min((i + 1) * 3, 12), 28) if is_done else None

                suivi, s_created = SuiviAction.objects.get_or_create(
                    plan_action=plan,
                    defaults={
                        'statut_action': statut,
                        'date_realisation': date_real,
                        'date_cloture': date_clo,
                        'element_preuve': preuve,
                        'critere_efficacite_objectif_vise': (
                            f'{data["objectifs"]} — Reevaluation apres amendement et verification sur site.'
                        ),
                        'resultats_mise_en_oeuvre': resultats_map.get(statut.nom, 'Action en cours.'),
                    }
                )
                if s_created:
                    count_suivis += 1

        self.stdout.write(
            f'    -> {count_details} details amend, {count_evals} reevaluations, '
            f'{count_plans} plans action, {count_suivis} suivis'
        )

    # -----------------------------------------------------------------------
    # Preuve PDF helper
    # -----------------------------------------------------------------------

    def _get_or_create_preuve(self):
        existing = Preuve.objects.filter(medias__fichier__icontains='preuve').first()
        if existing:
            return existing

        if not os.path.exists(PREUVE_PDF_PATH):
            self.stdout.write(self.style.WARNING(f'  ! preuve.pdf introuvable: {PREUVE_PDF_PATH}'))
            return None

        with open(PREUVE_PDF_PATH, 'rb') as f:
            media = Media()
            media.fichier.save('preuve.pdf', File(f), save=True)

        preuve = Preuve.objects.create(titre='Preuve PDF seed CDR')
        preuve.medias.add(media)
        return preuve
