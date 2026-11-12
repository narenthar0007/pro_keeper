from datetime import time

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserProfile, ensure_default_privileges
from appointments.models import Appointment
from appointments.services.booking import create_host_appointment, create_public_request, ensure_booking_slug
from appointments.services.slots import slot_is_free


class AppointmentBookingTests(TestCase):
    def setUp(self):
        ensure_default_privileges()
        self.host = User.objects.create_user('host1', password='x', email='h@example.com')
        UserProfile.objects.filter(user=self.host).update(role=UserProfile.ROLE_MANAGER, can_manage_appointments=True)
        ensure_booking_slug(self.host)

    def test_internal_booking_auto_approved(self):
        today = timezone.localdate()
        appt = create_host_appointment(
            self.host,
            {
                'title': 'Meet',
                'appointment_date': today,
                'start_time': time(10, 0),
                'end_time': time(10, 30),
                'guest_name': 'Client',
            },
        )
        self.assertEqual(appt.status, Appointment.STATUS_APPROVED)
        self.assertFalse(slot_is_free(self.host, today, time(10, 0), time(10, 30)))

    def test_public_request_pending(self):
        today = timezone.localdate()
        appt = create_public_request(
            self.host,
            {
                'guest_name': 'Visitor',
                'appointment_date': today,
                'start_time': time(11, 0),
                'end_time': time(11, 30),
            },
        )
        self.assertEqual(appt.status, Appointment.STATUS_PENDING)
