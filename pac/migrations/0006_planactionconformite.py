# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0005_make_traitement_fields_optional'),
        ('parametre', '0032_annee_typetableaupac'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
    ]
