# Generated manually for appointment booking fields on UserProfile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_userprivilege'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='booking_slug',
            field=models.CharField(
                blank=True,
                help_text='Public token segment for /book/<slug>/ (unset until generated).',
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_manage_appointments',
            field=models.BooleanField(
                default=False,
                help_text='Allow this user to use the appointment booking module (in addition to role defaults).',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_public_booking_active',
            field=models.BooleanField(
                default=True,
                help_text='When off, the public booking link shows as disabled.',
            ),
        ),
    ]
