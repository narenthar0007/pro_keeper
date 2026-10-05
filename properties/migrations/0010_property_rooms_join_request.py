from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('properties', '0009_brand_media_uploads'),
        ('accounts', '0009_alter_roleprivilege_role_alter_userprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='kitchens',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='property',
            name='planned_vacate_date',
            field=models.DateField(
                blank=True,
                help_text='Future date when the current tenant will vacate',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='rooms',
            field=models.PositiveIntegerField(default=1, help_text='Total number of rooms'),
        ),
        migrations.AlterField(
            model_name='usernotification',
            name='kind',
            field=models.CharField(
                choices=[
                    ('rent_due', 'Rent due'),
                    ('enquiry', 'Enquiry'),
                    ('visit', 'Visit'),
                    ('offer', 'Offer'),
                    ('complaint', 'Complaint'),
                    ('campaign_invite', 'Campaign invite'),
                    ('campaign_task', 'Campaign task'),
                    ('lease_expiry', 'Lease expiry'),
                    ('message', 'Message'),
                    ('join_request', 'Join request'),
                    ('admin_message', 'Admin message'),
                    ('rent_reminder', 'Rent reminder'),
                ],
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name='TenantJoinRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField(blank=True, default='')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('accepted', 'Accepted'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('brand', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tenant_join_requests',
                    to='accounts.brand',
                )),
                ('property', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='join_requests',
                    to='properties.property',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='property_join_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='tenantjoinrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'pending')),
                fields=('property', 'user'),
                name='uniq_pending_join_request',
            ),
        ),
    ]
