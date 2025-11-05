# Generated manually for adding initial_ref to Pac model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0022_add_unique_constraint_pac'),
    ]

    operations = [
        migrations.AddField(
            model_name='pac',
            name='initial_ref',
            field=models.ForeignKey(
                blank=True,
                help_text='Référence au PAC initial (pour les amendements)',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='amendements',
                to='pac.pac'
            ),
        ),
    ]

