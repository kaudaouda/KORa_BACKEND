# Generated manually to rename TypeTableau to Versions

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0035_add_annee_model'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='TypeTableau',
            new_name='Versions',
        ),
        migrations.AlterModelOptions(
            name='versions',
            options={
                'ordering': ['nom'],
                'verbose_name': 'Version',
                'verbose_name_plural': 'Versions',
            },
        ),
    ]

