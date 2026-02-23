# Migration: unicité globale (processus, annee, type_tableau) comme pour le dashboard
# Un seul PAC par combinaison, quel que soit l'utilisateur

from django.db import migrations, models
from django.db.models import Count, Q


def deduplicate_pacs(apps, schema_editor):
    """Supprimer les doublons: garder un PAC par (processus, annee, type_tableau)."""
    Pac = apps.get_model('pac', 'Pac')

    # Récupérer les PACs avec processus, annee, type_tableau tous non null
    pacs = Pac.objects.exclude(
        Q(processus_id__isnull=True) | Q(annee_id__isnull=True) | Q(type_tableau_id__isnull=True)
    )

    from collections import defaultdict
    groups = defaultdict(list)
    for p in pacs.annotate(detail_count=Count('details')):
        key = (p.processus_id, p.annee_id, p.type_tableau_id)
        groups[key].append(p)

    to_delete = []
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        sorted_group = sorted(group, key=lambda p: (-p.detail_count, str(p.uuid)))
        for p in sorted_group[1:]:
            to_delete.append(p.uuid)

    for uid in to_delete:
        Pac.objects.filter(uuid=uid).delete()


def reverse_deduplicate(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0025_update_unique_constraint_to_include_user'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='pac',
            name='unique_pac_per_processus_annee_type_tableau_user',
        ),
        migrations.RunPython(deduplicate_pacs, reverse_deduplicate),
        migrations.AddConstraint(
            model_name='pac',
            constraint=models.UniqueConstraint(
                fields=['processus', 'annee', 'type_tableau'],
                name='unique_pac_per_processus_annee_type_tableau'
            ),
        ),
    ]
