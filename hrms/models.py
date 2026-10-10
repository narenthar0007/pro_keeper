from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

mobile_validator = RegexValidator(r'^\d{10}$', 'Enter a 10-digit mobile number.')


class OwnerHrmsSettings(models.Model):
    INDUSTRY_REAL_ESTATE = 'real_estate'
    INDUSTRY_CONSTRUCTION = 'construction'
    INDUSTRY_OTHER = 'other'
    INDUSTRY_CHOICES = [
        (INDUSTRY_REAL_ESTATE, 'Real estate'),
        (INDUSTRY_CONSTRUCTION, 'Construction'),
        (INDUSTRY_OTHER, 'Other'),
    ]

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_settings',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hrms_settings',
    )
    hrms_enabled = models.BooleanField(
        default=False,
        help_text='Admin flips this when the owner subscribes to HRMS',
    )
    industry = models.CharField(
        max_length=30,
        choices=INDUSTRY_CHOICES,
        default=INDUSTRY_OTHER,
    )
    whatsapp_number = models.CharField(
        max_length=10,
        blank=True,
        default='',
        validators=[mobile_validator],
        help_text='10-digit number; 91 is prepended for wa.me links',
    )
    is_paid = models.BooleanField(default=False)
    subscription_ends_on = models.DateField(null=True, blank=True)

    button_color = models.CharField(max_length=20, blank=True, default='')
    header_color = models.CharField(max_length=20, blank=True, default='')
    bg_color = models.CharField(max_length=20, blank=True, default='')
    text_color = models.CharField(max_length=20, blank=True, default='')
    sidebar_color = models.CharField(max_length=20, blank=True, default='')
    button_style = models.CharField(max_length=40, blank=True, default='')
    theme_preset = models.CharField(max_length=40, blank=True, default='')
    theme_edited_at = models.CharField(
        max_length=7,
        blank=True,
        default='',
        help_text='YYYY-MM of last owner theme edit (one change per month)',
    )
    weekly_off_days = models.CharField(
        max_length=20,
        blank=True,
        default='6',
        help_text='Comma-separated weekdays off (0=Mon … 6=Sun). Default Sunday.',
    )
    holiday_calendar_color = models.CharField(
        max_length=20,
        blank=True,
        default='#9333ea',
        help_text='Default color for company holidays on the calendar',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Owner HRMS settings'
        verbose_name_plural = 'Owner HRMS settings'

    def __str__(self):
        state = 'ON' if self.hrms_enabled else 'OFF'
        return f'{self.owner.username} HRMS [{state}]'

    @property
    def theme_locked_this_month(self):
        if not self.theme_edited_at:
            return False
        return self.theme_edited_at == timezone.localdate().strftime('%Y-%m')


class Site(models.Model):
    TYPE_PROJECT = 'project'
    TYPE_HOME = 'home'
    TYPE_RENOVATION = 'renovation'
    TYPE_CONSTRUCTION = 'construction'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_PROJECT, 'Project'),
        (TYPE_HOME, 'Home'),
        (TYPE_RENOVATION, 'Renovation'),
        (TYPE_CONSTRUCTION, 'Construction'),
        (TYPE_OTHER, 'Other'),
    ]
    STATUS_ACTIVE = 'Active'
    STATUS_CLOSED = 'Closed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CLOSED, 'Closed'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_sites',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hrms_sites',
    )
    name = models.CharField(max_length=120)
    site_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PROJECT)
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hrms_sites',
    )
    address = models.CharField(max_length=255, blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hrms_sites_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.owner.username})'


class SiteAssignment(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='assignments')
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_site_assignments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('site', 'manager')
        ordering = ['site__name', 'manager__username']

    def __str__(self):
        return f'{self.manager.username} → {self.site.name}'


class Employee(models.Model):
    APPROVAL_PENDING = 'Pending'
    APPROVAL_APPROVED = 'Approved'
    APPROVAL_REJECTED = 'Rejected'
    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, 'Pending'),
        (APPROVAL_APPROVED, 'Approved'),
        (APPROVAL_REJECTED, 'Rejected'),
    ]
    STATUS_ACTIVE = 'Active'
    STATUS_INACTIVE = 'Inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_employees',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hrms_employees',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hrms_employee',
    )
    emp_code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=10, validators=[mobile_validator])
    joining_date = models.DateField(null=True, blank=True)
    job_role = models.CharField(max_length=80, blank=True, default='')
    team = models.CharField(max_length=80, blank=True, default='')
    leader = models.CharField(max_length=80, blank=True, default='')
    gender = models.CharField(max_length=20, blank=True, default='')
    company_name = models.CharField(max_length=120, blank=True, default='')
    employment_type = models.CharField(max_length=40, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    email = models.EmailField(blank=True, default='')
    emergency = models.CharField(max_length=120, blank=True, default='')
    address = models.CharField(max_length=255, blank=True, default='')
    remarks = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    default_site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_PENDING,
    )
    is_editable = models.BooleanField(default=True)
    is_not_working = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hrms_employees_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['emp_code']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'emp_code'], name='hrms_emp_owner_code_uniq'),
            models.UniqueConstraint(fields=['owner', 'mobile'], name='hrms_emp_owner_mobile_uniq'),
        ]

    def __str__(self):
        return f'{self.emp_code} — {self.name}'

    @property
    def is_approved(self):
        return self.approval_status == self.APPROVAL_APPROVED

    @property
    def can_punch(self):
        return (
            self.is_approved
            and self.status == self.STATUS_ACTIVE
            and not self.is_not_working
        )


