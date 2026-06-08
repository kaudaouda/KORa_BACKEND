from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0065_recaptcha_encrypt_secret_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='recaptchaconfig',
            name='allowed_hostname',
            field=models.CharField(
                blank=True,
                default='',
                max_length=253,
                verbose_name='Hostname autorisé',
                help_text=(
                    'Domaine retourné par Google dans la réponse reCAPTCHA '
                    '(ex : app.example.com). '
                    'Laissez vide pour ne pas vérifier le hostname.'
                ),
            ),
        ),
    ]
