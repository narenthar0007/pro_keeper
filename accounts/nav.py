"""Role-aware top navigation items for the shared app header."""

from django.urls import reverse

from .models import UserProfile
from .privileges import get_user_role, has_privilege, is_admin_user

# SVG path snippets keyed by icon name (stroke icons, 24x24 viewBox)
NAV_ICONS = {
    'browse': '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    'admin': (
        '<rect x="3" y="3" width="7" height="9" rx="1"/>'
        '<rect x="14" y="3" width="7" height="5" rx="1"/>'
        '<rect x="14" y="12" width="7" height="9" rx="1"/>'
        '<rect x="3" y="16" width="7" height="5" rx="1"/>'
    ),
    'dashboard': (
        '<rect x="3" y="3" width="8" height="8" rx="1"/>'
        '<rect x="13" y="3" width="8" height="5" rx="1"/>'
        '<rect x="13" y="10" width="8" height="11" rx="1"/>'
        '<rect x="3" y="13" width="8" height="8" rx="1"/>'
    ),
    'properties': '<path d="M3 10.5 12 3l9 7.5V21H3z"/><path d="M9 21v-7h6v7"/>',
    'tenants': (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="3"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a3 3 0 0 1 0 5.75"/>'
    ),
    'reports': (
        '<path d="M4 19V5"/><path d="M4 19h16"/>'
        '<path d="M8 17V9"/><path d="M12 17v-6"/><path d="M16 17v-3"/>'
    ),
    'marketing': (
        '<path d="M3 11h3l2-7h8l2 7h3v8H3z"/>'
        '<path d="M12 17a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/>'
    ),
    'buildings': (
        '<path d="M4 21V8l8-5 8 5v13"/>'
        '<path d="M9 21v-6h6v6"/>'
        '<path d="M9 10h.01M12 10h.01M15 10h.01"/>'
    ),
    'inbox': (
        '<path d="M4 4h16v16H4z"/>'
        '<path d="m4 8 8 5 8-5"/>'
    ),
    'calendar': (
        '<rect x="3" y="5" width="18" height="16" rx="2"/>'
        '<path d="M16 3v4M8 3v4M3 11h18"/>'
    ),
    'portal': (
        '<path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4z"/>'
        '<path d="M4 21a8 8 0 0 1 16 0"/>'
    ),
    'settings': (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68 1.65 1.65 0 0 0 10 3.17V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
    ),
}


def _item(key, label, url_name, icon, privilege=None, match=None, admin_only=False):
    return {
        'key': key,
        'label': label,
        'url_name': url_name,
        'icon': icon,
        'icon_svg': NAV_ICONS.get(icon, ''),
        'privilege': privilege,
        'match': match or f'/{url_name}/',
        'admin_only': admin_only,
    }


