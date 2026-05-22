"""
Commande de normalisation : donne à chaque PacSuivi sa propre Preuve.

Contexte du bug : le seeder (et le clonage d'amendement avant fix) assignait
la même instance Preuve à plusieurs PacSuivi. Ajouter un média à cette preuve
la faisait apparaître sur tous les suivis qui la partageaient.

Usage :
    python manage.py fix_shared_preuves
    python manage.py fix_shared_preuves --dry-run   (aperçu sans modifier la DB)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from pac.models import PacSuivi
from parametre.models import Preuve


class Command(BaseCommand):
    help = "Donne une Preuve individuelle à chaque PacSuivi qui partage sa preuve avec d'autres."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Afficher ce qui serait fait sans modifier la base de données.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Trouver les preuves partagées entre plusieurs PacSuivi
        shared = (
            PacSuivi.objects
            .values('preuve__uuid', 'preuve__titre')
            .annotate(cnt=Count('uuid'))
            .filter(cnt__gt=1)
            .order_by('-cnt')
        )

        if not shared:
            self.stdout.write(self.style.SUCCESS('Aucune preuve partagée trouvée. Rien à faire.'))
            return

        total_fixed = 0

        for entry in shared:
            preuve_uuid = entry['preuve__uuid']
            preuve_titre = entry['preuve__titre']
            cnt = entry['cnt']
            self.stdout.write(
                f"Preuve {preuve_uuid} ({preuve_titre!r}) partagée par {cnt} PacSuivi"
            )

            # Récupérer tous les PacSuivi qui partagent cette preuve
            suivis = list(PacSuivi.objects.filter(preuve__uuid=preuve_uuid))

            # Le premier garde la preuve originale ; les autres en reçoivent une nouvelle (vide)
            for suivi in suivis[1:]:
                if dry_run:
                    self.stdout.write(f"  [dry-run] Créerait une Preuve vide pour PacSuivi {suivi.uuid}")
                else:
                    with transaction.atomic():
                        new_preuve = Preuve.objects.create(
                            titre=preuve_titre or f'Preuve suivi {suivi.uuid}'
                        )
                        suivi.preuve = new_preuve
                        suivi.save(update_fields=['preuve'])
                    self.stdout.write(
                        f"  PacSuivi {suivi.uuid} -> nouvelle Preuve {new_preuve.uuid}"
                    )
                total_fixed += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n[dry-run] {total_fixed} PacSuivi auraient reçu une nouvelle Preuve. "
                "Relancez sans --dry-run pour appliquer."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n{total_fixed} PacSuivi ont maintenant leur propre Preuve."
            ))
