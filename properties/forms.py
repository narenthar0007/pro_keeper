from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Amenity,
    Building,
    CampaignCollaborator,
    OTHERS_AMENITY_CODE,
    ensure_default_amenities,
    Complaint,
    Document,
    Enquiry,
    Expense,
    LeadVisit,
    MarketingCampaign,
    MeterReading,
    Offer,
    Property,
    PropertyImage,
    PropertyShare,
    RentPayment,
    SaleDeal,
    Tenant,
)


def get_or_create_custom_amenity(label):
    label = (label or '').strip()
    if not label:
        return None
    existing = Amenity.objects.filter(label__iexact=label).exclude(code=OTHERS_AMENITY_CODE).first()
    if existing:
        return existing
    base = slugify(label)[:40] or 'custom'
    code = base
    n = 2
    while Amenity.objects.filter(code=code).exists():
        suffix = f'-{n}'
        code = f'{base[: 40 - len(suffix)]}{suffix}'
        n += 1
    return Amenity.objects.create(code=code, label=label[:80])


class PropertyForm(forms.ModelForm):
    new_building_name = forms.CharField(
        required=False,
        max_length=200,
        label='Or type a building name',
        help_text='Type an existing building name to reuse it for another shop or home.',
    )
    add_other_amenity = forms.BooleanField(
        required=False,
        label='Others',
    )
    other_amenity = forms.CharField(
        required=False,
        max_length=80,
        label='Specify other amenity',
        widget=forms.TextInput(attrs={'placeholder': 'Type the amenity name'}),
    )

    class Meta:
        model = Property
        fields = [
            'title',
            'description',
            'listing_type',
            'door_number',
            'street',
            'landmark',
            'address',
            'city',
            'state',
            'pincode',
            'country',
            'latitude',
            'longitude',
            'contact_phone',
            'property_type',
            'bedrooms',
            'bathrooms',
            'rooms',
            'kitchens',
            'area_sqft',
            'year_of_building',
            'monthly_rent',
            'advance_amount',
            'sale_price',
            'sale_status',
            'price_negotiable',
            'furnishing',
            'possession_date',
            'allow_tenant_marketing',
            'is_listed_publicly',
            'is_occupied',
            'building',
            'unit_number',
            'floor_number',
            'amenities',
            'late_fee_amount',
            'late_fee_grace_days',
            'featured_image',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. 2BHK near Metro'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the property...'}),
            'listing_type': forms.Select(),
            'door_number': forms.TextInput(attrs={'placeholder': 'e.g. 12A'}),
            'street': forms.TextInput(attrs={'placeholder': 'Street name'}),
            'landmark': forms.TextInput(attrs={'placeholder': 'Nearby landmark'}),
            'address': forms.TextInput(attrs={'placeholder': 'Full address'}),
            'city': forms.TextInput(attrs={'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'placeholder': 'State'}),
            'pincode': forms.TextInput(attrs={'placeholder': 'e.g. 600001'}),
            'country': forms.TextInput(attrs={'placeholder': 'Country'}),
            'latitude': forms.NumberInput(attrs={'placeholder': 'Optional', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'placeholder': 'Optional', 'step': '0.000001'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': '919876543210'}),
            'area_sqft': forms.NumberInput(attrs={'placeholder': 'e.g. 1200'}),
            'year_of_building': forms.NumberInput(attrs={'placeholder': 'e.g. 2018', 'min': 1800}),
            'monthly_rent': forms.NumberInput(attrs={'placeholder': 'Monthly rent', 'class': 'rent-field'}),
            'advance_amount': forms.NumberInput(attrs={'placeholder': 'Advance / deposit', 'class': 'rent-field'}),
            'sale_price': forms.NumberInput(attrs={'placeholder': 'Sale price', 'class': 'sale-field'}),
            'possession_date': forms.DateInput(attrs={'type': 'date', 'class': 'sale-field'}),
            'late_fee_grace_days': forms.NumberInput(attrs={'min': 0}),
            'rooms': forms.NumberInput(attrs={'min': 0}),
            'kitchens': forms.NumberInput(attrs={'min': 0}),
            'amenities': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, brand=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._form_user = user
        self._form_brand = brand
        ensure_default_amenities()
        self.fields['building'].required = False
        self.fields['amenities'].required = False
        self.fields['amenities'].queryset = Amenity.objects.exclude(
            code=OTHERS_AMENITY_CODE
        ).order_by('label')
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].help_text = 'Select every amenity that applies. Tick Others to type a custom one.'
        if user is not None and brand is not None:
            self.fields['building'].queryset = Building.for_user(user, brand=brand).order_by('name')
        else:
            self.fields['building'].queryset = Building.objects.none()
        self.fields['building'].empty_label = 'No building / standalone'
        self.fields['advance_amount'].required = False
        self.fields['late_fee_amount'].required = False
        self.fields['late_fee_grace_days'].required = False
        self.fields['rooms'].required = False
        self.fields['kitchens'].required = False
        self.fields['bedrooms'].required = False
        self.fields['bathrooms'].required = False
        self.fields['building'].help_text = (
            'You can pick the same building for every shop or home in it. '
            'Give each unit a unique unit or door number.'
        )
        self.fields['unit_number'].help_text = (
            'Unique shop / flat / room number in this building. Copied from door number if left blank.'
        )

    def amenity_checkbox_items(self):
        selected = set()
        if self.is_bound:
            selected = {str(value) for value in self.data.getlist('amenities')}
        elif self.instance and self.instance.pk:
            selected = {
                str(pk)
                for pk in self.instance.amenities.exclude(code=OTHERS_AMENITY_CODE).values_list(
                    'pk', flat=True
                )
            }
        return [
            {
                'id': amenity.pk,
                'label': amenity.label,
                'checked': str(amenity.pk) in selected,
            }
            for amenity in self.fields['amenities'].queryset
        ]

    def clean(self):
        cleaned = super().clean()
        listing_type = cleaned.get('listing_type')
        selected = [item for item in (cleaned.get('amenities') or []) if item.code != OTHERS_AMENITY_CODE]
        cleaned['amenities'] = selected
        if cleaned.get('add_other_amenity'):
            if not (cleaned.get('other_amenity') or '').strip():
                self.add_error('other_amenity', 'Type the custom amenity name.')
        else:
            cleaned['other_amenity'] = ''

        if listing_type == 'rent':
            if not cleaned.get('monthly_rent'):
                self.add_error('monthly_rent', 'Monthly rent is required for rent listings.')
        elif listing_type == 'sale':
            if not cleaned.get('sale_price'):
                self.add_error('sale_price', 'Sale price is required for sale listings.')
            cleaned['is_occupied'] = False

        building = cleaned.get('building')
        new_name = (cleaned.get('new_building_name') or '').strip()
        user = self._form_user
        brand = self._form_brand
        if new_name and user is not None and brand is not None:
            existing = Building.objects.filter(
                owner=user, brand=brand, name__iexact=new_name
            ).first()
            if existing:
                building = existing
                cleaned['building'] = existing
            elif not building:
                building = Building(
                    owner=user,
                    brand=brand,
                    name=new_name,
                    address=cleaned.get('address') or new_name,
                    city=cleaned.get('city') or '',
                    state=cleaned.get('state') or '',
                    pincode=cleaned.get('pincode') or '',
                    country=cleaned.get('country') or 'India',
                    street=cleaned.get('street') or '',
                    landmark=cleaned.get('landmark') or '',
                    latitude=cleaned.get('latitude'),
                    longitude=cleaned.get('longitude'),
                    year_of_building=cleaned.get('year_of_building'),
                )
                cleaned['_new_building'] = building
                cleaned['building'] = building

        unit = (cleaned.get('unit_number') or cleaned.get('door_number') or '').strip()
        if building and not unit:
            count = 1
            if getattr(building, 'pk', None):
                count = building.units.count() + 1
            unit = f'U{count}'
            cleaned['unit_number'] = unit
        elif unit:
            cleaned['unit_number'] = unit

        if building and getattr(building, 'pk', None) and unit:
            clash = Property.objects.filter(building=building, unit_number=unit)
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error(
                    'unit_number',
                    'That unit number is already used in this building. Use a different shop or flat number.',
                )
        return cleaned

    def save(self, commit=True):
        new_building = self.cleaned_data.pop('_new_building', None)
        if new_building is not None and new_building.pk is None:
            new_building.save()
            self.cleaned_data['building'] = new_building
            self.instance.building = new_building
        instance = super().save(commit=commit)
        if commit:
            self._save_other_amenity(instance)
        return instance

    def _save_other_amenity(self, instance):
        extra = get_or_create_custom_amenity(self.cleaned_data.get('other_amenity'))
        if extra:
            instance.amenities.add(extra)


class MarketingCampaignForm(forms.ModelForm):
    class Meta:
        model = MarketingCampaign
        fields = [
            'property',
            'title',
            'channel',
            'listing_url',
            'budget',
            'spend',
            'status',
            'start_date',
            'end_date',
            'photos_per_day',
            'videos_per_day',
            'content_reminder_note',
            'leads_count',
            'notes',
            'cover_image',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'content_reminder_note': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'e.g. Film a short walkthrough video for this seller today',
                }
            ),
            'listing_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'photos_per_day': forms.NumberInput(attrs={'min': 0}),
            'videos_per_day': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, user=None, brand=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Property.objects.none()
        if user is not None and brand is not None:
            qs = Property.for_user(user, brand=brand).order_by('title')
        self.fields['property'].queryset = qs
        self.fields['photos_per_day'].label = 'Photo posts per day'
        self.fields['videos_per_day'].label = 'Video posts per day'
        self.fields['content_reminder_note'].label = 'Reminder note for collaborators'
        self.fields['content_reminder_note'].help_text = (
            'Sent by the background job if daily posts/videos are missing.'
        )


class CampaignContentLogForm(forms.Form):
    photos_count = forms.IntegerField(min_value=0, initial=0, label='Photos posted today')
    videos_count = forms.IntegerField(min_value=0, initial=0, label='Videos posted today')
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
        label='Note',
    )


class CampaignCollaboratorInviteForm(forms.Form):
    username = forms.CharField(max_length=150)
    role = forms.ChoiceField(choices=CampaignCollaborator.ROLE_CHOICES, initial='creator')
    can_edit = forms.BooleanField(required=False, initial=True)
    can_publish = forms.BooleanField(required=False, initial=False)
    invite_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Message to collaborator',
        help_text='This appears in their Marketing inbox as your collaboration request.',
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise forms.ValidationError('No user with that username.') from exc


class TenantForm(forms.ModelForm):
    existing_username = forms.CharField(
        required=False,
        max_length=150,
        label='Existing login username',
        help_text='If this tenant already has an account, type their username to attach them.',
    )
    create_username = forms.CharField(
        required=False,
        max_length=150,
        label='New login username',
        help_text='Create portal login for a tenant who is not in the system yet.',
    )
    create_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label='New login password',
    )
    create_password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label='Confirm password',
    )

    class Meta:
        model = Tenant
        fields = [
            'name',
            'phone',
            'email',
            'move_in_date',
            'lease_end_date',
            'advance_paid',
            'advance_deduction',
            'advance_refunded',
            'lease_document',
            'photo',
            'notes',
            'is_active',
        ]
        widgets = {
            'move_in_date': forms.DateInput(attrs={'type': 'date'}),
            'lease_end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields['existing_username'].initial = self.instance.user.username
            self.fields['existing_username'].help_text = (
                f'Currently linked to {self.instance.user.username}. Leave as-is or change.'
            )

    def clean_existing_username(self):
        username = (self.cleaned_data.get('existing_username') or '').strip()
        if not username:
            return ''
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise forms.ValidationError('No user with that username.') from exc

    def clean(self):
        cleaned = super().clean()
        create_username = (cleaned.get('create_username') or '').strip()
        password = cleaned.get('create_password') or ''
        password2 = cleaned.get('create_password2') or ''
        existing = cleaned.get('existing_username')
        if create_username and existing:
            self.add_error('create_username', 'Attach an existing user or create a new login, not both.')
        if create_username:
            if User.objects.filter(username=create_username).exists():
                self.add_error(
                    'create_username',
                    'Username already exists. Attach them with existing username instead.',
                )
            if not password:
                self.add_error('create_password', 'Password is required to create a login.')
            elif password != password2:
                self.add_error('create_password2', 'Passwords do not match.')
        elif password or password2:
            self.add_error('create_username', 'Enter a username to create login details.')
        return cleaned


class TenantLoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

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


class PlannedVacateForm(forms.Form):
    planned_vacate_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Vacate date',
        help_text='Pick a future date when this tenant will leave.',
    )

    def clean_planned_vacate_date(self):
        value = self.cleaned_data['planned_vacate_date']
        if value <= timezone.localdate():
            raise forms.ValidationError('Choose a future date.')
        return value


