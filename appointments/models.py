from django.conf import settings
from django.db import models
from django.utils import timezone


class AppointmentAvailability(models.Model):
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointment_availabilities',
    )
    day_of_week = models.PositiveSmallIntegerField(
        help_text='0=Sunday … 6=Saturday',
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveSmallIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']
        verbose_name_plural = 'Appointment availabilities'

    def __str__(self):
        return f'{self.host_id} · day {self.day_of_week} · {self.start_time}-{self.end_time}'


class AppointmentSettings(models.Model):
    host = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointment_settings',
    )
    slot_duration_minutes = models.PositiveSmallIntegerField(default=30)
    buffer_minutes = models.PositiveSmallIntegerField(default=0)
    minimum_notice_hours = models.PositiveSmallIntegerField(default=2)
    maximum_advance_days = models.PositiveSmallIntegerField(default=30)
    pending_blocks_slot = models.BooleanField(
        default=True,
        help_text='When true, pending external requests block the slot from new bookings.',
    )
    timezone_name = models.CharField(max_length=64, default='Asia/Kolkata')
    public_display_name = models.CharField(max_length=120, blank=True, default='')
    public_designation = models.CharField(max_length=120, blank=True, default='')
    public_description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Appointment settings · {self.host_id}'


class AppointmentHoliday(models.Model):
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointment_holidays',
    )
    holiday_date = models.DateField()
    reason = models.CharField(max_length=200, blank=True, default='')
    is_full_day = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['holiday_date']

    def __str__(self):
        return f'{self.holiday_date} · {self.host_id}'


class Appointment(models.Model):
    BOOKED_HOST = 'HOST'
    BOOKED_EXTERNAL = 'EXTERNAL_GUEST'
    BOOKED_BY_CHOICES = [
        (BOOKED_HOST, 'Self-created'),
        (BOOKED_EXTERNAL, 'External link'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_RESCHEDULE_PROPOSED = 'RESCHEDULE_PROPOSED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_RESCHEDULE_PROPOSED, 'Reschedule proposed'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    TYPE_ONLINE = 'online'
    TYPE_OFFLINE = 'offline'
    TYPE_CHOICES = [
        (TYPE_ONLINE, 'Online'),
        (TYPE_OFFLINE, 'Offline'),
    ]

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hosted_appointments',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='org_appointments',
        help_text='Organization owner for data isolation.',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    guest_name = models.CharField(max_length=120)
    guest_email = models.EmailField(blank=True, default='')
    guest_phone = models.CharField(max_length=20, blank=True, default='')
    guest_company = models.CharField(max_length=120, blank=True, default='')
    appointment_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_OFFLINE,
    )
    meeting_location = models.CharField(max_length=255, blank=True, default='')
    meeting_link = models.URLField(blank=True, default='')
    booked_by = models.CharField(max_length=20, choices=BOOKED_BY_CHOICES)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_PENDING)
    rejection_reason = models.CharField(max_length=500, blank=True, default='')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_appointments',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    alternative_date = models.DateField(null=True, blank=True)
    alternative_start_time = models.TimeField(null=True, blank=True)
    alternative_end_time = models.TimeField(null=True, blank=True)
    public_response_token = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-appointment_date', '-start_time']
        indexes = [
            models.Index(fields=['host', 'appointment_date', 'status']),
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self):
        return f'{self.title} · {self.appointment_date} · {self.status}'

    @property
    def reference_id(self):
        return f'APT-{self.pk:06d}'


class AppointmentAuditLog(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    actor_type = models.CharField(max_length=40, blank=True, default='')
    action = models.CharField(max_length=60)
    old_status = models.CharField(max_length=24, blank=True, default='')
    new_status = models.CharField(max_length=24, blank=True, default='')
    description = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AppointmentNotification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointment_notifications',
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    notification_type = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


def log_appointment_action(appointment, *, actor, action, old_status='', new_status='', description=''):
    AppointmentAuditLog.objects.create(
        appointment=appointment,
        actor=actor,
        actor_type='user' if actor else 'system',
        action=action,
        old_status=old_status or '',
        new_status=new_status or appointment.status,
        description=description,
    )


def notify_host(appointment, notification_type, title, message):
    AppointmentNotification.objects.create(
        recipient=appointment.host,
        appointment=appointment,
        notification_type=notification_type,
        title=title,
        message=message,
    )


def mark_notification_read(notification):
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
