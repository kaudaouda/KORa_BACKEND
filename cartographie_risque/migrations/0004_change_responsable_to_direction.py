# Generated manually

import django.db.models.deletion
from django.db import migrations, models


def clear_responsables_before_migration(apps, schema_editor):
    """Mettre à NULL tous les responsables existants avant de changer le type de champ"""
    PlanAction = apps.get_model('cartographie_risque', 'PlanAction')
    PlanAction.objects.all().update(responsable_id=None)


def reverse_clear_responsables(apps, schema_editor):
    """Fonction de rollback - ne fait rien car on ne peut pas restaurer les User"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cartographie_risque', '0003_alter_evaluationrisque_criticite_and_more'),
        ('parametre', '0037_criticiterisque_frequencerisque_graviterisque_risque_and_more'),
    ]

    operations = [
        # Étape 1: Mettre à NULL tous les responsables existants
        migrations.RunPython(clear_responsables_before_migration, reverse_clear_responsables),
        # Étape 2: Changer le type de champ
        migrations.AlterField(
            model_name='planaction',
            name='responsable',
            field=models.ForeignKey(
                blank=True,
                help_text='Responsable de la mise en œuvre (Direction)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='plans_action_responsable',
                to='parametre.direction'
            ),
        ),
    ]

