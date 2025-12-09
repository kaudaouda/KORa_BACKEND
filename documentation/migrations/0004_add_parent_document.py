# Generated manually for document amendments tracking

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documentation', '0003_document_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='parent_document',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='amendments',
                to='documentation.document',
                help_text="Document parent pour le suivi des amendements"
            ),
        ),
    ]

