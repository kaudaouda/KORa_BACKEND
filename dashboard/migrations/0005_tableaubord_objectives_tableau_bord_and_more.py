# No-op: état déjà inclus dans 0001_initial + 0002_initial (régénérés)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_observation'),
        ('parametre', '0028_merge_20251016_1210'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
    ]
