# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cartographie_risque', '0006_cdr_initial_ref'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('parametre', '0039_risque_niveaux_risque'),
    ]

    operations = [
    ]
