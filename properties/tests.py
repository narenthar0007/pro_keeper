from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.brands import ensure_default_brands
from accounts.models import Brand, ensure_default_privileges

from .marketing_permissions import (
    campaigns_for_user,
    pending_collaboration_invites,
    user_can_edit_campaign,
    user_can_publish_campaign,
    user_can_create_campaign_for_property,
    user_can_view_campaign,
)
from .models import (
    Building,
    CampaignCollaborator,
    Enquiry,
    MarketingCampaign,
    Property,
    RentPayment,
    Tenant,
    properties_missing_rent_for_month,
)


class PropertyFlowTests(TestCase):
    def setUp(self):
        ensure_default_brands()
        ensure_default_privileges()
        self.brand = Brand.objects.get(slug='propkeep')
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pass12345')
        self.owner.profile.brand = self.brand
        self.owner.profile.save(update_fields=['brand'])
        self.collaborator = User.objects.create_user('creator', 'creator@example.com', 'pass12345')
        self.collaborator.profile.brand = self.brand
        self.collaborator.profile.save(update_fields=['brand'])
        self.client = Client()
        self.prop = Property.objects.create(
            owner=self.owner,
            brand=self.brand,
            title='Test Flat',
            address='1 Main St',
            city='Chennai',
            listing_type='rent',
            monthly_rent=Decimal('15000'),
            advance_amount=Decimal('30000'),
            is_listed_publicly=True,
            is_occupied=True,
        )
        self.sale_prop = Property.objects.create(
            owner=self.owner,
            brand=self.brand,
            title='Sale Villa',
            address='2 Sale St',
            city='Chennai',
            listing_type='sale',
            sale_price=Decimal('8500000'),
            is_listed_publicly=True,
        )
        self.tenant = Tenant.objects.create(
            property=self.prop,
            name='Ravi',
            is_active=True,
            advance_paid=Decimal('30000'),
        )

    def test_public_listing_shows_property(self):
        response = self.client.get(reverse('public_listings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Flat')

    def test_sale_listing_public_browse(self):
        response = self.client.get(reverse('public_listings'))
        self.assertContains(response, 'Sale Villa')
        response = self.client.get(reverse('public_detail', args=[self.sale_prop.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sale Villa')

    def test_rent_dashboard_excludes_sale_from_due_rent(self):
        due = properties_missing_rent_for_month(self.owner, brand=self.brand)
        self.assertIn(self.prop, due)
        self.assertNotIn(self.sale_prop, due)

    def test_enquiry_creates_message(self):
        response = self.client.post(
            reverse('public_detail', args=[self.prop.pk]),
            {
                'name': 'Buyer',
                'email': 'buyer@example.com',
                'phone': '9999999999',
                'message': 'Is this available?',
            },
        )
        self.assertEqual(response.status_code, 302)
        enquiry = self.prop.enquiries.get()
        self.assertEqual(enquiry.enquiry_type, 'rent')

    def test_due_rent_detection(self):
        due = properties_missing_rent_for_month(self.owner)
        self.assertIn(self.prop, due)
        RentPayment.objects.create(
            property=self.prop,
            tenant=self.tenant,
            amount=Decimal('15000'),
            payment_date='2026-08-01',
            month_for='2026-08-01',
            status='paid',
        )
        properties_missing_rent_for_month(self.owner)

    def test_owner_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.client.login(username='owner', password='pass12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_api_public_properties(self):
        response = self.client.get('/api/properties/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Flat')

    def test_brand_isolation_on_public_listings(self):
        checkpro = Brand.objects.get(slug='checkpro-data')
        Property.objects.create(
            owner=self.owner,
            brand=checkpro,
            title='CheckPro Only Flat',
            address='2 Other St',
            city='Chennai',
            listing_type='rent',
            monthly_rent=Decimal('12000'),
            is_listed_publicly=True,
        )

        response = self.client.get(reverse('public_listings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Flat')
        self.assertNotContains(response, 'CheckPro Only Flat')

        session = self.client.session
        session['preview_brand_slug'] = 'checkpro-data'
        session.save()
        response = self.client.get(reverse('public_listings'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Test Flat')
        self.assertContains(response, 'CheckPro Only Flat')

    def test_brand_isolation_campaigns(self):
        checkpro = Brand.objects.get(slug='checkpro-data')
        other_prop = Property.objects.create(
            owner=self.owner,
            brand=checkpro,
            title='CheckPro Property',
            address='3 St',
            city='Chennai',
            listing_type='rent',
            monthly_rent=Decimal('10000'),
        )
        MarketingCampaign.objects.create(
            property=other_prop,
            created_by=self.owner,
            title='CheckPro Campaign',
            channel='facebook',
            status='active',
        )
        MarketingCampaign.objects.create(
            property=self.prop,
            created_by=self.owner,
            title='PropKeep Campaign',
            channel='whatsapp',
            status='active',
        )
        owner_campaigns = campaigns_for_user(self.owner, self.brand)
        self.assertEqual(owner_campaigns.count(), 1)
        self.assertEqual(owner_campaigns.first().title, 'PropKeep Campaign')

    def test_collaborator_can_edit_not_publish(self):
        campaign = MarketingCampaign.objects.create(
            property=self.prop,
            created_by=self.owner,
            title='Collab Test',
            channel='instagram',
            status='draft',
        )
        CampaignCollaborator.objects.create(
            campaign=campaign,
            user=self.collaborator,
            role='editor',
            can_edit=True,
            can_publish=False,
            accepted=True,
        )
        self.assertTrue(user_can_edit_campaign(self.collaborator, campaign))
        self.assertFalse(user_can_publish_campaign(self.collaborator, campaign))

    def test_tenant_campaign_blocked_without_flag(self):
        tenant_user = User.objects.create_user('tenant1', 't@example.com', 'pass12345')
        Tenant.objects.create(
            property=self.prop,
            user=tenant_user,
            name='Tenant One',
            is_active=True,
        )
        self.prop.allow_tenant_marketing = False
        self.prop.save(update_fields=['allow_tenant_marketing'])
        self.assertFalse(user_can_create_campaign_for_property(tenant_user, self.prop, self.brand))

    def test_marketing_page_requires_login_for_campaigns(self):
        response = self.client.get(reverse('marketing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')
        self.client.login(username='owner', password='pass12345')
        response = self.client.get(reverse('marketing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Marketing')

    def test_collaboration_invite_shows_in_marketing_inbox(self):
        campaign = MarketingCampaign.objects.create(
            property=self.prop,
            brand=self.brand,
            created_by=self.owner,
            title='Summer Promo',
            channel='facebook',
            status='draft',
        )
        self.client.login(username='owner', password='pass12345')
        response = self.client.post(
            reverse('campaign_invite', args=[campaign.pk]),
            {
                'username': self.collaborator.username,
                'role': 'creator',
                'can_edit': 'on',
                'invite_message': 'Please help run ads for this flat.',
            },
        )
        self.assertEqual(response.status_code, 302)

        self.client.login(username='creator', password='pass12345')
        response = self.client.get(reverse('marketing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Collaboration requests')
        self.assertContains(response, 'Please help run ads for this flat.')
        self.assertContains(response, 'Summer Promo')
        self.assertContains(response, 'owner')

        invite = CampaignCollaborator.objects.get(campaign=campaign, user=self.collaborator)
        response = self.client.post(reverse('campaign_accept_invite', args=[invite.pk]))
        self.assertEqual(response.status_code, 302)
        invite.refresh_from_db()
        self.assertTrue(invite.accepted)
        self.assertTrue(user_can_view_campaign(self.collaborator, campaign))
        self.assertIn(campaign, list(campaigns_for_user(self.collaborator, self.brand)))

    def test_campaign_jobs_remind_and_complete(self):
        from datetime import timedelta

        from properties.campaign_jobs import run_campaign_jobs
        from properties.models import CampaignContentLog, CampaignTaskMessage

        today = timezone.localdate()
        campaign = MarketingCampaign.objects.create(
            property=self.prop,
            brand=self.brand,
            created_by=self.owner,
            title='Daily Content Push',
            channel='instagram',
            status='active',
            start_date=today - timedelta(days=1),
            end_date=today - timedelta(days=1),
            photos_per_day=1,
            videos_per_day=1,
            content_reminder_note='Make a walkthrough video for this seller.',
        )
        CampaignCollaborator.objects.create(
            campaign=campaign,
            user=self.collaborator,
            role='creator',
            can_edit=True,
            accepted=True,
            invited_by=self.owner,
        )

        result = run_campaign_jobs(today=today - timedelta(days=1))
        self.assertEqual(result['reminders'], 1)
        msg = CampaignTaskMessage.objects.get(
            campaign=campaign, recipient=self.collaborator
        )
        self.assertIn('walkthrough video', msg.message)
        self.assertIn('Daily Content Push', msg.message)

        CampaignContentLog.objects.create(
            campaign=campaign,
            user=self.collaborator,
            work_date=today - timedelta(days=1),
            photos_count=1,
            videos_count=1,
        )
        result = run_campaign_jobs(today=today)
        self.assertEqual(result['completed'], 1)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'completed')


class BuildingAndLeadTests(TestCase):
    def setUp(self):
        ensure_default_brands()
        ensure_default_privileges()
        self.brand = Brand.objects.get(slug='propkeep')
        self.other = Brand.objects.get(slug='checkpro-data')
        self.owner = User.objects.create_user('bld_owner', 'o@example.com', 'pass12345')
        self.owner.profile.brand = self.brand
        self.owner.profile.save(update_fields=['brand'])
        self.outsider = User.objects.create_user('other_owner', 'x@example.com', 'pass12345')
        self.outsider.profile.brand = self.other
        self.outsider.profile.role = 'owner'
        self.outsider.profile.save(update_fields=['brand', 'role'])
        self.client = Client()
        self.building = Building.objects.create(
            owner=self.owner,
            brand=self.brand,
            name='Green Residency',
            address='1 Lake St',
            city='Chennai',
        )
        self.unit = Property.objects.create(
            owner=self.owner,
            brand=self.brand,
            building=self.building,
            title='Room 12',
            unit_number='12',
            address='1 Lake St',
            city='Chennai',
            listing_type='rent',
            monthly_rent=Decimal('8000'),
            is_listed_publicly=True,
        )
        self.sale = Property.objects.create(
            owner=self.owner,
            brand=self.brand,
            title='Sale Flat',
            address='2 Lake St',
            city='Chennai',
            listing_type='sale',
            sale_price=Decimal('5000000'),
            is_listed_publicly=True,
        )

    def test_building_brand_isolation(self):
        self.client.login(username='other_owner', password='pass12345')
        response = self.client.get(reverse('building_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Green Residency')

    def test_public_listing_shows_unit(self):
        response = self.client.get(reverse('public_listings'))
        self.assertContains(response, 'Room 12')

    def test_convert_rent_lead_to_tenant(self):
        enquiry = Enquiry.objects.create(
            property=self.unit,
            brand=self.brand,
            name='Buyer Ten',
            email='ten@example.com',
            phone='9999999999',
            message='Need a room',
        )
        self.client.login(username='bld_owner', password='pass12345')
        response = self.client.post(reverse('lead_convert_tenant', args=[enquiry.pk]))
        self.assertEqual(response.status_code, 302)
        enquiry.refresh_from_db()
        self.assertEqual(enquiry.status, 'converted')
        self.assertIsNotNone(enquiry.converted_tenant_id)
        self.unit.refresh_from_db()
        self.assertTrue(self.unit.is_occupied)

    def test_convert_sale_lead_to_deal(self):
        enquiry = Enquiry.objects.create(
            property=self.sale,
            brand=self.brand,
            name='Buyer One',
            email='buy@example.com',
            message='Want to buy',
        )
        self.client.login(username='bld_owner', password='pass12345')
        response = self.client.post(
            reverse('lead_convert_deal', args=[enquiry.pk]),
            {
                'agreed_price': '4800000',
                'token_amount': '100000',
                'status': 'token',
                'commission_percent': '1',
            },
        )
        self.assertEqual(response.status_code, 302)
        enquiry.refresh_from_db()
        self.assertEqual(enquiry.status, 'converted')
        self.assertIsNotNone(enquiry.converted_deal_id)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.sale_status, 'under_offer')

    def test_tenants_page_and_inbox(self):
        self.client.login(username='bld_owner', password='pass12345')
        self.assertEqual(self.client.get(reverse('tenant_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('inbox')).status_code, 200)
        self.assertEqual(self.client.get(reverse('calendar_view')).status_code, 200)
        self.assertEqual(self.client.get(reverse('password_reset')).status_code, 200)
        reports = self.client.get(reverse('reports'))
        self.assertEqual(reports.status_code, 200)
        self.assertContains(reports, 'Income report')
        self.assertContains(reports, 'GST invoices')

