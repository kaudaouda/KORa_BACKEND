# No-op: état déjà inclus dans 0001_initial (régénéré)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('parametre', '0052_alter_activitylog_entity_type'),
    ]

    operations = [
    ]
