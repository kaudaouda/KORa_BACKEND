# Generated manually for VersionEvaluationCDR

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0042_add_raison_to_versions'),
    ]

    operations = [
        migrations.CreateModel(
            name='VersionEvaluationCDR',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(default=True, help_text='Indique si cet élément est actif et peut être utilisé')),
                ('code', models.CharField(help_text='Code de la version (ex: EVAL_INITIALE, REEVALUATION_1, REEVALUATION_2)', max_length=30, unique=True)),
                ('nom', models.CharField(help_text="Nom affiché de la version (ex: Évaluation Initiale, Réévaluation 1)", max_length=100)),
                ('ordre', models.PositiveIntegerField(default=0, help_text="Ordre d'affichage des versions (0 pour initiale, 1 pour rééval 1, etc.)")),
                ('description', models.TextField(blank=True, help_text="Description de cette version d'évaluation", null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Version Évaluation CDR',
                'verbose_name_plural': 'Versions Évaluation CDR',
                'db_table': 'version_evaluation_cdr',
                'ordering': ['ordre', 'nom'],
            },
        ),
    ]