NAV_CATALOG = [
    _item('browse', 'Browse', 'public_listings', 'browse', privilege=None, match='/'),
    _item('admin', 'Admin', 'staff_dashboard', 'admin', admin_only=True, match='/accounts/staff'),
    _item('dashboard', 'Dashboard', 'dashboard', 'dashboard', privilege='view_dashboard', match='/dashboard/'),
    _item('properties', 'Properties', 'my_properties', 'properties', privilege='manage_properties', match='/my-properties'),
    _item('buildings', 'Buildings', 'building_list', 'buildings', privilege='view_buildings', match='/buildings'),
    _item('tenants', 'Tenants', 'tenant_list', 'tenants', privilege='manage_tenants', match='/tenants'),
    _item('reports', 'Reports', 'reports', 'reports', privilege='view_reports', match='/reports/'),
    _item('marketing', 'Marketing', 'marketing', 'marketing', privilege='view_marketing', match='/marketing'),
    _item('enquiries', 'Leads', 'enquiries_inbox', 'enquiries', privilege='view_enquiries', match='/enquiries'),
    _item('inbox', 'Inbox', 'inbox', 'inbox', privilege='view_inbox', match='/inbox'),
    _item('calendar', 'Calendar', 'calendar_view', 'calendar', privilege='view_calendar', match='/calendar'),
    _item('commissions', 'Commissions', 'commissions', 'reports', privilege='view_commissions', match='/commissions'),
    _item('saved', 'Saved', 'saved_listings', 'browse', privilege='save_listings', match='/saved'),
    _item('portal', 'My portal', 'tenant_portal', 'portal', privilege='view_tenant_portal', match='/tenant-portal/'),
    _item('hrms', 'HRMS', 'hrms_dashboard', 'dashboard', privilege='hrms_access', match='/hrms/'),
    _item('hrms_employees', 'Workforce', 'hrms_employees', 'tenants', privilege='hrms_access', match='/hrms/employees'),
    _item('hrms_sites', 'Sites', 'hrms_sites', 'buildings', privilege='hrms_access', match='/hrms/sites'),
    _item('hrms_attendance', 'Attendance', 'hrms_attendance', 'calendar', privilege='hrms_access', match='/hrms/attendance'),
    _item('hrms_punch', 'Punch', 'hrms_punch', 'portal', privilege='hrms_punch', match='/hrms/punch'),
    _item(
        'hrms_regularize_mgr',
        'Regularize',
        'hrms_regularize',
        'calendar',
        privilege='hrms_apply_regularize',
        match='/hrms/regularize',
    ),
    _item(
        'hrms_regularize_emp',
        'Regularize',
        'hrms_regularize',
        'calendar',
        privilege='hrms_apply_regularize_self',
        match='/hrms/regularize',
    ),
    _item('hrms_updates', 'Site updates', 'hrms_updates', 'inbox', privilege='hrms_site_updates', match='/hrms/updates'),
    _item('hrms_reports', 'Reports', 'hrms_reports', 'reports', privilege='hrms_view_reports', match='/hrms/reports'),
    _item('hrms_approvals', 'Approvals', 'hrms_approvals', 'inbox', privilege='hrms_access', match='/hrms/approvals'),
    _item('hrms_settings', 'HRMS settings', 'hrms_settings', 'settings', privilege='hrms_settings', match='/hrms/settings'),
    _item('hrms_leave_types', 'Leave types', 'hrms_leave_types', 'settings', privilege='hrms_manage_leave', match='/hrms/leave/types'),
    _item('hrms_holidays', 'Holidays', 'hrms_holidays', 'calendar', privilege='hrms_manage_leave', match='/hrms/holidays'),
    _item('hrms_leave_alloc', 'Leave allocations', 'hrms_leave_allocations', 'tenants', privilege='hrms_leave_allocate', match='/hrms/leave/allocations'),
    _item('hrms_leave_requests', 'Leave requests', 'hrms_leave_requests', 'inbox', privilege='hrms_leave_approve', match='/hrms/leave/requests'),
    _item('hrms_leave_my', 'My leaves', 'hrms_leave_my', 'portal', privilege='hrms_leave_apply', match='/hrms/leave/my'),
    _item('hrms_leave_apply', 'Apply leave', 'hrms_leave_apply', 'calendar', privilege='hrms_leave_apply', match='/hrms/leave/apply'),
    _item('hrms_calendar', 'HRMS calendar', 'hrms_calendar', 'calendar', privilege='hrms_leave_calendar', match='/hrms/calendar'),
    _item('settings', 'Settings', 'user_settings', 'settings', privilege='view_settings', match='/accounts/settings'),
]


def _is_active(path, match, key):
    path = path or ''
    if key == 'browse':
        return path == '/'
    if key == 'admin':
        return path.startswith('/accounts/staff')
    if key == 'properties':
        return path.startswith('/my-properties') and 'tenants' not in path
    if key == 'tenants':
        return path.startswith('/tenants')
    if key == 'enquiries':
        return path.startswith('/enquiries') or path.startswith('/leads')
    if key == 'inbox':
        return path.startswith('/inbox')
    if key == 'calendar':
        return path.startswith('/calendar')
    if key == 'buildings':
        return path.startswith('/buildings')
    if key == 'saved':
        return path.startswith('/saved')
    if key == 'commissions':
        return path.startswith('/commissions')
    if key == 'settings':
        return path.startswith('/accounts/settings')
    if key == 'hrms':
        return path == '/hrms/' or path == '/hrms'
    if key in ('hrms_regularize_mgr', 'hrms_regularize_emp'):
        return path.startswith('/hrms/regularize')
    if key == 'hrms_punch':
        return path.startswith('/hrms/punch')
    if key.startswith('hrms_'):
        return match in path if match else False
    return match in path if match else False


