"""
Migration : ajout du champ is_global sur UserProcessusRole
+ remplacement de unique_together par deux UniqueConstraint partiels
+ processus devient nullable (pour les rôles globaux)
+ ajout de l'index sur (user, is_global, is_active)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0056_rename_preuve_description_to_titre'),
    ]

    operations = [
        # 1. Rendre processus nullable (NULL autorisé pour is_global=True)
        migrations.AlterField(
            model_name='userprocessusrole',
            name='processus',
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Processus concerné. Doit être NULL si is_global=True.",
                on_delete=models.deletion.CASCADE,
                related_name='user_processus_roles',
                to='parametre.processus',
            ),
        ),

        # 2. Ajouter le champ is_global
        migrations.AddField(
            model_name='userprocessusrole',
            name='is_global',
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Si True, ce rôle s'applique à TOUS les processus (ex: superviseur_smi). "
                    "Le champ 'processus' doit alors être laissé vide. "
                    "Réservé aux rôles de supervision transverse."
                ),
            ),
        ),

        # 3. Supprimer l'ancien unique_together
        migrations.AlterUniqueTogether(
            name='userprocessusrole',
            unique_together=set(),
        ),

        # 4. Ajouter les deux UniqueConstraint partiels
        migrations.AddConstraint(
            model_name='userprocessusrole',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_global=True),
                fields=['user', 'role'],
                name='unique_global_user_role',
            ),
        ),
        migrations.AddConstraint(
            model_name='userprocessusrole',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_global=False),
                fields=['user', 'processus', 'role'],
                name='unique_processus_user_role',
            ),
        ),

        # 5. Ajouter l'index sur (user, is_global, is_active)
        migrations.AddIndex(
            model_name='userprocessusrole',
            index=models.Index(
                fields=['user', 'is_global', 'is_active'],
                name='user_prcs_role_global_idx',
            ),
        ),
    ]
