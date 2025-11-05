# Generated manually for removing unique constraint on numero_pac to allow duplicates for amendments

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0023_add_initial_ref_to_pac'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detailspac',
            name='numero_pac',
            field=models.CharField(blank=True, help_text='Numéro du détail PAC (peut être dupliqué pour les amendements)', max_length=50, null=True),
        ),
    ]
