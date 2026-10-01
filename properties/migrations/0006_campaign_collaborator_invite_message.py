from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0005_marketing_and_sales'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaigncollaborator',
            name='invite_message',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Message from campaign owner when inviting this collaborator',
            ),
        ),
        migrations.AddField(
            model_name='campaigncollaborator',
            name='is_read',
            field=models.BooleanField(
                default=False,
                help_text='Invitee has opened or responded to this collaboration request',
            ),
        ),
    ]
