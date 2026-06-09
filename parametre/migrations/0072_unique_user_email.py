"""
Ajoute une contrainte UNIQUE sur auth_user.email au niveau base de données.

Django's User.email n'est pas unique par défaut. Sans cette contrainte,
deux requêtes simultanées sur register() peuvent créer deux comptes avec
le même email, provoquant ensuite une MultipleObjectsReturned non gérée
dans la vue login() qui fait User.objects.get(email=email).

On utilise RunSQL (CREATE UNIQUE INDEX) plutôt qu'AlterField car le modèle
appartient à l'app 'auth' et ne peut pas être altéré directement depuis une
migration 'parametre'. L'index est équivalent fonctionnellement et compatible
SQLite + PostgreSQL.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0071_two_factor_config_check_constraints'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_unique
                ON auth_user (email)
                WHERE email != '';
            """,
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_unique;",
        ),
    ]
