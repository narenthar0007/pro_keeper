from django.db import migrations


def backfill_brands(apps, schema_editor):
    Brand = apps.get_model('accounts', 'Brand')
    UserProfile = apps.get_model('accounts', 'UserProfile')
    ActivityLog = apps.get_model('accounts', 'ActivityLog')
    Property = apps.get_model('properties', 'Property')
    Tenant = apps.get_model('properties', 'Tenant')
    RentPayment = apps.get_model('properties', 'RentPayment')
    Expense = apps.get_model('properties', 'Expense')
    Enquiry = apps.get_model('properties', 'Enquiry')
    Complaint = apps.get_model('properties', 'Complaint')

    propkeep = Brand.objects.filter(slug='propkeep').first()
    if not propkeep:
        propkeep = Brand.objects.first()
    if not propkeep:
        return

    Property.objects.filter(brand__isnull=True).update(brand=propkeep)
    Tenant.objects.filter(brand__isnull=True).update(brand=propkeep)
    RentPayment.objects.filter(brand__isnull=True).update(brand=propkeep)
    Expense.objects.filter(brand__isnull=True).update(brand=propkeep)
    Enquiry.objects.filter(brand__isnull=True).update(brand=propkeep)
    Complaint.objects.filter(brand__isnull=True).update(brand=propkeep)
    UserProfile.objects.filter(brand__isnull=True).update(brand=propkeep)
    ActivityLog.objects.filter(brand__isnull=True).update(brand=propkeep)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_brand_data_isolation'),
        ('properties', '0004_brand_data_isolation'),
    ]

    operations = [
        migrations.RunPython(backfill_brands, migrations.RunPython.noop),
    ]
