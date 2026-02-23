from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0026_pac_unique_global_processus_annee_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='pac',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                help_text='Date de création du PAC',
            ),
            preserve_default=False,
        ),
    ]
