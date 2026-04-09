# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cartographie_risque', '0011_migrate_existing_evaluations_to_version_initiale'),
        ('parametre', '0043_add_version_evaluation_cdr'),
    ]

    operations = [
    ]
