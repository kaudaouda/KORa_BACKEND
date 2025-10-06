# Generated manually to remove notification_override table

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0008_reminderemaillog'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP TABLE IF EXISTS notification_override;",
            reverse_sql="-- Cannot reverse DROP TABLE",
        ),
    ]
