from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametre', '0070_add_two_factor_user_session'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='twofactorconfig',
            constraint=models.CheckConstraint(
                condition=models.Q(otp_lifetime_seconds__gte=300) & models.Q(otp_lifetime_seconds__lte=31536000),
                name='2fa_otp_lifetime_range',
            ),
        ),
        migrations.AddConstraint(
            model_name='twofactorconfig',
            constraint=models.CheckConstraint(
                condition=models.Q(max_attempts__gte=1) & models.Q(max_attempts__lte=10),
                name='2fa_max_attempts_range',
            ),
        ),
        migrations.AddConstraint(
            model_name='twofactorconfig',
            constraint=models.CheckConstraint(
                condition=models.Q(code_length__gte=4) & models.Q(code_length__lte=8),
                name='2fa_code_length_range',
            ),
        ),
    ]
