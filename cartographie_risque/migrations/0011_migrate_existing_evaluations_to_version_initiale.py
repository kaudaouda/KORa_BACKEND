# Migration de données pour assigner la version initiale aux évaluations existantes

from django.db import migrations


def create_initial_version_and_assign(apps, schema_editor):
    """
    Crée la version 'EVAL_INITIALE' si elle n'existe pas et l'assigne à toutes les évaluations existantes
    """
    VersionEvaluationCDR = apps.get_model('parametre', 'VersionEvaluationCDR')
    EvaluationRisque = apps.get_model('cartographie_risque', 'EvaluationRisque')

    # Créer la version initiale si elle n'existe pas
    version_initiale, created = VersionEvaluationCDR.objects.get_or_create(
        code='EVAL_INITIALE',
        defaults={
            'nom': 'Évaluation Initiale',
            'ordre': 0,
            'description': 'Première évaluation des risques',
            'is_active': True
        }
    )

    if created:
        print(f"✅ Version 'EVAL_INITIALE' créée: {version_initiale}")
    else:
        print(f"ℹ️ Version 'EVAL_INITIALE' existe déjà: {version_initiale}")

    # Assigner cette version à toutes les évaluations existantes qui n'en ont pas
    evaluations_sans_version = EvaluationRisque.objects.filter(version_evaluation__isnull=True)
    count = evaluations_sans_version.count()

    if count > 0:
        evaluations_sans_version.update(version_evaluation=version_initiale)
        print(f"✅ {count} évaluations mises à jour avec la version initiale")
    else:
        print("ℹ️ Aucune évaluation à mettre à jour")


def reverse_migration(apps, schema_editor):
    """
    Inverse la migration en remettant version_evaluation à NULL
    """
    EvaluationRisque = apps.get_model('cartographie_risque', 'EvaluationRisque')
    EvaluationRisque.objects.all().update(version_evaluation=None)
    print("⚠️ Toutes les évaluations ont été remises à version_evaluation=NULL")


class Migration(migrations.Migration):

    dependencies = [
        ('cartographie_risque', '0010_add_version_evaluation_to_evaluation_risque'),
        ('parametre', '0043_add_version_evaluation_cdr'),
    ]

    operations = [
        migrations.RunPython(create_initial_version_and_assign, reverse_migration),
    ]
