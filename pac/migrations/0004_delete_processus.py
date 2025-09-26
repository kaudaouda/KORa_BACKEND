from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pac', '0003_alter_pac_processus_delete_processus'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name='Processus',
                )
            ]
        )
    ]
