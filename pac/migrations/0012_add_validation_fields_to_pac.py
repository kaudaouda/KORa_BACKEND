# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0011_add_annee_and_type_tableau_to_pac'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
    ]
