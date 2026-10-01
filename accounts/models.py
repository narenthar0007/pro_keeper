from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from .media_paths import brand_banner_upload, brand_icon_upload, brand_logo_upload, user_avatar_upload


class UserProfile(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_OWNER = 'owner'
    ROLE_MANAGER = 'manager'
    ROLE_EMPLOYEE = 'employee'
    ROLE_TENANT = 'tenant'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_OWNER, 'Owner'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_EMPLOYEE, 'Employee'),
        (ROLE_TENANT, 'Tenant'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OWNER)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
    )
    notes = models.CharField(max_length=255, blank=True, default='')
    rent_reminder_enabled = models.BooleanField(
        default=False,
        help_text='Show a reminder when rent is due this month',
    )
    rent_due_day = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text='Day of the month rent is due (1–28)',
    )
    reminder_days_before = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(14)],
        help_text='How many days before the due date to start reminding you',
    )
    reminder_email_enabled = models.BooleanField(
        default=True,
        help_text='Also send the reminder to the email on this account',
    )
    reminder_last_sent_on = models.DateField(
        null=True,
        blank=True,
        help_text='Last date an email reminder was sent',
    )
    brand = models.ForeignKey(
        'Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='user_profiles',
        help_text='Brand this login belongs to (data is isolated per brand)',
    )
    avatar = models.ImageField(
        upload_to=user_avatar_upload,
        blank=True,
        null=True,
        help_text='Profile photo for header and account screens',
    )

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser or self.user.is_staff

    @property
    def is_owner(self):
        return self.role == self.ROLE_OWNER

    @property
    def is_tenant(self):
        return self.role == self.ROLE_TENANT

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_employee(self):
        return self.role == self.ROLE_EMPLOYEE


