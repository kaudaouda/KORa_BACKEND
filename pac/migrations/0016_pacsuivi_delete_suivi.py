# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0015_rename_traitement_traitementpac_and_more'),
        ('parametre', '0035_add_annee_model'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
    ]
