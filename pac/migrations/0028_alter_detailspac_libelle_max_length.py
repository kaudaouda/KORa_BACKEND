from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0027_remove_pac_unique_pac_per_processus_annee_type_tableau_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detailspac',
            name='libelle',
            field=models.CharField(
                blank=True,
                help_text='Libellé du détail',
                max_length=2000,
                null=True,
            ),
        ),
    ]
