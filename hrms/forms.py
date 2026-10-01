from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from hrms.models import (
    Attendance,
    Employee,
    OwnerHrmsSettings,
    Site,
    SiteAssignment,
    SiteDailyUpdate,
    SiteMaterialEntry,
)


class EmployeeForm(forms.ModelForm):
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

    def __init__(self, *args, owner=None, sites_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sites_qs is not None:
            self.fields['default_site'].queryset = sites_qs
        elif owner is not None:
            self.fields['default_site'].queryset = Site.objects.filter(owner=owner)
        self.fields['default_site'].required = False


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
    punch_type = forms.ChoiceField(choices=[('in', 'Punch in'), ('out', 'Punch out')])
    latitude = forms.DecimalField(max_digits=10, decimal_places=7)
    longitude = forms.DecimalField(max_digits=10, decimal_places=7)
    site = forms.ModelChoiceField(queryset=Site.objects.none(), required=False)

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
