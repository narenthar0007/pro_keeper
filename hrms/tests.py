from datetime import time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Brand, UserProfile, ensure_default_privileges
from hrms.models import Attendance, Employee, OwnerHrmsSettings, Site, SiteAssignment
from hrms.services.attendance import (
    apply_regularize,
    approve_employee,
    decide_regularize,
    punch,
)
from hrms.services.punch_codes import decode_punch_code, generate_punch_code
from hrms.services.scoping import attendance_for_user, employees_for_user, sites_for_user
from hrms.services.users import ensure_employee_login


class HrmsCoreTests(TestCase):
    def setUp(self):
        ensure_default_privileges()
        self.brand = Brand.objects.create(
            name='TestBrand',
            slug='testbrand-hrms',
            hostnames='testserver',
            is_default=True,
        )
        self.owner_a = User.objects.create_user('owner_a', 'a@example.com', 'pass12345')
        self.owner_b = User.objects.create_user('owner_b', 'b@example.com', 'pass12345')
        for u in (self.owner_a, self.owner_b):
            p = u.profile
            p.role = UserProfile.ROLE_OWNER
            p.brand = self.brand
            p.save()
        OwnerHrmsSettings.objects.create(
            owner=self.owner_a,
            brand=self.brand,
            hrms_enabled=True,
            whatsapp_number='9876543210',
        )
        OwnerHrmsSettings.objects.create(
            owner=self.owner_b,
            brand=self.brand,
            hrms_enabled=True,
            whatsapp_number='9123456780',
        )
        self.site = Site.objects.create(
            owner=self.owner_a,
            brand=self.brand,
            name='Site Alpha',
            site_type=Site.TYPE_CONSTRUCTION,
        )
        self.emp = Employee.objects.create(
            owner=self.owner_a,
            brand=self.brand,
            emp_code='E001',
            name='Ravi Kumar',
            mobile='9000011111',
            latitude=Decimal('12.9716000'),
            longitude=Decimal('77.5946000'),
            default_site=self.site,
            approval_status=Employee.APPROVAL_PENDING,
        )
        ensure_employee_login(self.emp, role=UserProfile.ROLE_EMPLOYEE, brand=self.brand)

    def test_employee_punch_page_lists_assigned_site(self):
        approve_employee(actor=self.owner_a, employee=self.emp, approve=True)
        self.assertEqual(list(sites_for_user(self.emp.user)), [self.site])
        self.client.force_login(self.emp.user)
        response = self.client.get('/hrms/punch/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Site Alpha')
        posted = self.client.post(
            '/hrms/punch/',
            {
                'punch_type': 'in',
                'latitude': '12.9700000',
                'longitude': '77.5900000',
                'site': str(self.site.pk),
            },
        )
        self.assertEqual(posted.status_code, 200)
        self.assertContains(posted, 'In saved')
        att = Attendance.objects.get(employee=self.emp)
        self.assertEqual(att.site_id, self.site.pk)

    def test_not_working_blocks_punch_with_clear_reason(self):
        approve_employee(actor=self.owner_a, employee=self.emp, approve=True)
        self.emp.is_not_working = True
        self.emp.save(update_fields=['is_not_working'])
        with self.assertRaises(ValidationError) as ctx:
            punch(
                user=self.emp.user,
                punch_type='in',
                lat=Decimal('12.97'),
                lng=Decimal('77.59'),
            )
        self.assertIn('Not working', '; '.join(ctx.exception.messages))

    def test_pending_cannot_punch(self):
        with self.assertRaises(ValidationError):
            punch(
                user=self.emp.user,
                punch_type='in',
                lat=Decimal('12.97'),
                lng=Decimal('77.59'),
            )

    def test_punch_once_and_codes(self):
        approve_employee(actor=self.owner_a, employee=self.emp, approve=True)
        att, link, warn = punch(
            user=self.emp.user,
            punch_type='in',
            lat=Decimal('12.97'),
            lng=Decimal('77.59'),
            site=self.site,
        )
        self.assertTrue(att.punch_code_in)
        self.assertEqual(len(att.punch_code_in), 15)
        self.assertIsNotNone(link)
        with self.assertRaises(ValidationError):
            punch(
                user=self.emp.user,
                punch_type='in',
                lat=Decimal('12.97'),
                lng=Decimal('77.59'),
            )
        att2, _, _ = punch(
            user=self.emp.user,
            punch_type='out',
            lat=Decimal('12.98'),
            lng=Decimal('77.60'),
        )
        self.assertTrue(att2.punch_code_out)
        self.assertIsNotNone(att2.working_hours)

    def test_owner_isolation(self):
        other = Employee.objects.create(
            owner=self.owner_b,
            brand=self.brand,
            emp_code='E001',
            name='Other',
            mobile='9000022222',
            latitude=Decimal('12.0000000'),
            longitude=Decimal('77.0000000'),
            approval_status=Employee.APPROVAL_APPROVED,
        )
        qs_a = employees_for_user(self.owner_a)
        self.assertTrue(qs_a.filter(pk=self.emp.pk).exists())
        self.assertFalse(qs_a.filter(pk=other.pk).exists())

    def test_manager_regularize_owner_approves(self):
        approve_employee(actor=self.owner_a, employee=self.emp, approve=True)
        mgr_emp = Employee.objects.create(
            owner=self.owner_a,
            brand=self.brand,
            emp_code='M001',
            name='Manager One',
            mobile='9000033333',
            latitude=Decimal('12.9716000'),
            longitude=Decimal('77.5946000'),
            default_site=self.site,
            approval_status=Employee.APPROVAL_APPROVED,
        )
        mgr_user = ensure_employee_login(mgr_emp, role=UserProfile.ROLE_MANAGER, brand=self.brand)
        SiteAssignment.objects.create(site=self.site, manager=mgr_user)

        att = apply_regularize(
            actor=mgr_user,
            employee=self.emp,
            date=timezone.localdate(),
            reason='Forgot punch',
        )
        self.assertEqual(att.approval_status, Attendance.APPROVAL_PENDING)
        with self.assertRaises(ValidationError):
            decide_regularize(actor=mgr_user, attendance=att, approve=True)
        decide_regularize(actor=self.owner_a, attendance=att, approve=True)
        att.refresh_from_db()
        self.assertEqual(att.approval_status, Attendance.APPROVAL_APPROVED)

    def test_dashboard_count_matches_scope(self):
        approve_employee(actor=self.owner_a, employee=self.emp, approve=True)
        Employee.objects.create(
            owner=self.owner_b,
            brand=self.brand,
            emp_code='BX',
            name='B Emp',
            mobile='9000044444',
            latitude=Decimal('1.0'),
            longitude=Decimal('1.0'),
            approval_status=Employee.APPROVAL_APPROVED,
        )
        self.assertEqual(employees_for_user(self.owner_a).count(), 1)

    def test_punch_code_roundtrip_shape(self):
        now = timezone.localtime()
        code = generate_punch_code(
            emp_code='E001',
            name='Ravi Kumar',
            lat=12.97,
            lng=77.59,
            when=now,
            punch_type='in',
        )
        decoded = decode_punch_code(code)
        self.assertEqual(decoded['type'], 'In')
        self.assertEqual(len(code), 15)

    def test_theme_lock_flag(self):
        settings_row = self.owner_a.hrms_settings
        settings_row.theme_edited_at = timezone.localdate().strftime('%Y-%m')
        settings_row.save()
        self.assertTrue(settings_row.theme_locked_this_month)
