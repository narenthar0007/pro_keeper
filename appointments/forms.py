from django import forms

from appointments.models import Appointment, AppointmentAvailability, AppointmentSettings


class AppointmentCreateForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'title',
            'description',
            'guest_name',
            'guest_email',
            'guest_phone',
            'guest_company',
            'appointment_date',
            'start_time',
            'end_time',
            'appointment_type',
            'meeting_location',
            'meeting_link',
        ]
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class PublicBookingForm(forms.Form):
    guest_name = forms.CharField(max_length=120)
    guest_email = forms.EmailField(required=False)
    guest_phone = forms.CharField(max_length=20, required=False)
    guest_company = forms.CharField(max_length=120, required=False)
    title = forms.CharField(max_length=200, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    appointment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    appointment_type = forms.ChoiceField(
        choices=Appointment.TYPE_CHOICES,
        required=False,
        initial=Appointment.TYPE_OFFLINE,
    )


class AvailabilityDayForm(forms.Form):
    day_of_week = forms.IntegerField(min_value=0, max_value=6)
    start_time = forms.TimeField()
    end_time = forms.TimeField()
    slot_duration_minutes = forms.IntegerField(min_value=5, max_value=240, initial=30)
    is_active = forms.BooleanField(required=False, initial=True)


class AppointmentSettingsForm(forms.ModelForm):
    class Meta:
        model = AppointmentSettings
        fields = [
            'slot_duration_minutes',
            'buffer_minutes',
            'minimum_notice_hours',
            'maximum_advance_days',
            'pending_blocks_slot',
            'public_display_name',
            'public_designation',
            'public_description',
        ]