def uses_hrms_workspace(role):
    """Manager/employee use HRMS sidebar only (no property modules in header)."""
    return role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_EMPLOYEE)


def get_nav_items(user, current_path='', brand=None):
    """Return nav items allowed for this user."""
    items = []
    role = get_user_role(user) if getattr(user, 'is_authenticated', False) else None
    hrms_workspace = uses_hrms_workspace(role)
    pending_marketing_invites = 0
    unread_inbox = 0
    hrms_access_ok = None
    if user.is_authenticated and brand is not None and not hrms_workspace:
        try:
            from properties.marketing_permissions import pending_collaboration_invites_count

            pending_marketing_invites = pending_collaboration_invites_count(user, brand)
        except Exception:
            pending_marketing_invites = 0
        try:
            from properties.models import UserNotification

            unread_inbox = UserNotification.objects.filter(
                user=user, brand=brand, is_read=False
            ).count()
        except Exception:
            unread_inbox = 0
    elif hrms_workspace and user.is_authenticated:
        try:
            from hrms.services.scoping import user_can_access_hrms

            hrms_access_ok = user_can_access_hrms(user) or is_admin_user(user)
        except Exception:
            hrms_access_ok = False

    for raw in NAV_CATALOG:
        if hrms_workspace and not raw['key'].startswith('hrms'):
            continue
        if role == UserProfile.ROLE_EMPLOYEE and raw['key'] in (
            'hrms_employees',
            'hrms_sites',
            'hrms_approvals',
            'hrms_leave_types',
            'hrms_holidays',
            'hrms_leave_alloc',
            'hrms_leave_requests',
        ):
            continue
        if role == UserProfile.ROLE_MANAGER and raw['key'] in (
            'hrms_leave_types',
            'hrms_holidays',
        ):
            continue
        if not user.is_authenticated and raw['key'] != 'browse':
            continue
        if raw['admin_only'] and not is_admin_user(user):
            continue
        # Tenant portal is only for tenant role (admins have all privileges)
        if raw['key'] == 'portal' and role != UserProfile.ROLE_TENANT:
            continue
        # Settings (rent reminders) is for owner and tenant accounts only
        if raw['key'] == 'settings' and role not in (UserProfile.ROLE_OWNER, UserProfile.ROLE_TENANT):
            continue

        # HRMS nav only when module enabled for this user's company
        if raw['key'].startswith('hrms'):
            if not user.is_authenticated:
                continue
            if hrms_access_ok is None:
                try:
                    from hrms.services.scoping import user_can_access_hrms

                    hrms_access_ok = user_can_access_hrms(user) or is_admin_user(user)
                except Exception:
                    hrms_access_ok = False
            if not hrms_access_ok:
                continue
            # Managers/employees: show HRMS items; hide rental-heavy items already gated by privilege
            if role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_EMPLOYEE):
                pass

        privilege = raw['privilege']
        if raw['key'] == 'marketing' and privilege:
            if not (user.is_authenticated and has_privilege(user, privilege)):
                if pending_marketing_invites <= 0:
                    continue
        elif privilege and not (user.is_authenticated and has_privilege(user, privilege)):
            continue
        # privilege=None is only for browse (public) or admin_only entries
        if privilege is None and raw['key'] != 'browse' and not raw['admin_only']:
            continue

        try:
            url = reverse(raw['url_name'])
        except Exception:
            continue

        items.append(
            {
                **raw,
                'url': url,
                'active': _is_active(current_path, raw['match'], raw['key']),
                'badge_count': (
                    pending_marketing_invites
                    if raw['key'] == 'marketing'
                    else unread_inbox
                    if raw['key'] == 'inbox'
                    else 0
                ),
            }
        )
    return items


def show_quick_add(user):
    return user.is_authenticated and has_privilege(user, 'manage_properties')
