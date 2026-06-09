from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0019_alter_tableaubord_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='objectives',
            name='libelle',
            field=models.CharField(
                help_text="Libellé de l'objectif (ex: Assurer à 70% la mise en œuvre du plan annuel)",
                max_length=2000,
            ),
        ),
        migrations.AlterField(
            model_name='indicateur',
            name='libelle',
            field=models.CharField(
                help_text="Libellé de l'indicateur (ex: Taux de mise en œuvre des actions du plan ANAC 2025)",
                max_length=2000,
            ),
        ),
    ]
