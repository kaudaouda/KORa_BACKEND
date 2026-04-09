# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0047_populate_mois_data'),
        ('activite_periodique', '0005_remove_periodicite_and_suivis_models'),
    ]

    operations = [
    ]
