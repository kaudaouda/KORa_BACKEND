import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0001_initial'),
        ('pac', '0002_remove_utilisateur_model'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Processus',
                    fields=[
                        ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('numero_processus', models.CharField(blank=True, max_length=10, unique=True)),
                        ('nom', models.CharField(max_length=200, unique=True)),
                        ('description', models.TextField(blank=True, null=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('cree_par', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='processus_crees', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Processus',
                        'verbose_name_plural': 'Processus',
                        'db_table': 'processus',
                    },
                )
            ],
        )
    ]