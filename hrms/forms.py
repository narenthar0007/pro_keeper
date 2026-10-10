from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from hrms.models import (
    Attendance,
    CompanyHoliday,
    Employee,
    EmployeeLeaveAllocation,
    LeaveType,
    OwnerHrmsSettings,
    Site,
    SiteAssignment,
    SiteDailyUpdate,
    SiteMaterialEntry,
)


class EmployeeForm(forms.ModelForm):
    can_login = forms.BooleanField(
        required=False,
        initial=False,
        label='Can login',
        help_text='Allow this employee to sign in, punch in/out, apply regularize, and view their attendance.',
    )
    login_username = forms.CharField(
        max_length=150,
        required=False,
        label='Login username',
    )
    login_password = forms.CharField(
        required=False,
        label='Login password',
        widget=forms.PasswordInput(render_value=True),
    )

    class Meta:
        model = Employee
        fields = [
            'emp_code',
            'name',
            'mobile',
            'joining_date',
            'job_role',
            'team',
            'leader',
            'gender',
            'company_name',
            'employment_type',
            'status',
            'email',
            'emergency',
            'address',
            'remarks',
            'latitude',
            'longitude',
            'default_site',
            'is_not_working',
        ]
        widgets = {
            'joining_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
            'address': forms.TextInput(),
        }
        labels = {
            'is_not_working': 'Not working',
        }
        help_texts = {
            'is_not_working': 'Checked means this person cannot punch in or out.',
        }

    def __init__(self, *args, owner=None, sites_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sites_qs is not None:
            self.fields['default_site'].queryset = sites_qs
        elif owner is not None:
            self.fields['default_site'].queryset = Site.objects.filter(owner=owner)
        self.fields['default_site'].required = False
        if self.instance.pk and self.instance.user_id:
            self.fields['can_login'].initial = True
            self.fields['login_username'].initial = self.instance.user.username
        self.order_fields(
            [
                'emp_code',
                'name',
                'mobile',
                'joining_date',
                'job_role',
                'team',
                'leader',
                'gender',
                'company_name',
                'employment_type',
                'status',
                'email',
                'emergency',
                'address',
                'remarks',
                'latitude',
                'longitude',
                'default_site',
                'is_not_working',
                'can_login',
                'login_username',
                'login_password',
            ]
        )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('can_login'):
            return cleaned
        username = (cleaned.get('login_username') or '').strip()
        if not username:
            username = (cleaned.get('emp_code') or '').strip()
            cleaned['login_username'] = username
        if not username:
            self.add_error('login_username', 'Enter a username or employee code.')
        else:
            existing_pk = self.instance.user_id if self.instance.pk else None
            clash = User.objects.filter(username=username)
            if existing_pk:
                clash = clash.exclude(pk=existing_pk)
            if clash.exists():
                self.add_error('login_username', 'Username already exists.')
        password = cleaned.get('login_password') or ''
        is_new_login = not (self.instance.pk and self.instance.user_id)
        if is_new_login and not password:
            self.add_error('login_password', 'Password is required when Can login is enabled.')
        return cleaned


class ManagerCreateForm(forms.Form):
    emp_code = forms.CharField(max_length=40)
    name = forms.CharField(max_length=120)
    mobile = forms.CharField(max_length=10)
    email = forms.EmailField(required=False)
    latitude = forms.DecimalField(max_digits=10, decimal_places=7)
    longitude = forms.DecimalField(max_digits=10, decimal_places=7)
    default_site = forms.ModelChoiceField(queryset=Site.objects.none(), required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    username = forms.CharField(max_length=150, required=False)

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields['default_site'].queryset = Site.objects.filter(owner=owner)

    def clean_mobile(self):
        mobile = self.cleaned_data['mobile']
        if not mobile.isdigit() or len(mobile) != 10:
            raise forms.ValidationError('Enter a 10-digit mobile number.')
        return mobile

    def clean_username(self):
        username = self.cleaned_data.get('username') or ''
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already exists.')
        return username


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = [
            'name',
            'site_type',
            'property',
            'address',
            'latitude',
            'longitude',
            'status',
        ]

    def __init__(self, *args, properties_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['property'].required = False
        if properties_qs is not None:
            from properties.models import Property

            if hasattr(properties_qs, 'model'):
                self.fields['property'].queryset = properties_qs
            else:
                self.fields['property'].queryset = Property.objects.none()
        else:
            from properties.models import Property

            self.fields['property'].queryset = Property.objects.all()


class SiteAssignForm(forms.Form):
    manager = forms.ModelChoiceField(queryset=User.objects.none())

    def __init__(self, *args, managers_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if managers_qs is not None:
            self.fields['manager'].queryset = managers_qs


class AttendanceMarkForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = [
            'employee',
            'date',
            'punch_in',
            'punch_out',
            'shift',
            'status',
            'site',
            'remark',
            'overtime',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'punch_in': forms.TimeInput(attrs={'type': 'time'}),
            'punch_out': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, employees_qs=None, sites_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employees_qs is not None:
            self.fields['employee'].queryset = employees_qs
        if sites_qs is not None:
            self.fields['site'].queryset = sites_qs
        self.fields['date'].initial = timezone.localdate()


class PunchForm(forms.Form):
    punch_type = forms.ChoiceField(
        label='Punch',
        choices=[('in', 'Punch in'), ('out', 'Punch out')],
    )
    latitude = forms.DecimalField(label='Latitude', max_digits=10, decimal_places=7)
    longitude = forms.DecimalField(label='Longitude', max_digits=10, decimal_places=7)
    site = forms.ModelChoiceField(
        label='Site',
        queryset=Site.objects.none(),
        required=False,
        empty_label='Select site',
    )

    def __init__(self, *args, sites_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sites_qs is not None:
            self.fields['site'].queryset = sites_qs


class RegularizeForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, employees_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employees_qs is not None:
            self.fields['employee'].queryset = employees_qs
        self.fields['date'].initial = timezone.localdate()


class SiteDailyUpdateForm(forms.ModelForm):
    class Meta:
        model = SiteDailyUpdate
        fields = [
            'site',
            'date',
            'employees_present_count',
            'work_done',
            'percent_complete',
            'notes',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'work_done': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, sites_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sites_qs is not None:
            self.fields['site'].queryset = sites_qs
        self.fields['date'].initial = timezone.localdate()


class MaterialForm(forms.ModelForm):
    class Meta:
        model = SiteMaterialEntry
        fields = ['item', 'quantity', 'unit', 'cost']


class OwnerHrmsSettingsForm(forms.ModelForm):
    class Meta:
        model = OwnerHrmsSettings
        fields = [
            'whatsapp_number',
            'industry',
            'button_color',
            'header_color',
            'bg_color',
            'text_color',
            'sidebar_color',
            'button_style',
            'theme_preset',
        ]
        widgets = {
            'button_color': forms.TextInput(attrs={'type': 'color'}),
            'header_color': forms.TextInput(attrs={'type': 'color'}),
            'bg_color': forms.TextInput(attrs={'type': 'color'}),
            'text_color': forms.TextInput(attrs={'type': 'color'}),
            'sidebar_color': forms.TextInput(attrs={'type': 'color'}),
        }


class AdminOwnerHrmsEnableForm(forms.ModelForm):
    class Meta:
        model = OwnerHrmsSettings
        fields = [
            'hrms_enabled',
            'industry',
            'whatsapp_number',
            'is_paid',
            'subscription_ends_on',
        ]
        widgets = {
            'subscription_ends_on': forms.DateInput(attrs={'type': 'date'}),
        }


class PunchDecodeForm(forms.Form):
    code = forms.CharField(max_length=15, min_length=15, label='15-char punch code')


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = [
            'name',
            'code',
            'description',
            'annual_entitlement',
            'color',
            'is_paid',
            'is_active',
            'applicable_roles',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'color': forms.TextInput(attrs={'type': 'color'}),
            'annual_entitlement': forms.NumberInput(attrs={'step': '0.5', 'min': '0'}),
        }


class CompanyHolidayForm(forms.ModelForm):
    class Meta:
        model = CompanyHoliday
        fields = ['name', 'date', 'description', 'color', 'recurring_annual']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }


class LeaveAllocationForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    leave_type = forms.ModelChoiceField(queryset=LeaveType.objects.none())
    year = forms.IntegerField(min_value=2000, max_value=2100)
    allocated_days = forms.DecimalField(min_value=0, max_digits=6, decimal_places=2)
    adjustment_days = forms.DecimalField(
        required=False,
        min_value=Decimal('-365'),
        max_digits=6,
        decimal_places=2,
        initial=Decimal('0'),
    )
    carry_forward_days = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=6,
        decimal_places=2,
        initial=Decimal('0'),
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, employees_qs=None, types_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employees_qs is not None:
            self.fields['employee'].queryset = employees_qs
        if types_qs is not None:
            self.fields['leave_type'].queryset = types_qs
        self.fields['year'].initial = timezone.localdate().year


class LeaveApplyForm(forms.Form):
    leave_type = forms.ModelChoiceField(queryset=LeaveType.objects.none())
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, employee=None, types_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        if types_qs is not None:
            self.fields['leave_type'].queryset = types_qs

    def clean(self):
        cleaned = super().clean()
        if not self.employee:
            return cleaned
        from hrms.services.leave import validate_leave_request

        try:
            days = validate_leave_request(
                self.employee,
                cleaned['leave_type'],
                cleaned['start_date'],
                cleaned['end_date'],
            )
            cleaned['days_requested'] = days
        except forms.ValidationError:
            raise
        except Exception as exc:
            from django.core.exceptions import ValidationError as DjangoValidationError

            if isinstance(exc, DjangoValidationError):
                raise forms.ValidationError(exc.messages)
            raise forms.ValidationError(str(exc))
        return cleaned


class LeaveDecisionForm(forms.Form):
    action = forms.ChoiceField(choices=[('approve', 'Approve'), ('reject', 'Reject')])
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == 'reject' and not (cleaned.get('comment') or '').strip():
            self.add_error('comment', 'Rejection reason is required.')
        return cleaned