class JoinRequestForm(forms.Form):
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional message to the owner'}),
    )


class AdminBroadcastForm(forms.Form):
    AUDIENCE_CHOICES = [
        ('all', 'All users'),
        ('owners', 'Owners'),
        ('tenants', 'Tenants'),
        ('selected', 'Selected users'),
    ]
    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES, initial='all')
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Selected users',
    )
    title = forms.CharField(max_length=200, initial='Message from admin')
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, *args, users=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['users'].queryset = users if users is not None else User.objects.none()
        self.fields['users'].help_text = 'Used when audience is Selected users. Hold Ctrl to pick more than one.'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('audience') == 'selected' and not cleaned.get('users'):
            self.add_error('users', 'Select at least one user.')
        return cleaned


class RentReminderForm(forms.Form):
    tenants = forms.ModelMultipleChoiceField(
        queryset=Tenant.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label='Tenants',
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        initial='This is a reminder to pay this month’s rent. Please check your tenant portal.',
    )

    def __init__(self, *args, tenants=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenants'].queryset = tenants if tenants is not None else Tenant.objects.none()
        self.fields['tenants'].label_from_instance = (
            lambda t: f'{t.name} · {t.property.title}'
            + (f' (@{t.user.username})' if t.user_id else ' (no login)')
        )


class RentPaymentForm(forms.ModelForm):
    class Meta:
        model = RentPayment
        fields = ['tenant', 'amount', 'payment_date', 'month_for', 'due_date', 'status', 'late_fee', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'month_for': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Optional note'}),
        }

    def __init__(self, *args, property_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        if property_obj is not None:
            self.fields['tenant'].queryset = property_obj.tenants.all()
            self.fields['tenant'].required = False


class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ['image', 'caption', 'is_cover']


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'category', 'amount', 'expense_date', 'notes']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Optional note'}),
        }


