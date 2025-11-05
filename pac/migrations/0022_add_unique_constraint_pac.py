# Generated manually for unique constraint on Pac model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0021_rename_typetableau_to_versions'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='pac',
            constraint=models.UniqueConstraint(
                fields=['processus', 'annee', 'type_tableau'],
                name='unique_pac_per_processus_annee_type_tableau'
            ),
        ),
    ]


