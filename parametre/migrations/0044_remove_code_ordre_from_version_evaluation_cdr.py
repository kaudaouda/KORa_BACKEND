# Migration pour supprimer les champs code et ordre de VersionEvaluationCDR

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0043_add_version_evaluation_cdr'),
    ]

    operations = [
        # Supprimer le champ 'code'
        migrations.RemoveField(
            model_name='versionevaluationcdr',
            name='code',
        ),
        # Supprimer le champ 'ordre'
        migrations.RemoveField(
            model_name='versionevaluationcdr',
            name='ordre',
        ),
        # Rendre le champ 'nom' unique
        migrations.AlterField(
            model_name='versionevaluationcdr',
            name='nom',
            field=models.CharField(
                max_length=100,
                unique=True,
                help_text="Nom de la version (ex: Évaluation Initiale, Réévaluation 1)"
            ),
        ),
    ]
