from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.brands import ensure_default_brands
from accounts.models import Brand, RolePrivilege, UserProfile, ensure_default_privileges
from accounts.nav import get_nav_items


class SettingsPrivilegeTests(TestCase):
    def setUp(self):
        ensure_default_brands()
        ensure_default_privileges()
        self.brand = Brand.objects.get(slug='propkeep')
        self.owner = User.objects.create_user('owner1', 'owner1@example.com', 'pass12345')
        self.owner.profile.role = UserProfile.ROLE_OWNER
        self.owner.profile.brand = self.brand
        self.owner.profile.save(update_fields=['role', 'brand'])
        self.tenant = User.objects.create_user('tenant1', 'tenant1@example.com', 'pass12345')
        self.tenant.profile.role = UserProfile.ROLE_TENANT
        self.tenant.profile.brand = self.brand
        self.tenant.profile.save(update_fields=['role', 'brand'])
        self.client = Client()

    def _set_priv(self, role, code, enabled):
        RolePrivilege.objects.filter(role=role, code=code).update(enabled=enabled)

    def test_default_privileges_include_settings(self):
        codes = set(
            RolePrivilege.objects.filter(role=UserProfile.ROLE_OWNER).values_list(
                'code', flat=True
            )
        )
        self.assertIn('view_settings', codes)
        self.assertIn('manage_rent_reminders', codes)
        tenant_codes = set(
            RolePrivilege.objects.filter(role=UserProfile.ROLE_TENANT).values_list(
                'code', flat=True
            )
        )
        self.assertIn('view_settings', tenant_codes)
        self.assertIn('manage_rent_reminders', tenant_codes)

    def test_owner_can_open_and_save_settings(self):
        self.client.login(username='owner1', password='pass12345')
        response = self.client.get(reverse('user_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'collect rent')
        self.assertContains(response, 'has-side-nav')
        self.assertContains(response, 'app-side-nav')
        self.assertContains(response, 'aria-label="Back"')
        self.assertContains(response, 'aria-label="Refresh"')
        response = self.client.post(
            reverse('user_settings'),
            {
                'rent_reminder_enabled': 'on',
                'rent_due_day': '7',
                'reminder_days_before': '2',
                'reminder_email_enabled': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.owner.profile.refresh_from_db()
        self.assertTrue(self.owner.profile.rent_reminder_enabled)
        self.assertEqual(self.owner.profile.rent_due_day, 7)

    def test_settings_hidden_when_view_privilege_off(self):
        from accounts.privileges import has_privilege

        self._set_priv(UserProfile.ROLE_OWNER, 'view_settings', False)
        self.owner.refresh_from_db()
        self.assertFalse(has_privilege(self.owner, 'view_settings'))
        self.client.login(username='owner1', password='pass12345')
        response = self.client.get(reverse('user_settings'))
        self.assertEqual(response.status_code, 302)
        keys = [item['key'] for item in get_nav_items(self.owner, '/dashboard/', brand=self.brand)]
        self.assertNotIn('settings', keys)

    def test_cannot_save_when_manage_privilege_off(self):
        self._set_priv(UserProfile.ROLE_TENANT, 'manage_rent_reminders', False)
        self.client.login(username='tenant1', password='pass12345')
        response = self.client.get(reverse('user_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'read-only')
        self.assertContains(response, 'has-side-nav')
        self.assertContains(response, 'app-side-nav')
        response = self.client.post(
            reverse('user_settings'),
            {
                'rent_reminder_enabled': 'on',
                'rent_due_day': '10',
                'reminder_days_before': '1',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.tenant.profile.refresh_from_db()
        self.assertFalse(self.tenant.profile.rent_reminder_enabled)

    def test_nav_includes_settings_when_allowed(self):
        keys = [item['key'] for item in get_nav_items(self.owner, '/dashboard/', brand=self.brand)]
        self.assertIn('settings', keys)
        tenant_keys = [
            item['key'] for item in get_nav_items(self.tenant, '/tenant-portal/', brand=self.brand)
        ]
        self.assertIn('settings', tenant_keys)


class RentReminderLogicTests(TestCase):
    def test_due_date_and_window(self):
        from datetime import date

        from accounts.reminders import is_in_reminder_window, reminder_due_date, reminder_window_start

        today = date(2026, 8, 26)
        due = reminder_due_date(today, 5)
        self.assertEqual(due, date(2026, 8, 5))
        self.assertEqual(reminder_window_start(due, 3), date(2026, 8, 2))
        profile = UserProfile(rent_reminder_enabled=True, rent_due_day=5, reminder_days_before=3)
        self.assertFalse(is_in_reminder_window(profile, date(2026, 8, 1)))
        self.assertTrue(is_in_reminder_window(profile, date(2026, 8, 2)))
        self.assertTrue(is_in_reminder_window(profile, date(2026, 8, 26)))

    def test_owner_banner_and_email_for_unpaid_rent(self):
        from decimal import Decimal

        from django.core import mail
        from django.utils import timezone

        from accounts.reminders import build_reminder_banner, maybe_send_rent_reminder
        from properties.models import Property

        ensure_default_brands()
        ensure_default_privileges()
        brand = Brand.objects.get(slug='propkeep')
        owner = User.objects.create_user('owner2', 'owner2@example.com', 'pass12345')
        owner.profile.brand = brand
        owner.profile.rent_reminder_enabled = True
        owner.profile.rent_due_day = timezone.localdate().day
        owner.profile.reminder_days_before = 0
        owner.profile.reminder_email_enabled = True
        owner.profile.save()
        Property.objects.create(
            owner=owner,
            brand=brand,
            title='Unpaid Flat',
            address='1 Main St',
            city='Chennai',
            listing_type='rent',
            monthly_rent=Decimal('12000'),
            is_occupied=True,
        )
        banner = build_reminder_banner(owner, brand=brand)
        self.assertIsNotNone(banner)
        self.assertEqual(banner['title'], 'Collect rent reminder')
        self.assertIn('Unpaid Flat', banner['text'])
        self.assertTrue(maybe_send_rent_reminder(owner, brand=brand))
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(maybe_send_rent_reminder(owner, brand=brand))
        self.assertEqual(len(mail.outbox), 1)


class HeaderLayoutTests(TestCase):
    def setUp(self):
        ensure_default_brands()
        ensure_default_privileges()
        self.brand = Brand.objects.get(slug='propkeep')
        self.admin = User.objects.create_user(
            'admin1', 'admin1@example.com', 'pass12345', is_staff=True, is_superuser=True
        )
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.brand = self.brand
        self.admin.profile.save(update_fields=['role', 'brand'])
        self.client = Client()

    def test_admin_staff_drops_top_site_nav_and_keeps_search_left(self):
        self.client.login(username='admin1', password='pass12345')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('app-header-search', html)
        search_at = html.find('app-header-search')
        actions_at = html.find('app-header-actions')
        self.assertGreater(search_at, 0)
        self.assertGreater(actions_at, search_at)
        self.assertNotIn('has-side-nav', html)
        self.assertNotIn('class="app-side-nav"', html)

    def test_admin_site_pages_use_left_nav(self):
        self.client.login(username='admin1', password='pass12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'has-side-nav')
        self.assertContains(response, 'app-side-nav')


class UnfoldAdminTests(TestCase):
    def setUp(self):
        ensure_default_brands()
        ensure_default_privileges()
        self.brand = Brand.objects.get(slug='propkeep')
        self.admin = User.objects.create_user(
            'unfold_admin',
            'unfold@example.com',
            'pass12345',
            is_staff=True,
            is_superuser=True,
        )
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.brand = self.brand
        self.admin.profile.save(update_fields=['role', 'brand'])
        self.client = Client()

    def test_unfold_admin_index_shows_kpis(self):
        self.client.login(username='unfold_admin', password='pass12345')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PropKeep')
        self.assertContains(response, 'Customers')
        self.assertContains(response, 'Invoices due')

    def test_customer_and_invoice_changelists(self):
        self.client.login(username='unfold_admin', password='pass12345')
        self.assertEqual(
            self.client.get(reverse('admin:properties_tenant_changelist')).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('admin:properties_rentpayment_changelist')).status_code,
            200,
        )

    def test_non_staff_cannot_open_admin(self):
        owner = User.objects.create_user('plain_owner', 'owner@example.com', 'pass12345')
        owner.profile.role = UserProfile.ROLE_OWNER
        owner.profile.brand = self.brand
        owner.profile.save(update_fields=['role', 'brand'])
        self.client.login(username='plain_owner', password='pass12345')
        response = self.client.get('/admin/')
        self.assertIn(response.status_code, {302, 403})

    def test_admin_dashboard_shows_brand_switcher_and_chart(self):
        self.client.login(username='unfold_admin', password='pass12345')
        response = self.client.get('/admin/')
        self.assertContains(response, 'Active brand')
        self.assertContains(response, 'Rent collected vs due')
        self.assertContains(response, 'Staff console')

    def test_brand_switch_url(self):
        self.client.login(username='unfold_admin', password='pass12345')
        response = self.client.get(reverse('admin:admin_brand_switch', args=['checkpro-data']))
        self.assertEqual(response.status_code, 302)
        follow = self.client.get('/admin/')
        self.assertContains(follow, 'CheckPro Data')


class StatusPageTests(TestCase):
    def setUp(self):
        ensure_default_brands()
        ensure_default_privileges()
        self.client = Client()

    def test_preview_error_pages_use_ui_kit(self):
        for code, heading in (
            ('404', 'Page not found'),
            ('403', 'Access denied'),
            ('500', 'Something went wrong'),
        ):
            response = self.client.get(reverse('error_preview', args=[code]))
            self.assertEqual(response.status_code, int(code))
            self.assertContains(response, heading, status_code=int(code))
            self.assertContains(response, 'status-page', status_code=int(code))
            self.assertContains(response, 'Go home', status_code=int(code))

    def test_under_construction_page(self):
        response = self.client.get(reverse('under_construction'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Under construction')
        self.assertContains(response, 'Coming soon')
        response = self.client.get(reverse('under_construction') + '?feature=GST+invoices')
        self.assertContains(response, 'GST invoices is under construction')

    def test_page_not_found_named_url(self):
        response = self.client.get(reverse('page_not_found'))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Page not found', status_code=404)
        self.assertContains(response, 'That address is not in PropKeep.', status_code=404)
        self.assertContains(response, 'status-page', status_code=404)

    def test_real_404_uses_handler_when_debug_off(self):
        from django.test.utils import override_settings

        with override_settings(DEBUG=False):
            response = self.client.get('/this-page-does-not-exist-propkeep/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Page not found', status_code=404)
        self.assertContains(response, 'status-page', status_code=404)
        self.assertContains(response, 'That address is not in PropKeep.', status_code=404)


