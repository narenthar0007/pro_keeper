from django import forms
from django.contrib.auth.models import User

from .models import (
    Amenity,
    Building,
    CampaignCollaborator,
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


class PropertyForm(forms.ModelForm):
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
        }

    def __init__(self, *args, user=None, brand=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['building'].required = False
        self.fields['amenities'].required = False
        self.fields['amenities'].queryset = Amenity.objects.all().order_by('label')
        if user is not None and brand is not None:
            self.fields['building'].queryset = Building.for_user(user, brand=brand).order_by('name')
        else:
            self.fields['building'].queryset = Building.objects.none()
        self.fields['building'].help_text = 'Optional. Attach this listing to a building as a unit.'
        self.fields['unit_number'].help_text = 'Room / flat number. Copied from door number if left blank.'

    def clean(self):
        cleaned = super().clean()
        listing_type = cleaned.get('listing_type')
        if listing_type == 'rent':
            if not cleaned.get('monthly_rent'):
                self.add_error('monthly_rent', 'Monthly rent is required for rent listings.')
        elif listing_type == 'sale':
            if not cleaned.get('sale_price'):
                self.add_error('sale_price', 'Sale price is required for sale listings.')
            cleaned['is_occupied'] = False
        return cleaned


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
    class Meta:
        model = Tenant
        fields = [
            'name',
            'phone',
            'email',
            'user',
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
        self.fields['user'].queryset = User.objects.order_by('username')
        self.fields['user'].required = False
        self.fields['user'].help_text = 'Optional: link a registered user for tenant portal access'


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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amenities'].required = False
        self.fields['amenities'].queryset = Amenity.objects.all().order_by('label')


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

