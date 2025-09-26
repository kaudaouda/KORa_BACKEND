import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0002_remove_utilisateur_model'),
        ('parametre', '0002_add_processus_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pac',
            name='processus',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pacs', to='parametre.processus'),
        ),
    ]
