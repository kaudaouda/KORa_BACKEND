# Generated manually for adding version_evaluation to EvaluationRisque

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cartographie_risque', '0009_add_raison_to_cdr'),
        ('parametre', '0043_add_version_evaluation_cdr'),
    ]

    operations = [
        # Étape 1: Ajouter le champ version_evaluation avec null=True temporaire
        migrations.AddField(
            model_name='evaluationrisque',
            name='version_evaluation',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='evaluations',
                help_text="Version de l'évaluation (Initiale, Réévaluation 1, etc.)",
                to='parametre.versionevaluationcdr'
            ),
        ),
        # Étape 2: Modifier le ordering pour inclure version_evaluation__ordre
        migrations.AlterModelOptions(
            name='evaluationrisque',
            options={
                'ordering': ['details_cdr', 'version_evaluation__ordre', 'created_at'],
                'verbose_name': 'Évaluation des Risques',
                'verbose_name_plural': 'Évaluations des Risques',
            },
        ),
    ]
