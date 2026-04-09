# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_tableaubord_objectives_tableau_bord_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
    ]
