from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0067_recaptcha_add_fail_open'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recaptchaconfig',
            name='min_score',
            field=models.FloatField(
                default=0.5,
                verbose_name='Score minimum v3 (global)',
                help_text='Entre 0.0 (bot) et 1.0 (humain). Recommandé : 0.5. Utilisé quand le score par endpoint est absent.',
            ),
        ),
        migrations.AddField(
            model_name='recaptchaconfig',
            name='min_score_login',
            field=models.FloatField(
                null=True, blank=True, default=None,
                verbose_name='Score min. — connexion',
                help_text='Laissez vide pour utiliser le score global.',
            ),
        ),
        migrations.AddField(
            model_name='recaptchaconfig',
            name='min_score_register',
            field=models.FloatField(
                null=True, blank=True, default=None,
                verbose_name='Score min. — inscription',
                help_text='Laissez vide pour utiliser le score global.',
            ),
        ),
        migrations.AddField(
            model_name='recaptchaconfig',
            name='min_score_invitation',
            field=models.FloatField(
                null=True, blank=True, default=None,
                verbose_name="Score min. — complétion d'invitation",
                help_text='Laissez vide pour utiliser le score global.',
            ),
        ),
        migrations.AddField(
            model_name='recaptchaconfig',
            name='min_score_password_reset',
            field=models.FloatField(
                null=True, blank=True, default=None,
                verbose_name='Score min. — réinitialisation de mot de passe',
                help_text='Laissez vide pour utiliser le score global.',
            ),
        ),
    ]
