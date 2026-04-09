# No-op: état déjà inclus dans 0001_initial (régénéré)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0013_add_is_active_field'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
    ]
