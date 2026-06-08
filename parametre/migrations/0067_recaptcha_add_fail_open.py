from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0066_recaptcha_add_allowed_hostname'),
    ]

    operations = [
        migrations.AddField(
            model_name='recaptchaconfig',
            name='fail_open_on_network_error',
            field=models.BooleanField(
                default=False,
                verbose_name='Fail-open si Google injoignable',
                help_text=(
                    'Si activé, un token est accepté sans vérification quand Google est '
                    'injoignable (réseau KO, timeout). '
                    'Si désactivé (défaut), la requête échoue avec HTTP 500 — plus sûr.'
                ),
            ),
        ),
    ]
