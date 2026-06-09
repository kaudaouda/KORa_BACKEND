from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0069_add_two_factor_config_and_email_otp'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='twofactorconfig',
            name='is_enabled',
            field=models.BooleanField(
                default=False,
                help_text="Si activé, un code par email est requis à la connexion si la session 2FA est expirée.",
                verbose_name='2FA activé',
            ),
        ),
        migrations.AlterField(
            model_name='twofactorconfig',
            name='otp_lifetime_seconds',
            field=models.PositiveIntegerField(
                default=86400,
                help_text=(
                    "Durée pendant laquelle l'utilisateur n'est pas redemandé après une vérification réussie. "
                    "Exemples : 3600 = 1h, 86400 = 1 jour, 604800 = 7 jours, 2592000 = 30 jours."
                ),
                verbose_name='Durée de la session 2FA (secondes)',
            ),
        ),
        migrations.CreateModel(
            name='TwoFactorUserSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('verified_at', models.DateTimeField(verbose_name='Dernière vérification 2FA réussie')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='two_factor_session',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur',
                )),
            ],
            options={
                'verbose_name': 'Session 2FA utilisateur',
                'verbose_name_plural': 'Sessions 2FA utilisateurs',
                'db_table': 'two_factor_user_session',
            },
        ),
    ]
