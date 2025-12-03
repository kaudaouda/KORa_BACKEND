# Generated migration to add livrable and date_realisation fields to SuivisAP

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activite_periodique', '0007_remove_commentaire_from_suivisap'),
    ]

    operations = [
        migrations.AddField(
            model_name='suivisap',
            name='livrable',
            field=models.TextField(
                blank=True,
                null=True,
                help_text='Livrable associé à ce suivi'
            ),
        ),
        migrations.AddField(
            model_name='suivisap',
            name='date_realisation',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Date de réalisation effective'
            ),
        ),
    ]

