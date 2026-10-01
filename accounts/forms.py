from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group, User

from .models import Brand, RolePrivilege, UserProfile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True, brand=None):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = UserProfile.ROLE_OWNER
            if brand is not None:
                profile.brand = brand
            profile.save(update_fields=['role', 'brand'])
        return user


class RoleLoginForm(AuthenticationForm):
    """Optional role hint on login page (actual role comes from profile)."""

    role_hint = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Select login type (optional)'),
            (UserProfile.ROLE_ADMIN, 'Admin'),
            (UserProfile.ROLE_OWNER, 'Owner'),
            (UserProfile.ROLE_MANAGER, 'Manager'),
            (UserProfile.ROLE_EMPLOYEE, 'Employee'),
            (UserProfile.ROLE_TENANT, 'Tenant'),
        ],
        label='Login as',
    )


class AdminCreateUserForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(
        choices=[
            (UserProfile.ROLE_OWNER, 'Owner'),
            (UserProfile.ROLE_MANAGER, 'Manager'),
            (UserProfile.ROLE_EMPLOYEE, 'Employee'),
            (UserProfile.ROLE_TENANT, 'Tenant'),
            (UserProfile.ROLE_ADMIN, 'Admin'),
        ]
    )
    notes = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional note'}))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm_password'):
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned

    def save(self, created_by=None, brand=None):
        role = self.cleaned_data['role']
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data.get('email') or '',
            password=self.cleaned_data['password'],
        )
        user.is_staff = role == UserProfile.ROLE_ADMIN
        user.is_superuser = role == UserProfile.ROLE_ADMIN
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.created_by = created_by
        profile.notes = self.cleaned_data.get('notes') or ''
        if brand is not None:
            profile.brand = brand
        profile.save()
        return user


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = [
            'name',
            'slug',
            'tagline',
            'footer_text',
            'hostnames',
            'base_url',
            'logo',
            'icon',
            'banner',
            'is_default',
            'is_active',
            'primary_color',
            'secondary_color',
            'button_color',
            'button_text_color',
            'background_color',
            'surface_color',
            'text_color',
            'header_color',
            'header_text_color',
            'header_active_color',
            'footer_bg_color',
            'footer_text_color',
            'font_style',
            'table_format',
            'border_radius',
        ]
        widgets = {
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color'}),
            'button_color': forms.TextInput(attrs={'type': 'color'}),
            'button_text_color': forms.TextInput(attrs={'type': 'color'}),
            'background_color': forms.TextInput(attrs={'type': 'color'}),
            'surface_color': forms.TextInput(attrs={'type': 'color'}),
            'text_color': forms.TextInput(attrs={'type': 'color'}),
            'header_color': forms.TextInput(attrs={'type': 'color'}),
            'header_text_color': forms.TextInput(attrs={'type': 'color'}),
            'header_active_color': forms.TextInput(attrs={'type': 'color'}),
            'footer_bg_color': forms.TextInput(attrs={'type': 'color'}),
            'footer_text_color': forms.TextInput(attrs={'type': 'color'}),
            'footer_text': forms.TextInput(attrs={'style': 'min-width:280px'}),
            'hostnames': forms.TextInput(attrs={'style': 'min-width:280px'}),
            'base_url': forms.TextInput(attrs={'style': 'min-width:280px'}),
        }


# Backward-compatible name
SiteThemeForm = BrandForm


class SitePromotionForm(forms.ModelForm):
    class Meta:
        from properties.models import SitePromotion

        model = SitePromotion
        fields = [
            'title',
            'description',
            'image',
            'cta_label',
            'cta_url',
            'placement',
            'sort_order',
            'is_active',
            'start_date',
            'end_date',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class PrivilegeToggleForm(forms.Form):
    """Dynamic form built from RolePrivilege queryset."""

    def __init__(self, privileges, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for priv in privileges:
            self.fields[f'priv_{priv.pk}'] = forms.BooleanField(
                required=False,
                initial=priv.enabled,
                label=f'{priv.get_role_display()}: {priv.label}',
            )


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']


class RentReminderSettingsForm(forms.ModelForm):
    """Owner/tenant settings for rent reminders and profile photo."""

    class Meta:
        model = UserProfile
        fields = [
            'avatar',
            'rent_reminder_enabled',
            'rent_due_day',
            'reminder_days_before',
            'reminder_email_enabled',
        ]
        widgets = {
            'rent_due_day': forms.NumberInput(attrs={'min': 1, 'max': 28, 'step': 1}),
            'reminder_days_before': forms.NumberInput(attrs={'min': 0, 'max': 14, 'step': 1}),
        }

    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        is_tenant = role == UserProfile.ROLE_TENANT
        self.fields['rent_reminder_enabled'].label = (
            'Remind me to pay rent' if is_tenant else 'Remind me to collect rent'
        )
        self.fields['rent_reminder_enabled'].help_text = (
            'A banner appears in the app from the reminder day until rent is paid.'
            if is_tenant
            else 'A banner appears in the app for occupied properties that still have unpaid rent.'
        )
        self.fields['rent_due_day'].label = 'Rent due day of month'
        self.fields['rent_due_day'].help_text = 'Use 1–28 so the date exists every month.'
        self.fields['reminder_days_before'].label = 'Remind me this many days before'
        self.fields['reminder_days_before'].help_text = (
            '0 means only on the due date. 3 means you are reminded 3 days early.'
        )
        self.fields['reminder_email_enabled'].label = 'Also email me'
        self.fields['reminder_email_enabled'].help_text = (
            'Uses the email address on your account. Sent once per month when rent is still unpaid.'
        )
