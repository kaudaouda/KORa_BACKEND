"""
Commande de nettoyage des choix PAC :
- Source : garde uniquement "Audit interne" et "Audit externe" (désactive les autres)
- DysfonctionnementRecommandation : garde uniquement "Dysfonctionnement" et "Recommandation"
  (désactive les autres, les crée si absents)

Usage:
    python manage.py fix_pac_choices
    python manage.py fix_pac_choices --dry-run   # aperçu sans modification
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


SOURCES_AUTORISEES = ['Audit interne', 'Audit externe']

DYSFONCTIONNEMENTS_AUTORISES = [
    {'nom': 'Dysfonctionnement', 'description': 'Dysfonctionnement constaté nécessitant une action corrective'},
    {'nom': 'Recommandation',    'description': 'Recommandation émise suite à un audit ou une revue'},
]


class Command(BaseCommand):
    help = 'Normalise les choix Source et DysfonctionnementRecommandation du PAC'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans modifier la base'
        )

    def handle(self, *args, **options):
        from parametre.models import Source, DysfonctionnementRecommandation

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN — aucune modification ==='))

        # ── Sources ──────────────────────────────────────────────────────────
        self.stdout.write('\n[Source]')
        for source in Source.objects.all():
            if source.nom in SOURCES_AUTORISEES:
                if not source.is_active:
                    self.stdout.write(f'  [^]Réactivation : {source.nom}')
                    if not dry_run:
                        source.is_active = True
                        source.save(update_fields=['is_active'])
                else:
                    self.stdout.write(f'  [OK] : {source.nom}')
            else:
                if source.is_active:
                    self.stdout.write(self.style.WARNING(f'  [v]Désactivation : {source.nom}'))
                    if not dry_run:
                        source.is_active = False
                        source.save(update_fields=['is_active'])
                else:
                    self.stdout.write(f'  - Déjà inactif : {source.nom}')

        # Créer les sources manquantes
        for nom in SOURCES_AUTORISEES:
            if not Source.objects.filter(nom=nom).exists():
                self.stdout.write(f'  + Création : {nom}')
                if not dry_run:
                    Source.objects.create(nom=nom, is_active=True)

        # ── DysfonctionnementRecommandation ───────────────────────────────────
        self.stdout.write('\n[DysfonctionnementRecommandation]')
        noms_autorises = [d['nom'] for d in DYSFONCTIONNEMENTS_AUTORISES]

        # Désactiver les entrées non autorisées
        for dysf in DysfonctionnementRecommandation.objects.all():
            if dysf.nom in noms_autorises:
                if not dysf.is_active:
                    self.stdout.write(f'  [^]Réactivation : {dysf.nom}')
                    if not dry_run:
                        dysf.is_active = True
                        dysf.save(update_fields=['is_active'])
                else:
                    self.stdout.write(f'  [OK] : {dysf.nom}')
            else:
                if dysf.is_active:
                    self.stdout.write(self.style.WARNING(f'  [v]Désactivation : {dysf.nom[:60]}'))
                    if not dry_run:
                        dysf.is_active = False
                        dysf.save(update_fields=['is_active'])

        # Créer les entrées manquantes
        superuser = User.objects.filter(is_superuser=True).first()
        if not superuser:
            superuser = User.objects.first()

        for data in DYSFONCTIONNEMENTS_AUTORISES:
            if not DysfonctionnementRecommandation.objects.filter(nom=data['nom']).exists():
                self.stdout.write(f'  + Création : {data["nom"]}')
                if not dry_run and superuser:
                    DysfonctionnementRecommandation.objects.create(
                        nom=data['nom'],
                        description=data['description'],
                        cree_par=superuser,
                        is_active=True,
                    )

        self.stdout.write(self.style.SUCCESS('\nTerminé.'))
