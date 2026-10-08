from .brands import resolve_brand
from .nav import get_nav_items, show_quick_add, uses_hrms_workspace
from .privileges import get_user_role, has_privilege, is_admin_user
from .brand_scoping import get_request_brand


def _user_initials(user):
    name = (user.get_full_name() or user.username or '?').strip()
    parts = [p for p in name.replace('.', ' ').replace('_', ' ').split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


class _FallbackBrand:
    name = 'PropKeep'
    slug = 'propkeep'
    tagline = 'Property Management'
    footer_text = 'PropKeep — rent, advance, and listings in one place.'
    hostnames = 'localhost,127.0.0.1'
    base_url = 'http://127.0.0.1:8000'
    is_default = True
    is_active = True
    primary_color = '#0b5fff'
    secondary_color = '#111827'
    button_color = '#0b5fff'
    button_text_color = '#ffffff'
    background_color = '#f4f6f8'
    surface_color = '#ffffff'
    text_color = '#111827'
    header_color = '#0f2744'
    header_text_color = '#e8eef7'
    header_active_color = '#12b886'
    footer_bg_color = '#ffffff'
    footer_text_color = '#6b7280'
    font_style = 'syne_source'
    table_format = 'comfortable'
    border_radius = 'soft'

    def font_css(self):
        return ("'Syne', sans-serif", "'Source Sans 3', sans-serif")

    def radius_value(self):
        return '18px'


def _file_url(file_field):
    if not file_field:
        return ''
    try:
        return file_field.url
    except (ValueError, AttributeError):
        return ''


def site_theme_and_role(request):
    try:
        brand = getattr(request, 'brand', None) or resolve_brand(request)
    except Exception:
        brand = _FallbackBrand()

    display_font, body_font = brand.font_css()
    user = request.user
    role = None
    admin = False
    path = getattr(request, 'path', '')
    if user.is_authenticated:
        try:
            role = get_user_role(user)
            admin = is_admin_user(user)
        except Exception:
            role = None
            admin = user.is_staff or user.is_superuser

    def priv(code):
        if not user.is_authenticated:
            return False
        try:
            return has_privilege(user, code)
        except Exception:
            return admin

    unread = 0
    unread_inbox = 0
    pending_collab_invites = 0
    open_complaints = 0
    property_count = 0
    if user.is_authenticated:
        try:
            from properties.models import Complaint, Enquiry, Property, UserNotification

            brand = get_request_brand(request)
            props = Property.for_user(user, brand=brand)
            property_count = props.count()
            if priv('view_enquiries'):
                unread = Enquiry.objects.filter(
                    property__in=props, brand=brand, is_read=False
                ).count()
            if priv('view_inbox'):
                unread_inbox = UserNotification.objects.filter(
                    user=user, brand=brand, is_read=False
                ).count()
            try:
                from properties.marketing_permissions import pending_collaboration_invites_count

                pending_collab_invites = pending_collaboration_invites_count(user, brand)
            except Exception:
                pending_collab_invites = 0
            open_complaints = Complaint.objects.filter(
                property__in=props,
                brand=brand,
                status__in=['open', 'in_progress'],
            ).count()
        except Exception:
            pass

    try:
        nav_items = get_nav_items(user, path, brand=brand)
        quick_add = show_quick_add(user)
    except Exception:
        nav_items = []
        quick_add = False

    rent_reminder_banner = None
    if user.is_authenticated and role in ('owner', 'tenant') and priv('manage_rent_reminders'):
        try:
            from .reminders import build_reminder_banner

            rent_reminder_banner = build_reminder_banner(user, brand=brand)
        except Exception:
            rent_reminder_banner = None

    if rent_reminder_banner:
        for item in nav_items:
            if item.get('key') == 'settings':
                item['badge_count'] = 1
                break

    return {
        'current_brand': brand,
        'site_theme': brand,  # templates already use site_theme.*
        'brand_logo_url': _file_url(getattr(brand, 'logo', None)),
        'brand_icon_url': _file_url(getattr(brand, 'icon', None)),
        'theme_display_font': display_font,
        'theme_body_font': body_font,
        'theme_radius': brand.radius_value(),
        'brand_name': getattr(brand, 'name', 'PropKeep'),
        'brand_tagline': getattr(brand, 'tagline', ''),
        'brand_footer': getattr(brand, 'footer_text', ''),
        'brand_base_url': getattr(brand, 'base_url', ''),
        'user_role': role,
        'is_admin_user': admin,
        'is_owner_user': role == 'owner',
        'is_tenant_user': role == 'tenant',
        'is_manager_user': role == 'manager',
        'is_employee_user': role == 'employee',
        'can_access_hrms': priv('hrms_access'),
        'can_view_dashboard': priv('view_dashboard'),
        'can_view_reports': priv('view_reports'),
        'can_view_enquiries': priv('view_enquiries'),
        'can_view_tenant_portal': priv('view_tenant_portal'),
        'can_view_settings': priv('view_settings'),
        'can_view_inbox': priv('view_inbox'),
        'can_manage_rent_reminders': priv('manage_rent_reminders'),
        'unread_enquiries_count': unread,
        'unread_inbox_count': unread_inbox,
        'pending_collab_invites_count': pending_collab_invites,
        'open_complaints_count': open_complaints,
        'nav_property_count': property_count,
        'user_initials': _user_initials(user) if user.is_authenticated else '',
        'user_avatar_url': _file_url(getattr(getattr(user, 'profile', None), 'avatar', None)) if user.is_authenticated else '',
        'current_path': path,
        'nav_items': nav_items,
        'show_quick_add': quick_add,
        'rent_reminder_banner': rent_reminder_banner,
        'use_hrms_workspace': bool(user.is_authenticated and uses_hrms_workspace(role)),
        'use_site_side_nav': bool(
            user.is_authenticated
            and (
                role in ('owner', 'tenant')
                or uses_hrms_workspace(role)
                or (admin and not (path or '').startswith('/accounts/staff'))
            )
        ),
    }
