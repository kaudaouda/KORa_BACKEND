# Generated manually to update unique constraint to include cree_par
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0024_remove_unique_constraint_numero_pac'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='pac',
            name='unique_pac_per_processus_annee_type_tableau',
        ),
        migrations.AddConstraint(
            model_name='pac',
            constraint=models.UniqueConstraint(
                fields=['processus', 'annee', 'type_tableau', 'cree_par'],
                name='unique_pac_per_processus_annee_type_tableau_user'
            ),
        ),
    ]

