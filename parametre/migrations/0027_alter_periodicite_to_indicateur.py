# Generated manually for Periodicite model changes - Data migration

from django.db import migrations, models
import django.db.models.deletion


def clear_periodicite_data(apps, schema_editor):
    """
    Supprimer toutes les données existantes de Periodicite car elles ne peuvent pas être migrées
    """
    Periodicite = apps.get_model('parametre', 'Periodicite')
    Periodicite.objects.all().delete()


def reverse_clear_periodicite_data(apps, schema_editor):
    """
    Fonction de rollback - ne peut pas restaurer les données supprimées
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0026_alter_cible_indicateur_id'),
        ('dashboard', '0001_initial'),
    ]

    operations = [
        # Étape 1: Supprimer toutes les données existantes
        migrations.RunPython(clear_periodicite_data, reverse_clear_periodicite_data),
        
        # Étape 2: Ajouter le nouveau champ nullable
        migrations.AddField(
            model_name='periodicite',
            name='indicateur_id',
            field=models.ForeignKey(
                blank=True, 
                null=True, 
                on_delete=django.db.models.deletion.CASCADE, 
                related_name='periodicites', 
                to='dashboard.indicateur',
                help_text="Indicateur associé à cette périodicité"
            ),
        ),
        
        # Étape 3: Supprimer l'ancien champ
        migrations.RemoveField(
            model_name='periodicite',
            name='frequence_id',
        ),
        
        # Étape 4: Rendre le nouveau champ non-nullable
        migrations.AlterField(
            model_name='periodicite',
            name='indicateur_id',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, 
                related_name='periodicites', 
                to='dashboard.indicateur',
                help_text="Indicateur associé à cette périodicité"
            ),
        ),
        
        # Étape 5: Ajouter la contrainte unique
        migrations.AlterUniqueTogether(
            name='periodicite',
            unique_together={('indicateur_id', 'periode')},
        ),
        
        # Étape 6: Mettre à jour l'ordering
        migrations.AlterModelOptions(
            name='periodicite',
            options={
                'ordering': ['indicateur_id', 'periode', 'created_at'],
                'verbose_name': 'Périodicité',
                'verbose_name_plural': 'Périodicités',
            },
        ),
    ]