class EnquiryForm(forms.ModelForm):
    class Meta:
        model = Enquiry
        fields = ['name', 'email', 'phone', 'message', 'preferred_move_in']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Ask about availability, visit timing...'}),
            'name': forms.TextInput(attrs={'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Phone (optional)'}),
            'preferred_move_in': forms.DateInput(attrs={'type': 'date'}),
        }


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['title', 'description', 'category', 'priority', 'photo']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Short title'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class ComplaintOwnerForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['status', 'owner_notes']
        widgets = {
            'owner_notes': forms.Textarea(attrs={'rows': 3}),
        }


class PropertyShareForm(forms.ModelForm):
    username = forms.CharField(max_length=150, help_text='Username of the person to share with')

    class Meta:
        model = PropertyShare
        fields = ['role', 'commission_percent']

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise forms.ValidationError('No user with that username.') from exc


class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = [
            'name',
            'description',
            'street',
            'landmark',
            'address',
            'city',
            'state',
            'pincode',
            'country',
            'latitude',
            'longitude',
            'year_of_building',
            'total_floors',
            'amenities',
            'notes',
            'is_active',
            'photo',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'latitude': forms.NumberInput(attrs={'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'step': '0.000001'}),
            'amenities': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amenities'].required = False
        self.fields['amenities'].queryset = Amenity.objects.all().order_by('label')
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()


class AttachUnitForm(forms.Form):
    property_id = forms.IntegerField()
    unit_number = forms.CharField(max_length=40, required=False)
    floor_number = forms.IntegerField(required=False, min_value=0)


class LeadStatusForm(forms.ModelForm):
    class Meta:
        model = Enquiry
        fields = ['status', 'source', 'assigned_to', 'owner_notes', 'lost_reason']
        widgets = {
            'owner_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, users=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = users if users is not None else User.objects.none()
        self.fields['assigned_to'].queryset = qs
        self.fields['assigned_to'].required = False


class LeadVisitForm(forms.ModelForm):
    class Meta:
        model = LeadVisit
        fields = ['property', 'scheduled_at', 'status', 'notes']
        widgets = {
            'scheduled_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, properties=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scheduled_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']
        if properties is not None:
            self.fields['property'].queryset = properties


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ['offer_type', 'amount', 'status', 'valid_until', 'notes']
        widgets = {
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class SaleDealForm(forms.ModelForm):
    class Meta:
        model = SaleDeal
        fields = [
            'agreed_price',
            'token_amount',
            'token_date',
            'agreement_date',
            'registration_date',
            'status',
            'commission_percent',
            'notes',
        ]
        widgets = {
            'token_date': forms.DateInput(attrs={'type': 'date'}),
            'agreement_date': forms.DateInput(attrs={'type': 'date'}),
            'registration_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'doc_type', 'file', 'expires_on', 'tenant']
        widgets = {
            'expires_on': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, property_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenant'].required = False
        if property_obj is not None:
            self.fields['tenant'].queryset = property_obj.tenants.all()
        else:
            self.fields['tenant'].queryset = Tenant.objects.none()


class MeterReadingForm(forms.ModelForm):
    class Meta:
        model = MeterReading
        fields = ['meter_type', 'reading_value', 'reading_date', 'billed_amount', 'photo']
        widgets = {
            'reading_date': forms.DateInput(attrs={'type': 'date'}),
        }


class MessageForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write a message…'}))
