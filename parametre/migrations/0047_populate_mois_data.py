# Generated migration to populate Mois table

from django.db import migrations, models


def populate_mois(apps, schema_editor):
    """Populate the Mois table with the 12 months"""
    Mois = apps.get_model('parametre', 'Mois')
    
    mois_data = [
        (1, 'Janvier', 'J'),
        (2, 'Février', 'F'),
        (3, 'Mars', 'M'),
        (4, 'Avril', 'A'),
        (5, 'Mai', 'M'),
        (6, 'Juin', 'J'),
        (7, 'Juillet', 'J'),
        (8, 'Août', 'O'),
        (9, 'Septembre', 'S'),
        (10, 'Octobre', 'O'),
        (11, 'Novembre', 'N'),
        (12, 'Décembre', 'D'),
    ]
    
    for numero, nom, abreviation in mois_data:
        Mois.objects.get_or_create(
            numero=numero,
            defaults={'nom': nom, 'abreviation': abreviation}
        )


def reverse_populate_mois(apps, schema_editor):
    """Reverse migration - delete all Mois entries"""
    Mois = apps.get_model('parametre', 'Mois')
    Mois.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0046_create_mois_model'),
    ]

    operations = [
        # Retirer la contrainte unique sur abreviation
        migrations.AlterField(
            model_name='mois',
            name='abreviation',
            field=models.CharField(
                help_text='Abréviation du mois (première lettre: J, F, M, etc.)',
                max_length=10
            ),
        ),
        # Peupler les données
        migrations.RunPython(populate_mois, reverse_populate_mois),
    ]

