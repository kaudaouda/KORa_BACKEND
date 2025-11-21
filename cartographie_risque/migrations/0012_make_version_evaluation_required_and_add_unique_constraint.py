# Migration pour rendre version_evaluation obligatoire et ajouter la contrainte unique

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cartographie_risque', '0011_migrate_existing_evaluations_to_version_initiale'),
        ('parametre', '0043_add_version_evaluation_cdr'),
    ]

    operations = [
        # Rendre le champ version_evaluation obligatoire (NOT NULL)
        migrations.AlterField(
            model_name='evaluationrisque',
            name='version_evaluation',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='evaluations',
                help_text="Version de l'évaluation (Initiale, Réévaluation 1, etc.)",
                to='parametre.versionevaluationcdr'
            ),
        ),
        # Ajouter la contrainte unique (details_cdr, version_evaluation)
        migrations.AlterUniqueTogether(
            name='evaluationrisque',
            unique_together={('details_cdr', 'version_evaluation')},
        ),
    ]