class Attendance(models.Model):
    SHIFT_DAY = 'Day'
    SHIFT_NIGHT = 'Night'
    SHIFT_GENERAL = 'General'
    SHIFT_CHOICES = [
        (SHIFT_DAY, 'Day'),
        (SHIFT_NIGHT, 'Night'),
        (SHIFT_GENERAL, 'General'),
    ]
    STATUS_PRESENT = 'Present'
    STATUS_ABSENT = 'Absent'
    STATUS_HALF = 'Half Day'
    STATUS_LEAVE = 'Leave'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Present'),
        (STATUS_ABSENT, 'Absent'),
        (STATUS_HALF, 'Half Day'),
        (STATUS_LEAVE, 'Leave'),
    ]
    REG_YES = 'Yes'
    REG_NO = 'No'
    REG_CHOICES = [(REG_YES, 'Yes'), (REG_NO, 'No')]
    APPROVAL_NA = 'N/A'
    APPROVAL_PENDING = 'Pending'
    APPROVAL_APPROVED = 'Approved'
    APPROVAL_REJECTED = 'Rejected'
    APPROVAL_CHOICES = [
        (APPROVAL_NA, 'N/A'),
        (APPROVAL_PENDING, 'Pending'),
        (APPROVAL_APPROVED, 'Approved'),
        (APPROVAL_REJECTED, 'Rejected'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_attendance',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hrms_attendance',
    )
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance')
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance',
    )
    date = models.DateField(db_index=True)
    punch_in = models.TimeField(null=True, blank=True)
    punch_out = models.TimeField(null=True, blank=True)
    working_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default=SHIFT_GENERAL)
    lat_in = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    long_in = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    lat_out = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    long_out = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    project = models.CharField(max_length=120, blank=True, default='')
    company_name = models.CharField(max_length=120, blank=True, default='')
    overtime = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    regularized = models.CharField(max_length=3, choices=REG_CHOICES, default=REG_NO)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    remark = models.TextField(blank=True, default='')
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_NA,
    )
    punch_code_in = models.CharField(max_length=15, blank=True, default='')
    punch_code_out = models.CharField(max_length=15, blank=True, default='')
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hrms_attendance_marked',
    )
    leave_request = models.ForeignKey(
        'LeaveRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_rows',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'employee__emp_code']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='hrms_attendance_emp_date_uniq'),
        ]

    def __str__(self):
        return f'{self.employee.emp_code} @ {self.date}'

    @property
    def is_late(self):
        if not self.punch_in:
            return False
        return self.punch_in.hour > 9 or (self.punch_in.hour == 9 and self.punch_in.minute > 15)


class SiteDailyUpdate(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='daily_updates')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_site_updates',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hrms_site_updates',
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_updates_posted',
    )
    date = models.DateField(default=timezone.localdate)
    employees_present_count = models.PositiveIntegerField(default=0)
    work_done = models.TextField(blank=True, default='')
    percent_complete = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'manager', 'date'],
                name='hrms_site_update_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.site.name} · {self.date}'


class SiteMaterialEntry(models.Model):
    update = models.ForeignKey(
        SiteDailyUpdate,
        on_delete=models.CASCADE,
        related_name='materials',
    )
    item = models.CharField(max_length=120)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=40, blank=True, default='')
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['item']
        verbose_name_plural = 'Site material entries'

    def __str__(self):
        return f'{self.item} ({self.quantity} {self.unit})'


class LeaveType(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_leave_types',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hrms_leave_types',
    )
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True, default='')
    annual_entitlement = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    color = models.CharField(max_length=20, default='#0b5fff')
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    applicable_roles = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Comma-separated job roles; empty = all employees',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'code'], name='hrms_leave_type_owner_code_uniq'),
        ]

    def __str__(self):
        return f'{self.code} — {self.name}'


class EmployeeLeaveAllocation(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='leave_allocations',
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name='allocations',
    )
    year = models.PositiveIntegerField()
    allocated_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    adjustment_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    carry_forward_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'leave_type__name']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'leave_type', 'year'],
                name='hrms_leave_alloc_emp_type_year_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['employee', 'year']),
        ]

    def __str__(self):
        return f'{self.employee.emp_code} · {self.leave_type.code} · {self.year}'


class LeaveAllocationAuditLog(models.Model):
    allocation = models.ForeignKey(
        EmployeeLeaveAllocation,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_allocation_audits',
    )
    action = models.CharField(max_length=40)
    note = models.CharField(max_length=500, blank=True, default='')
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class LeaveRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='leave_requests',
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name='requests',
    )
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.DecimalField(max_digits=6, decimal_places=2)
    reason = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_requests_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approver_comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['status', 'start_date']),
        ]

    def __str__(self):
        return f'{self.employee.emp_code} · {self.leave_type.code} · {self.status}'


class CompanyHoliday(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hrms_holidays',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hrms_holidays',
    )
    name = models.CharField(max_length=120)
    date = models.DateField()
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=20, blank=True, default='')
    recurring_annual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'date'],
                name='hrms_holiday_owner_date_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.name} · {self.date}'


class LeaveAuditLog(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_audit_logs',
    )
    entity_type = models.CharField(max_length=40)
    entity_id = models.PositiveIntegerField()
    action = models.CharField(max_length=40)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_audits_performed',
    )
    detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