class RolePrivilege(models.Model):
    """Toggleable privileges per role — controlled in admin panel."""

    ROLE_CHOICES = [
        (UserProfile.ROLE_OWNER, 'Owner'),
        (UserProfile.ROLE_MANAGER, 'Manager'),
        (UserProfile.ROLE_EMPLOYEE, 'Employee'),
        (UserProfile.ROLE_TENANT, 'Tenant'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=120)
    enabled = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        unique_together = ('role', 'code')
        ordering = ['role', 'label']

    def __str__(self):
        state = 'ON' if self.enabled else 'OFF'
        return f'{self.role}.{self.code} [{state}]'


class Brand(models.Model):
    """
    Multi-brand site identity + theme.

    Each brand has its own colors, fonts, header/footer, hostnames, and base URL.
    All brands are managed from the same admin panel.
    """

    FONT_CHOICES = [
        ('syne_source', 'Syne + Source Sans 3'),
        ('inter_system', 'Inter + System'),
        ('cinzel_josefin', 'Cinzel + Josefin Sans'),
        ('georgia_arial', 'Georgia + Arial'),
        ('mono', 'Monospace'),
    ]
    TABLE_CHOICES = [
        ('comfortable', 'Comfortable'),
        ('compact', 'Compact'),
        ('bordered', 'Bordered'),
        ('striped', 'Striped'),
    ]
    RADIUS_CHOICES = [
        ('sharp', 'Sharp'),
        ('soft', 'Soft'),
        ('round', 'Round'),
    ]

    name = models.CharField(max_length=80, default='PropKeep', help_text='Brand display name')
    slug = models.SlugField(max_length=80, unique=True, default='propkeep')
    tagline = models.CharField(max_length=120, blank=True, default='Property Management')
    footer_text = models.CharField(
        max_length=255,
        blank=True,
        default='PropKeep — rent, advance, and listings in one place.',
    )
    hostnames = models.CharField(
        max_length=255,
        blank=True,
        default='localhost,127.0.0.1',
        help_text='Comma-separated hosts that activate this brand (e.g. checkpro.localhost)',
    )
    base_url = models.CharField(
        max_length=255,
        blank=True,
        default='http://127.0.0.1:8000',
        help_text='Public base URL shown for this brand',
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    primary_color = models.CharField(max_length=20, default='#0b5fff')
    secondary_color = models.CharField(max_length=20, default='#111827')
    button_color = models.CharField(max_length=20, default='#0b5fff')
    button_text_color = models.CharField(max_length=20, default='#ffffff')
    background_color = models.CharField(max_length=20, default='#f4f6f8')
    surface_color = models.CharField(max_length=20, default='#ffffff')
    text_color = models.CharField(max_length=20, default='#111827')
    header_color = models.CharField(max_length=20, default='#0f2744')
    header_text_color = models.CharField(max_length=20, default='#e8eef7')
    header_active_color = models.CharField(max_length=20, default='#12b886')
    footer_bg_color = models.CharField(max_length=20, default='#ffffff')
    footer_text_color = models.CharField(max_length=20, default='#6b7280')

    font_style = models.CharField(max_length=30, choices=FONT_CHOICES, default='syne_source')
    table_format = models.CharField(max_length=20, choices=TABLE_CHOICES, default='comfortable')
    border_radius = models.CharField(max_length=20, choices=RADIUS_CHOICES, default='soft')
    logo = models.ImageField(
        upload_to=brand_logo_upload,
        blank=True,
        null=True,
        help_text='Main brand logo shown in the app header',
    )
    icon = models.ImageField(
        upload_to=brand_icon_upload,
        blank=True,
        null=True,
        help_text='Square icon / favicon for this brand',
    )
    banner = models.ImageField(
        upload_to=brand_banner_upload,
        blank=True,
        null=True,
        help_text='Optional wide banner for marketing pages',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Brand'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            type(self).objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """Compatibility helper — returns the default brand (theme)."""
        from .brands import resolve_brand

        return resolve_brand(None)

    def font_css(self):
        mapping = {
            'syne_source': ("'Syne', sans-serif", "'Source Sans 3', sans-serif"),
            'inter_system': ("'Inter', sans-serif", "'Inter', system-ui, sans-serif"),
            'cinzel_josefin': ("'Cinzel', serif", "'Josefin Sans', sans-serif"),
            'georgia_arial': ('Georgia, serif', 'Arial, sans-serif'),
            'mono': ("'Courier New', monospace", "'Courier New', monospace"),
        }
        return mapping.get(self.font_style, mapping['syne_source'])

    def radius_value(self):
        return {'sharp': '4px', 'soft': '18px', 'round': '28px'}.get(self.border_radius, '18px')


# Backward-compatible alias used by older imports
SiteTheme = Brand

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('register', 'Register'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    username = models.CharField(max_length=150, blank=True, default='')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='other')
    method = models.CharField(max_length=10, blank=True, default='')
    path = models.CharField(max_length=500, blank=True, default='')
    status_code = models.PositiveIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True, default='')
    message = models.CharField(max_length=500, blank=True, default='')
    brand = models.ForeignKey(
        'Brand',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
        help_text='Brand context when this action happened',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        who = self.username or (self.user.username if self.user else 'anonymous')
        return f'{who} · {self.action} · {self.path}'


DEFAULT_PRIVILEGES = [
    # Owner
    (UserProfile.ROLE_OWNER, 'view_dashboard', 'View owner dashboard', True),
    (UserProfile.ROLE_OWNER, 'manage_properties', 'Add / edit / delete properties', True),
    (UserProfile.ROLE_OWNER, 'manage_tenants', 'Manage tenants', True),
    (UserProfile.ROLE_OWNER, 'manage_payments', 'Record rent payments', True),
    (UserProfile.ROLE_OWNER, 'manage_expenses', 'Manage expenses', True),
    (UserProfile.ROLE_OWNER, 'view_reports', 'View reports', True),
    (UserProfile.ROLE_OWNER, 'view_enquiries', 'View enquiries / leads', True),
    (UserProfile.ROLE_OWNER, 'manage_leads', 'Manage lead pipeline (visits, offers, convert)', True),
    (UserProfile.ROLE_OWNER, 'public_browse', 'Browse public listings', True),
    (UserProfile.ROLE_OWNER, 'manage_marketing', 'Manage marketing campaigns', True),
    (UserProfile.ROLE_OWNER, 'view_marketing', 'View marketing page', True),
    (UserProfile.ROLE_OWNER, 'view_settings', 'Access settings page', True),
    (UserProfile.ROLE_OWNER, 'manage_rent_reminders', 'Set rent collection reminders', True),
    (UserProfile.ROLE_OWNER, 'view_buildings', 'View buildings', True),
    (UserProfile.ROLE_OWNER, 'manage_buildings', 'Add / edit buildings and units', True),
    (UserProfile.ROLE_OWNER, 'view_inbox', 'View notification inbox', True),
    (UserProfile.ROLE_OWNER, 'manage_documents', 'Upload and manage documents', True),
    (UserProfile.ROLE_OWNER, 'view_calendar', 'View calendar', True),
    (UserProfile.ROLE_OWNER, 'send_messages', 'Message tenants', True),
    (UserProfile.ROLE_OWNER, 'manage_meters', 'Log meter readings', True),
    (UserProfile.ROLE_OWNER, 'view_commissions', 'View agent commissions', True),
    # Tenant
    (UserProfile.ROLE_TENANT, 'view_tenant_portal', 'Access tenant portal', True),
    (UserProfile.ROLE_TENANT, 'submit_complaints', 'Submit complaints', True),
    (UserProfile.ROLE_TENANT, 'view_own_payments', 'View own rent payments', True),
    (UserProfile.ROLE_TENANT, 'public_browse', 'Browse public listings', True),
    (UserProfile.ROLE_TENANT, 'view_marketing', 'View marketing page', True),
    (UserProfile.ROLE_TENANT, 'create_marketing', 'Create marketing campaigns', False),
    (UserProfile.ROLE_TENANT, 'collaborate_marketing', 'Collaborate on campaigns', True),
    (UserProfile.ROLE_TENANT, 'view_settings', 'Access settings page', True),
    (UserProfile.ROLE_TENANT, 'manage_rent_reminders', 'Set rent payment reminders', True),
    (UserProfile.ROLE_TENANT, 'view_inbox', 'View notification inbox', True),
    (UserProfile.ROLE_TENANT, 'send_messages', 'Message property owner', True),
    (UserProfile.ROLE_TENANT, 'pay_rent', 'Pay rent from portal', True),
    (UserProfile.ROLE_TENANT, 'save_listings', 'Save listings to shortlist', True),
    (UserProfile.ROLE_TENANT, 'view_dashboard', 'View owner dashboard', False),
    (UserProfile.ROLE_TENANT, 'manage_properties', 'Manage properties', False),
    (UserProfile.ROLE_OWNER, 'save_listings', 'Save listings to shortlist', True),
    # Owner HRMS
    (UserProfile.ROLE_OWNER, 'hrms_access', 'Access HRMS module', True),
    (UserProfile.ROLE_OWNER, 'hrms_manage_employees', 'Manage employees', True),
    (UserProfile.ROLE_OWNER, 'hrms_manage_managers', 'Manage managers', True),
    (UserProfile.ROLE_OWNER, 'hrms_manage_sites', 'Manage sites', True),
    (UserProfile.ROLE_OWNER, 'hrms_approve', 'Approve employees and regularize', True),
    (UserProfile.ROLE_OWNER, 'hrms_mark_attendance', 'Mark attendance', True),
    (UserProfile.ROLE_OWNER, 'hrms_view_reports', 'View HRMS reports', True),
    (UserProfile.ROLE_OWNER, 'hrms_settings', 'Edit HRMS settings', True),
    # Manager HRMS
    (UserProfile.ROLE_MANAGER, 'hrms_access', 'Access HRMS module', True),
    (UserProfile.ROLE_MANAGER, 'hrms_view_site', 'View assigned sites', True),
    (UserProfile.ROLE_MANAGER, 'hrms_mark_attendance', 'Mark attendance on sites', True),
    (UserProfile.ROLE_MANAGER, 'hrms_apply_regularize', 'Apply regularize', True),
    (UserProfile.ROLE_MANAGER, 'hrms_site_updates', 'Post site updates', True),
    (UserProfile.ROLE_MANAGER, 'hrms_punch', 'Punch in / out', True),
    (UserProfile.ROLE_MANAGER, 'hrms_manage_employees', 'Add employees on sites', True),
    # Employee HRMS
    (UserProfile.ROLE_EMPLOYEE, 'hrms_access', 'Access HRMS module', True),
    (UserProfile.ROLE_EMPLOYEE, 'hrms_punch', 'Punch in / out', True),
    (UserProfile.ROLE_EMPLOYEE, 'hrms_view_own', 'View own attendance', True),
    (UserProfile.ROLE_EMPLOYEE, 'hrms_apply_regularize_self', 'Apply own regularize', True),
]


def ensure_default_privileges():
    for role, code, label, enabled in DEFAULT_PRIVILEGES:
        RolePrivilege.objects.get_or_create(
            role=role,
            code=code,
            defaults={'label': label, 'enabled': enabled},
        )


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = UserProfile.ROLE_ADMIN if (instance.is_staff or instance.is_superuser) else UserProfile.ROLE_OWNER
        UserProfile.objects.get_or_create(user=instance, defaults={'role': role})
    else:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                'role': UserProfile.ROLE_ADMIN
                if (instance.is_staff or instance.is_superuser)
                else UserProfile.ROLE_OWNER
            },
        )
