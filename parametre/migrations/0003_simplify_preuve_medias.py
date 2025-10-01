# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0002_change_preuve_media_to_many_to_many'),
    ]

    operations = [
        # Supprimer la table preuve_media
        migrations.RunSQL(
            "DROP TABLE IF EXISTS preuve_media;",
            reverse_sql="-- Cannot reverse this operation"
        ),
        
        # Recréer le champ medias sans through
        migrations.RemoveField(
            model_name='preuve',
            name='medias',
        ),
        migrations.AddField(
            model_name='preuve',
            name='medias',
            field=models.ManyToManyField(blank=True, related_name='preuves', to='parametre.media'),
        ),
    ]
