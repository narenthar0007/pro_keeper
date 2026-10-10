from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Brand, UserProfile, ensure_default_privileges
from hrms.models import CompanyHoliday, Employee, LeaveRequest, LeaveType, OwnerHrmsSettings, Site
from hrms.services.attendance import approve_employee
from hrms.services.leave import (
    approve_leave_request,
    create_leave_request,
    get_balance_row,
    reject_leave_request,
    seed_default_leave_types,
    upsert_allocation,
    validate_leave_request,
    working_days_between,
)
from hrms.services.users import ensure_employee_login


class LeaveManagementTests(TestCase):
    def setUp(self):
        ensure_default_privileges()
        self.brand = Brand.objects.create(
            name='LeaveBrand',
            slug='leavebrand',
            hostnames='testserver',
            is_default=True,
        )
        self.owner = User.objects.create_user('leaveowner', 'o@example.com', 'pass12345')
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.brand = self.brand
        self.owner.profile.save()
        OwnerHrmsSettings.objects.create(
            owner=self.owner,
            brand=self.brand,
            hrms_enabled=True,
            weekly_off_days='6',
        )
        seed_default_leave_types(self.owner, self.brand)
        self.cl = LeaveType.objects.get(owner=self.owner, code='CL')
        self.emp_record = Employee.objects.create(
            owner=self.owner,
            brand=self.brand,
            emp_code='L100',
            name='Leave Emp',
            mobile='9876543210',
            latitude=Decimal('12.9716000'),
            longitude=Decimal('77.5946000'),
            approval_status=Employee.APPROVAL_PENDING,
        )
        ensure_employee_login(
            self.emp_record,
            role=UserProfile.ROLE_EMPLOYEE,
            brand=self.brand,
            username='leaveemp',
            password='pass12345',
        )
        approve_employee(actor=self.owner, employee=self.emp_record, approve=True)
        upsert_allocation(
            actor=self.owner,
            employee=self.emp_record,
            leave_type=self.cl,
            year=date.today().year,
            allocated_days=Decimal('15'),
        )

    def test_duplicate_leave_type_code(self):
        with self.assertRaises(Exception):
            LeaveType.objects.create(
                owner=self.owner,
                brand=self.brand,
                name='Dup',
                code='CL',
                annual_entitlement=1,
            )

    def test_working_days_exclude_sunday(self):
        # 2026-06-01 is Monday, through 2026-06-07 includes one Sunday
        days = working_days_between(self.owner, date(2026, 6, 1), date(2026, 6, 7))
        self.assertEqual(days, Decimal('6'))

    def test_holiday_excluded_from_working_days(self):
        CompanyHoliday.objects.create(
            owner=self.owner,
            brand=self.brand,
            name='Test Hol',
            date=date(2026, 6, 3),
        )
        days = working_days_between(self.owner, date(2026, 6, 1), date(2026, 6, 5))
        self.assertEqual(days, Decimal('4'))

    def test_apply_and_approve_updates_balance(self):
        req = create_leave_request(
            employee=self.emp_record,
            leave_type=self.cl,
            start=date(2026, 6, 1),
            end=date(2026, 6, 1),
            reason='Personal',
            actor=self.emp_record.user,
        )
        row = get_balance_row(self.emp_record, self.cl, 2026)
        self.assertEqual(row['pending'], Decimal('1'))
        self.assertEqual(row['available'], Decimal('15'))
        approve_leave_request(self.owner, req, comment='OK')
        row = get_balance_row(self.emp_record, self.cl, 2026)
        self.assertEqual(row['used'], Decimal('1'))
        self.assertEqual(row['pending'], Decimal('0'))
        self.assertEqual(row['available'], Decimal('14'))

    def test_overlap_rejected(self):
        create_leave_request(
            employee=self.emp_record,
            leave_type=self.cl,
            start=date(2026, 7, 1),
            end=date(2026, 7, 2),
            reason='A',
            actor=self.emp_record.user,
        )
        with self.assertRaises(ValidationError):
            validate_leave_request(
                self.emp_record,
                self.cl,
                date(2026, 7, 2),
                date(2026, 7, 3),
            )

    def test_oversubscription_blocked(self):
        with self.assertRaises(ValidationError):
            validate_leave_request(
                self.emp_record,
                self.cl,
                date(2026, 8, 1),
                date(2026, 8, 20),
            )

    def test_double_approve_fails(self):
        req = create_leave_request(
            employee=self.emp_record,
            leave_type=self.cl,
            start=date(2026, 9, 1),
            end=date(2026, 9, 1),
            reason='One day',
            actor=self.emp_record.user,
        )
        approve_leave_request(self.owner, req, comment='yes')
        with self.assertRaises(ValidationError):
            approve_leave_request(self.owner, req, comment='again')

    def test_reject_requires_comment(self):
        req = create_leave_request(
            employee=self.emp_record,
            leave_type=self.cl,
            start=date(2026, 10, 1),
            end=date(2026, 10, 1),
            reason='Try',
            actor=self.emp_record.user,
        )
        with self.assertRaises(ValidationError):
            reject_leave_request(self.owner, req, comment='')

    def test_manager_cannot_approve_out_of_scope(self):
        manager = User.objects.create_user('mgrleave', 'm@example.com', 'pass12345')
        manager.profile.role = UserProfile.ROLE_MANAGER
        manager.profile.brand = self.brand
        manager.profile.save()
        other_site = Site.objects.create(
            owner=self.owner,
            brand=self.brand,
            name='Other',
            site_type=Site.TYPE_OTHER,
            latitude=Decimal('1'),
            longitude=Decimal('1'),
        )
        mgr_emp = Employee.objects.create(
            owner=self.owner,
            brand=self.brand,
            emp_code='MGR1',
            name='Mgr',
            mobile='9876543211',
            latitude=Decimal('1'),
            longitude=Decimal('1'),
            default_site=other_site,
            approval_status=Employee.APPROVAL_APPROVED,
        )
        ensure_employee_login(mgr_emp, role=UserProfile.ROLE_MANAGER, brand=self.brand, password='pass12345')
        req = create_leave_request(
            employee=self.emp_record,
            leave_type=self.cl,
            start=date(2026, 11, 2),
            end=date(2026, 11, 2),
            reason='X',
            actor=self.emp_record.user,
        )
        from hrms.services.leave import can_approve_leave

        self.assertFalse(can_approve_leave(manager, req))
