from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from pac.models import Pac, Traitement, Suivi
from parametre.models import (
    Processus, Nature, Categorie, Source,
    ActionType, Direction, SousDirection,
    Preuve, Media, EtatMiseEnOeuvre, Appreciation, Statut,
    DysfonctionnementRecommandation,
)

from datetime import timedelta


class Command(BaseCommand):
    help = "Crée un PAC complet de démonstration avec traitements, suivis et preuves."

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email de l\'utilisateur créateur. Si absent, utilise cyberjunkies@mail.com')
        parser.add_argument('--with-media', action='store_true', help='Associer des médias de démonstration aux preuves')
        parser.add_argument('--count', type=int, default=5, help='Nombre de PACs à créer (défaut: 5)')

    def handle(self, *args, **options):
        email = options.get('email', 'cyberjunkies@mail.com')
        with_media = options.get('with_media', False)
        count = options.get('count', 5)

        user = self._get_or_create_user_by_email(email)
        refs = self._ensure_reference_data(user)

        pacs_created = []
        for i in range(count):
            with transaction.atomic():
                pac = self._create_pac(user, refs, index=i)
                traitements = self._create_traitements(pac, refs, with_media, index=i)
                self._create_suivis(traitements, refs, user, with_media)
                pacs_created.append(pac)

        self.stdout.write(self.style.SUCCESS(f"{count} PAC(s) créé(s) pour {user.email}:"))
        for pac in pacs_created:
            self.stdout.write(f"  - {pac.numero_pac} ({pac.uuid})")

    # ======================= Helpers =======================
    def _get_or_create_user_by_email(self, email: str) -> User:
        """Récupère ou crée un utilisateur par email."""
        user = User.objects.filter(email=email).first()
        if user:
            return user
        
        # Créer l'utilisateur s'il n'existe pas
        username = email.split('@')[0]
        # S'assurer que le username est unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password='password123',
            first_name='Cyber',
            last_name='Junkies'
        )
        self.stdout.write(self.style.WARNING(f"Utilisateur créé: {email} (username: {username})"))
        return user

    def _ensure_reference_data(self, user: User):
        # Créer plusieurs natures
        natures = []
        nature_data = [
            ('Recommandation', 'Recommandation d\'amélioration'),
            ('Non-conformité', 'Non-conformité détectée'),
            ('Observation', 'Observation relevée lors d\'audit'),
        ]
        for nom, desc in nature_data:
            nat, _ = Nature.objects.get_or_create(nom=nom, defaults={'description': desc})
            natures.append(nat)

        # Créer plusieurs catégories
        categories = []
        cat_data = [
            ('Qualité', 'Gestion de la qualité'),
            ('Sécurité', 'Sécurité et prévention'),
            ('Environnement', 'Management environnemental'),
            ('Documentation', 'Gestion documentaire'),
            ('Formation', 'Formation et compétences'),
        ]
        for nom, desc in cat_data:
            cat, _ = Categorie.objects.get_or_create(nom=nom, defaults={'description': desc})
            categories.append(cat)

        # Créer plusieurs sources
        sources = []
        source_data = [
            ('Audit interne', 'Audit interne annuel'),
            ('Audit externe', 'Audit de certification'),
            ('Revue de direction', 'Revue de direction trimestrielle'),
            ('Inspection réglementaire', 'Inspection par l\'autorité'),
            ('Réclamation client', 'Réclamation client'),
        ]
        for nom, desc in source_data:
            src, _ = Source.objects.get_or_create(nom=nom, defaults={'description': desc})
            sources.append(src)

        # Créer plusieurs types d'action
        action_types = []
        action_data = [
            ('Corrective', 'Action corrective'),
            ('Préventive', 'Action préventive'),
            ('Amélioration', 'Action d\'amélioration'),
        ]
        for nom, desc in action_data:
            act, _ = ActionType.objects.get_or_create(nom=nom, defaults={'description': desc})
            action_types.append(act)

        # États et appréciations
        etat_en_cours, _ = EtatMiseEnOeuvre.objects.get_or_create(nom='En cours')
        etat_realisee, _ = EtatMiseEnOeuvre.objects.get_or_create(nom='Réalisée')
        appreciation_sat, _ = Appreciation.objects.get_or_create(nom='Satisfaisant')
        appreciation_non_sat, _ = Appreciation.objects.get_or_create(nom='Non satisfaisant')
        statut_ouvert, _ = Statut.objects.get_or_create(nom='Ouverte')
        statut_cloture, _ = Statut.objects.get_or_create(nom='Clôturée')

        # Créer plusieurs processus
        processus_list = []
        processus_data = [
            ('Amélioration continue', 'Processus d\'amélioration continue'),
            ('Management des ressources', 'Gestion des ressources humaines et matérielles'),
            ('Réalisation du produit', 'Processus de réalisation'),
            ('Mesure et analyse', 'Mesure, analyse et amélioration'),
            ('Relation client', 'Gestion de la relation client'),
        ]
        for nom, desc in processus_data:
            proc, _ = Processus.objects.get_or_create(
                nom=nom,
                defaults={'description': desc, 'cree_par': user}
            )
            if not proc.cree_par_id:
                proc.cree_par = user
                proc.save(update_fields=['cree_par'])
            processus_list.append(proc)

        # Créer plusieurs directions et sous-directions
        directions_data = [
            ('Direction Qualité', ['Contrôle interne', 'Assurance qualité', 'Audit']),
            ('Direction Technique', ['Production', 'Maintenance', 'R&D']),
            ('Direction Commerciale', ['Ventes', 'Marketing', 'Service client']),
            ('Direction RH', ['Formation', 'Recrutement', 'Administration du personnel']),
            ('Direction Générale', ['Stratégie', 'Communication', 'Finances']),
        ]
        
        directions = []
        sous_directions_all = []
        for dir_nom, sous_dirs in directions_data:
            dir_obj, _ = Direction.objects.get_or_create(nom=dir_nom)
            directions.append(dir_obj)
            for sd_nom in sous_dirs:
                sd, _ = SousDirection.objects.get_or_create(
                    direction=dir_obj,
                    nom=sd_nom
                )
                sous_directions_all.append(sd)

        # Créer plusieurs dysfonctionnements
        dysfonctionnements = []
        dys_data = [
            ('Non-conformité procédure', 'Procédure non respectée'),
            ('Écart de documentation', 'Documentation obsolète ou manquante'),
            ('Défaut de traçabilité', 'Traçabilité insuffisante'),
            ('Non-conformité produit', 'Produit non conforme aux spécifications'),
            ('Manquement formation', 'Personnel insuffisamment formé'),
        ]
        for nom, desc in dys_data:
            dys, _ = DysfonctionnementRecommandation.objects.get_or_create(
                nom=nom,
                defaults={'description': desc, 'cree_par': user}
            )
            if not dys.cree_par_id:
                dys.cree_par = user
                dys.save(update_fields=['cree_par'])
            dysfonctionnements.append(dys)

        return {
            'natures': natures,
            'categories': categories,
            'sources': sources,
            'action_types': action_types,
            'etat_en_cours': etat_en_cours,
            'etat_realisee': etat_realisee,
            'appreciation_sat': appreciation_sat,
            'appreciation_non_sat': appreciation_non_sat,
            'statut_ouvert': statut_ouvert,
            'statut_cloture': statut_cloture,
            'processus_list': processus_list,
            'directions': directions,
            'sous_directions_all': sous_directions_all,
            'dysfonctionnements': dysfonctionnements,
        }

    def _create_pac(self, user: User, refs, index: int = 0) -> Pac:
        today = timezone.now().date()
        
        # Varier les libellés de manière significative
        libelles = [
            'Mise en conformité de la procédure de traçabilité des matières premières',
            'Révision complète du système documentaire qualité suite à audit externe',
            'Renforcement des mesures de sécurité au poste de travail',
            'Optimisation du processus de gestion des réclamations clients',
            'Amélioration de la formation du personnel sur les bonnes pratiques de fabrication',
            'Mise à jour du plan de maintenance préventive des équipements critiques',
            'Révision des procédures d\'urgence et plans d\'évacuation',
            'Amélioration de la gestion des non-conformités produits',
            'Renforcement du contrôle qualité des fournisseurs',
            'Optimisation de la communication interne entre services',
        ]
        
        # Sélectionner des références variées en fonction de l'index
        processus = refs['processus_list'][index % len(refs['processus_list'])]
        nature = refs['natures'][index % len(refs['natures'])]
        categorie = refs['categories'][index % len(refs['categories'])]
        source = refs['sources'][index % len(refs['sources'])]
        dysfonctionnement = refs['dysfonctionnements'][index % len(refs['dysfonctionnements'])]
        
        pac = Pac.objects.create(
            numero_pac=self._generate_numero_pac(),
            processus=processus,
            libelle=libelles[index % len(libelles)],
            nature=nature,
            categorie=categorie,
            source=source,
            dysfonctionnement_recommandation=dysfonctionnement,
            periode_de_realisation=today + timedelta(days=14 + (index * 7)),
            cree_par=user,
        )
        return pac

    def _generate_numero_pac(self) -> str:
        count = Pac.objects.count()
        numero = f"PAC{count + 1:04d}"
        while Pac.objects.filter(numero_pac=numero).exists():
            count += 1
            numero = f"PAC{count + 1:04d}"
        return numero

    def _create_traitements(self, pac: Pac, refs, with_media: bool, index: int = 0):
        today = timezone.now().date()
        
        # Actions très variées et détaillées
        actions_1 = [
            'Réviser et valider la procédure de traçabilité en intégrant les nouvelles exigences ISO',
            'Mettre à jour le manuel qualité sections 4.2 à 4.8 selon les recommandations de l\'audit',
            'Documenter l\'ensemble des processus critiques avec organigrammes et responsabilités',
            'Réviser les instructions de travail des postes de production avec validation terrain',
            'Actualiser la documentation technique des équipements de mesure et de contrôle',
            'Réaliser un diagnostic complet du système documentaire et identifier les écarts',
            'Élaborer un plan d\'action pour la mise en conformité réglementaire',
            'Mettre en place un système de gestion des compétences par poste',
            'Développer des indicateurs de performance pour le suivi de la qualité',
            'Créer une base de données centralisée pour la gestion des non-conformités',
        ]
        actions_2 = [
            'Former l\'ensemble du personnel concerné sur les nouvelles procédures (3 sessions minimum)',
            'Organiser des sessions de sensibilisation aux risques qualité et sécurité',
            'Déployer les nouveaux outils de suivi avec accompagnement des utilisateurs',
            'Former les responsables d\'équipe aux nouvelles normes et méthodes d\'audit',
            'Communiquer les changements à toutes les parties prenantes internes et externes',
            'Réaliser des audits internes pour vérifier l\'efficacité des actions mises en place',
            'Mettre en place un système de retour d\'expérience et d\'amélioration continue',
            'Élaborer et diffuser des supports pédagogiques (guides, vidéos, fiches pratiques)',
            'Organiser des ateliers de co-construction avec les équipes opérationnelles',
            'Mettre en place un suivi mensuel des indicateurs avec revue de direction',
        ]

        preuve1 = None
        preuve2 = None
        if with_media:
            media1 = Media.objects.create(url_fichier='/medias/Document_sans_titre-3.pdf')
            media2 = Media.objects.create(url_fichier='/medias/Decharge.pdf')
            preuve1 = Preuve.objects.create(description='Procédure mise à jour signée')
            preuve2 = Preuve.objects.create(description='Attestation de formation')
            preuve1.medias.add(media1)
            preuve2.medias.add(media2)

        # Varier les directions et sous-directions
        direction_index = index % len(refs['directions'])
        direction = refs['directions'][direction_index]
        
        # Sélectionner des sous-directions de cette direction si possible
        sous_directions_de_direction = [sd for sd in refs['sous_directions_all'] if sd.direction == direction]
        if sous_directions_de_direction:
            sous_direction = sous_directions_de_direction[0]
        else:
            sous_direction = refs['sous_directions_all'][index % len(refs['sous_directions_all'])]

        # Varier les types d'action
        action_type_1 = refs['action_types'][index % len(refs['action_types'])]
        action_type_2 = refs['action_types'][(index + 1) % len(refs['action_types'])]

        t1 = Traitement.objects.create(
            pac=pac,
            action=actions_1[index % len(actions_1)],
            type_action=action_type_1,
            responsable_direction=direction,
            responsable_sous_direction=sous_direction,
            preuve=preuve1,
            delai_realisation=today + timedelta(days=21 + (index * 3)),
        )
        # M2M responsables - ajouter plusieurs directions pour certains traitements
        t1.responsables_directions.add(direction)
        if index % 2 == 0 and len(refs['directions']) > 1:
            # Ajouter une deuxième direction pour certains PACs
            autre_direction = refs['directions'][(direction_index + 1) % len(refs['directions'])]
            t1.responsables_directions.add(autre_direction)
        t1.responsables_sous_directions.add(sous_direction)

        # Deuxième traitement avec d'autres responsables
        direction2_index = (index + 2) % len(refs['directions'])
        direction2 = refs['directions'][direction2_index]
        sous_directions_de_direction2 = [sd for sd in refs['sous_directions_all'] if sd.direction == direction2]
        if sous_directions_de_direction2:
            sous_direction2 = sous_directions_de_direction2[0]
        else:
            sous_direction2 = refs['sous_directions_all'][(index + 1) % len(refs['sous_directions_all'])]

        t2 = Traitement.objects.create(
            pac=pac,
            action=actions_2[index % len(actions_2)],
            type_action=action_type_2,
            responsable_direction=direction2,
            responsable_sous_direction=sous_direction2,
            preuve=preuve2,
            delai_realisation=today + timedelta(days=28 + (index * 3)),
        )
        t2.responsables_directions.add(direction2)
        t2.responsables_sous_directions.add(sous_direction2)
        
        return [t1, t2]

    def _create_suivis(self, traitements, refs, user: User, with_media: bool):
        today = timezone.now().date()
        
        # Résultats variés pour les suivis
        resultats_t1 = [
            'Révision de la procédure en cours. Workshop organisé avec les parties prenantes. Avancement: 50%',
            'Analyse documentaire terminée. Identification de 12 points d\'amélioration. Rédaction en cours',
            'Diagnostic réalisé. Plan d\'action validé par la direction. Mise en œuvre prévue semaine prochaine',
            'Formation des rédacteurs effectuée. Premier draft de la nouvelle procédure en revue',
            'Benchmark réalisé auprès de 3 sites similaires. Bonnes pratiques identifiées et intégrées',
        ]
        
        resultats_t2 = [
            'Programme de formation élaboré et validé. 3 sessions planifiées. Supports pédagogiques prêts',
            'Première session de sensibilisation réalisée avec 25 participants. Retours très positifs',
            'Déploiement des outils sur site pilote. Formation des utilisateurs en cours. Première version stable',
            'Audit interne réalisé. 8 observations mineures relevées. Actions correctives en cours',
            'Communication diffusée à l\'ensemble du personnel. Réunions d\'équipe organisées dans tous les services',
        ]
        
        # Suivis pour t1
        preuve_suivi = None
        if with_media:
            m = Media.objects.create(url_fichier='/medias/Document_sans_titre-3.pdf')
            preuve_suivi = Preuve.objects.create(description='PV de validation procédure')
            preuve_suivi.medias.add(m)

        # Varier l'état de mise en œuvre (parfois en cours, parfois réalisée)
        import random
        etat_t1 = refs['etat_en_cours'] if random.choice([True, False]) else refs['etat_realisee']
        appreciation_t1 = refs['appreciation_sat'] if random.choice([True, True, False]) else refs['appreciation_non_sat']
        statut_t1 = refs['statut_ouvert'] if etat_t1 == refs['etat_en_cours'] else refs['statut_cloture']

        Suivi.objects.create(
            traitement=traitements[0],
            etat_mise_en_oeuvre=etat_t1,
            resultat=random.choice(resultats_t1),
            appreciation=appreciation_t1,
            preuve=preuve_suivi,
            statut=statut_t1,
            date_mise_en_oeuvre_effective=today + timedelta(days=random.randint(5, 15)),
            cree_par=user,
        )

        # Suivi pour t2
        etat_t2 = refs['etat_en_cours'] if random.choice([True, False]) else refs['etat_realisee']
        appreciation_t2 = refs['appreciation_sat'] if random.choice([True, True, False]) else refs['appreciation_non_sat']
        statut_t2 = refs['statut_ouvert'] if etat_t2 == refs['etat_en_cours'] else refs['statut_cloture']

        Suivi.objects.create(
            traitement=traitements[1],
            etat_mise_en_oeuvre=etat_t2,
            resultat=random.choice(resultats_t2),
            appreciation=appreciation_t2,
            statut=statut_t2,
            date_mise_en_oeuvre_effective=today + timedelta(days=random.randint(7, 20)) if random.choice([True, False]) else None,
            cree_par=user,
        )


