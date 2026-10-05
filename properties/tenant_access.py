from django.contrib.auth.models import User

from accounts.models import UserProfile


def create_login_for_tenant(tenant, username, password, brand=None, email=''):
    user = User.objects.create_user(
        username=username,
        email=email or tenant.email or '',
        password=password,
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = UserProfile.ROLE_TENANT
    if brand is not None:
        profile.brand = brand
    profile.save()
    tenant.user = user
    tenant.save(update_fields=['user'])
    return user


def apply_tenant_login_fields(tenant, form, brand=None):
    existing = form.cleaned_data.get('existing_username')
    create_username = (form.cleaned_data.get('create_username') or '').strip()
    if existing:
        tenant.user = existing
        tenant.save(update_fields=['user'])
        return None
    if create_username:
        return create_login_for_tenant(
            tenant,
            create_username,
            form.cleaned_data['create_password'],
            brand=brand,
            email=tenant.email,
        )
    return None
