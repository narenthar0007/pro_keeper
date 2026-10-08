from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from properties.forms import AdminBroadcastForm
from properties.models import (
    Building,
    Complaint,
    Enquiry,
    Expense,
    LeadVisit,
    MarketingCampaign,
    Offer,
    Property,
    RentPayment,
    SaleDeal,
    SitePromotion,
    Tenant,
)
from properties.notifications import notify_user

from django.urls import reverse
from django.utils.safestring import mark_safe

from .brands import SESSION_KEY as BRAND_SESSION_KEY, ensure_default_brands
from .brand_scoping import filter_by_brand, get_request_brand, users_for_brand
from .forms import (
    AdminCreateUserForm,
    BrandForm,
    GroupForm,
    PrivilegeToggleForm,
    SitePromotionForm,
    UserPrivilegeToggleForm,
)
from .logging_utils import log_activity
from .models import (
    ActivityLog,
    Brand,
    RolePrivilege,
    UserPrivilege,
    UserProfile,
    ensure_default_privileges,
)
from .pagination import PAGE_SIZE, paginate_table, pagination_query
from .privileges import get_user_role, is_admin_user
from .components import (
    build_alert,
    build_button,
    build_empty,
    build_filter,
    build_heading,
    build_kpis,
    build_page_header,
    build_popup,
    build_search,
    build_status_page,
    build_table,
)


def admin_required(view_func):
    decorated = user_passes_test(is_admin_user)(view_func)
    return login_required(decorated)


ADMIN_NAV = [
    {'key': 'dashboard', 'label': 'Dashboard', 'url_name': 'staff_dashboard'},
    {'key': 'users', 'label': 'Users', 'url_name': 'staff_users'},
    {'key': 'create_user', 'label': 'Create login', 'url_name': 'staff_create_user'},
    {'key': 'groups', 'label': 'Groups', 'url_name': 'staff_table', 'url_kwargs': {'table': 'groups'}},
    {'key': 'properties', 'label': 'Properties', 'url_name': 'staff_table', 'url_kwargs': {'table': 'properties'}},
    {'key': 'buildings', 'label': 'Buildings', 'url_name': 'staff_table', 'url_kwargs': {'table': 'buildings'}},
    {'key': 'tenants', 'label': 'Tenants', 'url_name': 'staff_table', 'url_kwargs': {'table': 'tenants'}},
    {'key': 'payments', 'label': 'Payments', 'url_name': 'staff_table', 'url_kwargs': {'table': 'payments'}},
    {'key': 'expenses', 'label': 'Expenses', 'url_name': 'staff_table', 'url_kwargs': {'table': 'expenses'}},
    {'key': 'enquiries', 'label': 'Leads', 'url_name': 'staff_table', 'url_kwargs': {'table': 'enquiries'}},
    {'key': 'visits', 'label': 'Visits', 'url_name': 'staff_table', 'url_kwargs': {'table': 'visits'}},
    {'key': 'offers', 'label': 'Offers', 'url_name': 'staff_table', 'url_kwargs': {'table': 'offers'}},
    {'key': 'deals', 'label': 'Sale deals', 'url_name': 'staff_table', 'url_kwargs': {'table': 'deals'}},
    {'key': 'complaints', 'label': 'Complaints', 'url_name': 'staff_table', 'url_kwargs': {'table': 'complaints'}},
    {'key': 'campaigns', 'label': 'Campaigns', 'url_name': 'staff_table', 'url_kwargs': {'table': 'campaigns'}},
    {'key': 'promotions', 'label': 'Promotions', 'url_name': 'staff_promotions'},
    {'key': 'logs', 'label': 'Activity logs', 'url_name': 'staff_activity_logs'},
    {'key': 'privileges', 'label': 'Roles & privileges', 'url_name': 'staff_privileges'},
    {'key': 'hrms', 'label': 'HRMS subscriptions', 'url_name': 'hrms_settings'},
    {'key': 'brands', 'label': 'Brands', 'url_name': 'staff_brands'},
    {'key': 'theme', 'label': 'Theme settings', 'url_name': 'staff_theme'},
    {'key': 'components', 'label': 'UI components', 'url_name': 'staff_components'},
]


def _admin_context(active='', request=None):
    ctx = {'admin_nav': ADMIN_NAV, 'admin_active': active}
    if request is not None:
        brand = get_request_brand(request)
        ctx['active_brand'] = brand
    return ctx


def _brand_users(request):
    return users_for_brand(get_request_brand(request)).select_related('profile').order_by('-date_joined')


def _brand_logs(request):
    return filter_by_brand(
        ActivityLog.objects.select_related('user'), get_request_brand(request)
    ).order_by('-created_at')


TABLE_CONFIG = {
    'users': {
        'label': 'Users',
        'headers': ['ID', 'Username', 'Email', 'Role', 'Staff', 'Active', 'Joined'],
        'queryset': _brand_users,
        'row': lambda u: [
            u.id,
            u.username,
            u.email or '—',
            getattr(getattr(u, 'profile', None), 'get_role_display', lambda: '—')(),
            'Yes' if u.is_staff else 'No',
            'Yes' if u.is_active else 'No',
            u.date_joined.strftime('%d %b %Y'),
        ],
    },
    'groups': {
        'label': 'Groups',
        'headers': ['ID', 'Name', 'Members'],
        'queryset': lambda request: Group.objects.annotate(member_count=Count('user')).order_by('name'),
        'row': lambda g: [g.id, g.name, g.member_count],
    },
    'properties': {
        'label': 'Properties',
        'headers': ['ID', 'Title', 'Type', 'City', 'Building', 'Owner', 'Price', 'Public'],
        'queryset': lambda request: filter_by_brand(
            Property.objects.select_related('owner', 'building'), get_request_brand(request)
        ).order_by('-created_at'),
        'row': lambda p: [
            p.id,
            p.title,
            p.get_listing_type_display(),
            p.city,
            p.building.name if p.building_id else '—',
            p.owner.username,
            p.display_price,
            'Yes' if p.is_listed_publicly else 'No',
        ],
    },
    'buildings': {
        'label': 'Buildings',
        'headers': ['ID', 'Name', 'City', 'Owner', 'Units', 'Active'],
        'queryset': lambda request: filter_by_brand(
            Building.objects.select_related('owner'), get_request_brand(request)
        ).order_by('name'),
        'row': lambda b: [
            b.id,
            b.name,
            b.city,
            b.owner.username,
            b.units.count(),
            'Yes' if b.is_active else 'No',
        ],
    },
    'tenants': {
        'label': 'Tenants',
        'headers': ['ID', 'Name', 'Property', 'Phone', 'Active', 'Linked user'],
        'queryset': lambda request: filter_by_brand(
            Tenant.objects.select_related('property', 'user'), get_request_brand(request)
        ).order_by('-created_at'),
        'row': lambda t: [
            t.id,
            t.name,
            t.property.title,
            t.phone or '—',
            'Yes' if t.is_active else 'No',
            t.user.username if t.user else '—',
        ],
    },
    'payments': {
        'label': 'Payments',
        'headers': ['ID', 'Property', 'Tenant', 'Amount', 'Month', 'Status'],
        'queryset': lambda request: filter_by_brand(
            RentPayment.objects.select_related('property', 'tenant'), get_request_brand(request)
        ).order_by('-created_at'),
        'row': lambda p: [
            p.id,
            p.property.title,
            p.tenant.name if p.tenant else '—',
            f'₹{p.amount}',
            p.month_for.strftime('%b %Y'),
            p.get_status_display(),
        ],
    },
    'expenses': {
        'label': 'Expenses',
        'headers': ['ID', 'Property', 'Title', 'Category', 'Amount', 'Date'],
        'queryset': lambda request: filter_by_brand(
            Expense.objects.select_related('property'), get_request_brand(request)
        ).order_by('-expense_date'),
        'row': lambda e: [
            e.id,
            e.property.title,
            e.title,
            e.get_category_display(),
            f'₹{e.amount}',
            e.expense_date.strftime('%d %b %Y'),
        ],
    },
    'enquiries': {
        'label': 'Leads',
        'headers': ['ID', 'Property', 'Type', 'Status', 'Name', 'Email', 'Read', 'Created'],
        'queryset': lambda request: filter_by_brand(
            Enquiry.objects.select_related('property'), get_request_brand(request)
        ).order_by('-created_at'),
        'row': lambda e: [
            e.id,
            e.property.title,
            e.get_enquiry_type_display(),
            e.get_status_display(),
            e.name,
            e.email,
            'Yes' if e.is_read else 'No',
            e.created_at.strftime('%d %b %Y %H:%M'),
        ],
    },
    'visits': {
        'label': 'Lead visits',
        'headers': ['ID', 'Lead', 'Property', 'When', 'Status'],
        'queryset': lambda request: filter_by_brand(
            LeadVisit.objects.select_related('enquiry', 'property'), get_request_brand(request)
        ).order_by('-scheduled_at'),
        'row': lambda v: [
            v.id,
            v.enquiry.name,
            v.property.title,
            v.scheduled_at.strftime('%d %b %Y %H:%M'),
            v.get_status_display(),
        ],
    },
    'offers': {
        'label': 'Offers',
        'headers': ['ID', 'Lead', 'Type', 'Amount', 'Status'],
        'queryset': lambda request: filter_by_brand(
            Offer.objects.select_related('enquiry'), get_request_brand(request)
        ).order_by('-created_at'),
        'row': lambda o: [
            o.id,
            o.enquiry.name,
            o.get_offer_type_display(),
            f'₹{o.amount}',
            o.get_status_display(),
        ],
    },
    'deals': {
        'label': 'Sale deals',
        'headers': ['ID', 'Property', 'Buyer', 'Price', 'Status'],
        'queryset': lambda request: filter_by_brand(
            SaleDeal.objects.select_related('property'), get_request_brand(request)
        ).order_by('-created_at'),
        'row': lambda d: [
            d.id,
            d.property.title,
            d.buyer_name,
            f'₹{d.agreed_price}',
            d.get_status_display(),
        ],
    },
    'complaints': {
        'label': 'Complaints',
        'headers': ['ID', 'Property', 'Title', 'Status', 'Created'],
        'queryset': lambda request: filter_by_brand(
            Complaint.objects.select_related('property'), get_request_brand(request)
        ).order_by('-created_at'),
        'row': lambda c: [
            c.id,
            c.property.title,
            c.title,
            c.get_status_display(),
            c.created_at.strftime('%d %b %Y %H:%M'),
        ],
    },
    'campaigns': {
        'label': 'Marketing campaigns',
        'headers': ['ID', 'Property', 'Campaign', 'Channel', 'Status', 'Budget', 'Spend', 'Leads', 'Created by'],
        'queryset': lambda request: filter_by_brand(
            MarketingCampaign.objects.select_related('property', 'created_by'),
            get_request_brand(request),
        ).order_by('-created_at'),
        'row': lambda c: [
            c.id,
            c.property.title,
            c.title,
            c.get_channel_display(),
            c.get_status_display(),
            f'₹{c.budget}' if c.budget else '—',
            f'₹{c.spend}',
            c.leads_count,
            c.created_by.username if c.created_by else '—',
        ],
    },
    'logs': {
        'label': 'Activity logs',
        'headers': ['When', 'User', 'Action', 'Path', 'Status', 'IP'],
        'queryset': _brand_logs,
        'row': lambda log: [
            log.created_at.strftime('%d %b %Y %H:%M:%S'),
            log.username,
            log.get_action_display(),
            f'{log.method} {log.path}',
            log.status_code or '—',
            log.ip_address or '—',
        ],
    },
}


@admin_required
def staff_dashboard(request):
    brand = get_request_brand(request)
    users = users_for_brand(brand)
    logs = filter_by_brand(ActivityLog.objects.select_related('user'), brand)
    return render(
        request,
        'accounts/admin/dashboard.html',
        {
            **_admin_context('dashboard', request),
            'user_count': users.count(),
            'owner_count': users.filter(profile__role=UserProfile.ROLE_OWNER).count(),
            'tenant_count': users.filter(profile__role=UserProfile.ROLE_TENANT).count(),
            'staff_count': users.filter(Q(is_staff=True) | Q(profile__role=UserProfile.ROLE_ADMIN)).distinct().count(),
            'property_count': filter_by_brand(Property.objects.all(), brand).count(),
            'log_count': logs.count(),
            'recent_logs': logs[:12],
            'recent_users': users.select_related('profile').order_by('-date_joined')[:8],
            'page_header': build_page_header(
                'Admin dashboard',
                subtitle='Manage users, tables, privileges, and theme. Not visible to Owner/Tenant logins.',
                tooltip='Control center for the active brand.',
                actions=[
                    build_button('Create Owner / Tenant login', href=reverse('staff_create_user'), variant='primary'),
                    build_button('Message users', href=reverse('staff_broadcast'), variant='secondary'),
                    build_button('Django admin', href='/admin/', variant='secondary'),
                    build_button(
                        'Page not found',
                        href=reverse('page_not_found'),
                        variant='secondary',
                    ),
                    build_button(
                        'Under construction',
                        href=reverse('under_construction'),
                        variant='secondary',
                    ),
                ],
            ),
            'kpis': build_kpis(
                [
                    {'label': 'Users', 'value': users.count()},
                    {'label': 'Owners', 'value': users.filter(profile__role=UserProfile.ROLE_OWNER).count()},
                    {'label': 'Tenants', 'value': users.filter(profile__role=UserProfile.ROLE_TENANT).count()},
                    {'label': 'Properties', 'value': filter_by_brand(Property.objects.all(), brand).count()},
                    {'label': 'Activity logs', 'value': logs.count()},
                ]
            ),
        },
    )


@admin_required
def staff_broadcast(request):
    brand = get_request_brand(request)
    users = users_for_brand(brand).select_related('profile').order_by('username')
    if request.method == 'POST':
        form = AdminBroadcastForm(request.POST, users=users)
        if form.is_valid():
            audience = form.cleaned_data['audience']
            title = form.cleaned_data['title']
            body = form.cleaned_data['body']
            qs = users.filter(is_active=True)
            if audience == 'owners':
                qs = qs.filter(profile__role=UserProfile.ROLE_OWNER)
            elif audience == 'tenants':
                qs = qs.filter(profile__role=UserProfile.ROLE_TENANT)
            elif audience == 'selected':
                qs = form.cleaned_data['users']
            count = 0
            for user in qs:
                notify_user(
                    user=user,
                    brand=brand,
                    kind='admin_message',
                    title=f'{title}: {body}'[:200],
                    url=reverse('inbox'),
                )
                count += 1
            messages.success(request, f'Message sent to {count} user{"s" if count != 1 else ""}.')
            return redirect('staff_broadcast')
    else:
        form = AdminBroadcastForm(users=users)
    return render(
        request,
        'accounts/admin/broadcast.html',
        {
            **_admin_context('dashboard', request),
            'form': form,
            'page_header': build_page_header(
                'Send a message',
                subtitle='Reach all users, owners, tenants, or a selected list.',
            ),
        },
    )


@admin_required
def staff_users(request):
    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()
    brand = get_request_brand(request)
    users = users_for_brand(brand).select_related('profile').annotate(log_count=Count('activity_logs')).order_by('-date_joined')
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(email__icontains=q)
        )
    if role:
        users = users.filter(profile__role=role)
    paging = paginate_table(request, users, PAGE_SIZE)
    table_rows = []
    for u in paging['object_list']:
        role_label = u.profile.get_role_display() if hasattr(u, 'profile') and u.profile else '—'
        status = 'Active' if u.is_active else 'Inactive'
        table_rows.append(
            {
                'user': mark_safe(
                    f'<a href="{reverse("staff_user_detail", args=[u.pk])}">{u.username}</a>'
                ),
                'email': u.email or '—',
                'role': role_label,
                'joined': u.date_joined.strftime('%d %b %Y'),
                'last_login': u.last_login.strftime('%d %b %Y %H:%M') if u.last_login else 'Never',
                'logs': u.log_count,
                'status': status,
            }
        )
    users_table = build_table(
        id='admin-users',
        columns=[
            {'key': 'user', 'label': 'User', 'width': '16%', 'html': True, 'tooltip': 'Username — click to open profile'},
            {'key': 'email', 'label': 'Email', 'width': '18%', 'tooltip': 'Contact email on the account'},
            {'key': 'role', 'label': 'Role', 'width': '10%', 'badge': True, 'tooltip': 'Admin, Owner, or Tenant'},
            {'key': 'joined', 'label': 'Joined', 'width': '12%', 'tooltip': 'Account creation date'},
            {'key': 'last_login', 'label': 'Last login', 'width': '14%', 'tooltip': 'Most recent successful login'},
            {'key': 'logs', 'label': 'Logs', 'width': '8%', 'align': 'center', 'tooltip': 'Activity log count for this user'},
            {'key': 'status', 'label': 'Status', 'width': '10%', 'badge': True, 'tooltip': 'Active accounts can sign in'},
        ],
        rows=table_rows,
        empty_text='No users.',
    )
    role_choices = [('', 'All roles')] + list(UserProfile.ROLE_CHOICES)
    users_filter = build_filter(
        [
            build_search(name='q', value=q, placeholder='Username / email', label='Search'),
            {
                'name': 'role',
                'label': 'Role',
                'type': 'select',
                'value': role,
                'choices': role_choices,
            },
        ],
        submit_label='Filter',
        aria_label='Filter users',
    )
    users_help_popup = build_popup(
        'users-help',
        title='Users table',
        body='Search by username or email, filter by role, then open a user to change role or activate/deactivate.',
        cancel_label='Close',
    )
    return render(
        request,
        'accounts/admin/users.html',
        {
            **_admin_context('users'),
            'items': paging['object_list'],
            'page': paging['page'],
            'paging': paging,
            'q': q,
            'selected_role': role,
            'roles': UserProfile.ROLE_CHOICES,
            'filter_query': pagination_query(request, page=None, thru=None),
            'users_table': users_table,
            'users_filter': users_filter,
            'users_help_popup': users_help_popup,
            'page_header': build_page_header(
                'Users',
                subtitle=f'All Owner, Tenant, and Admin accounts. {PAGE_SIZE} per page.',
                tooltip='Manage logins for every brand from this shared admin panel.',
                actions=[
                    build_button('Help', variant='secondary', size='sm', open_popup='users-help'),
                    build_button('Create login', href=reverse('staff_create_user'), variant='primary'),
                ],
            ),
        },
    )


@admin_required
def staff_user_detail(request, user_id):
    brand = get_request_brand(request)
    target = get_object_or_404(
        users_for_brand(brand).select_related('profile'),
        pk=user_id,
    )
    logs = filter_by_brand(
        ActivityLog.objects.filter(Q(user=target) | Q(username=target.username)),
        brand,
    )[:40]
    return render(
        request,
        'accounts/admin/user_detail.html',
        {
            **_admin_context('users', request),
            'target': target,
            'logs': logs,
            'page_header': build_page_header(
                target.username,
                subtitle=(
                    f'{target.email or "No email"} · Role: '
                    f'{target.profile.get_role_display() if getattr(target, "profile", None) else "—"}'
                ),
            ),
            'kpis': build_kpis(
                [
                    {'label': 'Active', 'value': 'Yes' if target.is_active else 'No'},
                    {'label': 'Staff', 'value': 'Yes' if target.is_staff else 'No'},
                    {'label': 'Superuser', 'value': 'Yes' if target.is_superuser else 'No'},
                    {
                        'label': 'Last login',
                        'value': target.last_login.strftime('%d %b %Y %H:%M') if target.last_login else 'Never',
                    },
                ]
            ),
        },
    )


@admin_required
@require_POST
def staff_user_toggle(request, user_id):
    brand = get_request_brand(request)
    target = get_object_or_404(users_for_brand(brand), pk=user_id)
    action = request.POST.get('action')
    profile, _ = UserProfile.objects.get_or_create(user=target)

    if target.pk == request.user.pk and action in {'deactivate', 'remove_staff', 'role_tenant', 'role_owner'}:
        messages.error(request, 'You cannot apply that change to your own account.')
        return redirect('staff_user_detail', user_id=target.pk)

    msg = 'Updated'
    if action == 'activate':
        target.is_active = True
        msg = f'Activated {target.username}'
    elif action == 'deactivate':
        target.is_active = False
        msg = f'Deactivated {target.username}'
    elif action == 'make_staff':
        target.is_staff = True
        profile.role = UserProfile.ROLE_ADMIN
        msg = f'Made {target.username} admin'
    elif action == 'remove_staff':
        target.is_staff = False
        target.is_superuser = False
        profile.role = UserProfile.ROLE_OWNER
        msg = f'Removed admin from {target.username}'
    elif action == 'role_owner':
        profile.role = UserProfile.ROLE_OWNER
        target.is_staff = False
        msg = f'Set {target.username} as Owner'
    elif action == 'role_tenant':
        profile.role = UserProfile.ROLE_TENANT
        target.is_staff = False
        msg = f'Set {target.username} as Tenant'
    elif action == 'role_admin':
        profile.role = UserProfile.ROLE_ADMIN
        target.is_staff = True
        msg = f'Set {target.username} as Admin'
    else:
        messages.error(request, 'Unknown action.')
        return redirect('staff_user_detail', user_id=target.pk)

    target.save()
    profile.save()
    log_activity(request=request, action='update', message=msg)
    messages.success(request, msg)
    return redirect('staff_user_detail', user_id=target.pk)


@admin_required
def staff_create_user(request):
    if request.method == 'POST':
        form = AdminCreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(created_by=request.user, brand=get_request_brand(request))
            log_activity(
                request=request,
                action='create',
                message=f'Created {user.profile.get_role_display()} login: {user.username}',
            )
            messages.success(
                request,
                f'Created {user.profile.get_role_display()} login — username: {user.username}',
            )
            return redirect('staff_user_detail', user_id=user.pk)
    else:
        form = AdminCreateUserForm()
    return render(
        request,
        'accounts/admin/create_user.html',
        {**_admin_context('create_user'), 'form': form, 'page_header': build_page_header(
            'Create Owner / Tenant login',
            subtitle='Admin sets username, password, and role. Privileges for that role are controlled under Privileges.',
        )},
    )


@admin_required
def staff_activity_logs(request):
    q = request.GET.get('q', '').strip()
    action = request.GET.get('action', '').strip()
    brand = get_request_brand(request)
    logs = filter_by_brand(ActivityLog.objects.select_related('user'), brand)
    if q:
        logs = logs.filter(
            Q(username__icontains=q)
            | Q(path__icontains=q)
            | Q(message__icontains=q)
            | Q(ip_address__icontains=q)
        )
    if action:
        logs = logs.filter(action=action)
    paging = paginate_table(request, logs, PAGE_SIZE)
    table_rows = []
    for log in paging['object_list']:
        user_cell = log.username
        if log.user_id:
            user_cell = mark_safe(
                f'<a href="{reverse("staff_user_detail", args=[log.user_id])}">{log.username}</a>'
            )
        table_rows.append(
            {
                'when': log.created_at.strftime('%d %b %Y %H:%M:%S'),
                'user': user_cell,
                'action': log.get_action_display(),
                'request': f'{log.method} {log.path}',
                'status': log.status_code or '—',
                'ip': log.ip_address or '—',
                'message': log.message,
            }
        )
    logs_table = build_table(
        id='admin-logs',
        columns=[
            {'key': 'when', 'label': 'When', 'width': '14%'},
            {'key': 'user', 'label': 'User', 'html': True},
            {'key': 'action', 'label': 'Action', 'badge': True},
            {'key': 'request', 'label': 'Request'},
            {'key': 'status', 'label': 'Status', 'width': '8%'},
            {'key': 'ip', 'label': 'IP', 'width': '10%'},
            {'key': 'message', 'label': 'Message'},
        ],
        rows=table_rows,
        empty_text='No logs.',
    )
    logs_filter = build_filter(
        [
            build_search(name='q', value=q, placeholder='User, path, IP, message', label='Search'),
            {
                'name': 'action',
                'label': 'Action',
                'type': 'select',
                'value': action,
                'choices': [('', 'All')] + list(ActivityLog.ACTION_CHOICES),
            },
        ],
        submit_label='Filter',
    )
    return render(
        request,
        'accounts/admin/logs.html',
        {
            **_admin_context('logs'),
            'items': paging['object_list'],
            'page': paging['page'],
            'paging': paging,
            'q': q,
            'selected_action': action,
            'action_choices': ActivityLog.ACTION_CHOICES,
            'filter_query': pagination_query(request, page=None, thru=None),
            'page_header': build_page_header(
                'Activity logs',
                subtitle=f'All site activity is captured here. {PAGE_SIZE} per page.',
            ),
            'logs_filter': logs_filter,
            'logs_table': logs_table,
        },
    )


@admin_required
def staff_table(request, table):
    config = TABLE_CONFIG.get(table)
    if not config:
        messages.error(request, 'Unknown table.')
        return redirect('staff_dashboard')

    qs = config['queryset'](request)
    paging = paginate_table(request, qs, PAGE_SIZE)
    rows = [config['row'](obj) for obj in paging['object_list']]
    data_table = build_table(
        id=f'admin-{table}',
        headers=config['headers'],
        rows=rows,
        empty_text='No rows.',
        caption=f'{config["label"]} table',
    )

    group_form = None
    if table == 'groups' and request.method == 'POST':
        group_form = GroupForm(request.POST)
        if group_form.is_valid():
            group_form.save()
            messages.success(request, 'Group created.')
            return redirect('staff_table', table='groups')
    elif table == 'groups':
        group_form = GroupForm()

    return render(
        request,
        'accounts/admin/table.html',
        {
            **_admin_context(table if table in {item['key'] for item in ADMIN_NAV} else ''),
            'table_key': table,
            'table_label': config['label'],
            'headers': config['headers'],
            'rows': rows,
            'data_table': data_table,
            'page': paging['page'],
            'paging': paging,
            'group_form': group_form,
            'filter_query': pagination_query(request, page=None, thru=None),
        },
    )


def _privileges_admin_context():
    return {
        'privileges_subnav': [
            {
                'key': 'role',
                'label': 'Role-based privileges',
                'url_name': 'staff_privileges',
            },
            {
                'key': 'user',
                'label': 'User-based privileges',
                'url_name': 'staff_user_privileges',
            },
        ],
    }


def _assignable_privilege_users():
    return (
        User.objects.filter(
            profile__role__in=(
                UserProfile.ROLE_OWNER,
                UserProfile.ROLE_TENANT,
                UserProfile.ROLE_MANAGER,
                UserProfile.ROLE_EMPLOYEE,
            ),
            is_active=True,
        )
        .select_related('profile')
        .order_by('username')
    )


def _effective_user_privileges(target):
    role = get_user_role(target)
    role_privs = RolePrivilege.objects.filter(role=role)
    overrides = {
        row.code: row
        for row in UserPrivilege.objects.filter(
            user=target,
            code__in=role_privs.values('code'),
        )
    }
    rows = []
    effective = {}
    for priv in role_privs:
        override = overrides.get(priv.code)
        enabled = override.enabled if override else priv.enabled
        effective[priv.code] = enabled
        rows.append(
            {
                'code': priv.code,
                'label': priv.label,
                'enabled': enabled,
                'role_default': priv.enabled,
                'has_override': override is not None,
            }
        )
    return role, rows, effective


@admin_required
def staff_privileges(request):
    ensure_default_privileges()
    privileges = RolePrivilege.objects.all()
    if request.method == 'POST':
        form = PrivilegeToggleForm(privileges, request.POST)
        if form.is_valid():
            for priv in privileges:
                priv.enabled = form.cleaned_data.get(f'priv_{priv.pk}', False)
                priv.save(update_fields=['enabled'])
            log_activity(request=request, action='update', message='Updated role privileges')
            messages.success(request, 'Privileges updated.')
            return redirect('staff_privileges')
    else:
        form = PrivilegeToggleForm(privileges)

    owner_privs = privileges.filter(role=UserProfile.ROLE_OWNER)
    tenant_privs = privileges.filter(role=UserProfile.ROLE_TENANT)
    manager_privs = privileges.filter(role=UserProfile.ROLE_MANAGER)
    employee_privs = privileges.filter(role=UserProfile.ROLE_EMPLOYEE)
    return render(
        request,
        'accounts/admin/privileges.html',
        {
            **_admin_context('privileges'),
            **_privileges_admin_context(),
            'privileges_active_tab': 'role',
            'form': form,
            'owner_privs': owner_privs,
            'tenant_privs': tenant_privs,
            'manager_privs': manager_privs,
            'employee_privs': employee_privs,
            'page_header': build_page_header(
                'Role-based privileges',
                subtitle='Turn features on/off for Owner, Manager, Employee, and Tenant roles.',
            ),
        },
    )


@admin_required
def staff_user_privileges(request):
    ensure_default_privileges()
    users = _assignable_privilege_users()
    user_id = (request.GET.get('user') or request.POST.get('user_id') or '').strip()
    target = None
    role = None
    privilege_rows = []
    effective = {}
    form = None

    if user_id:
        target = get_object_or_404(User, pk=user_id)
        role, privilege_rows, effective = _effective_user_privileges(target)
        role_privs = RolePrivilege.objects.filter(role=role)

        if request.method == 'POST':
            if request.POST.get('action') == 'reset':
                UserPrivilege.objects.filter(user=target).delete()
                log_activity(
                    request=request,
                    action='update',
                    message=f'Reset user privileges to role defaults: {target.username}',
                )
                messages.success(request, 'User privileges reset to role defaults.')
                return redirect(f'{reverse("staff_user_privileges")}?user={target.pk}')

            form = UserPrivilegeToggleForm(role_privs, effective, request.POST)
            if form.is_valid():
                for priv in role_privs:
                    enabled = form.cleaned_data.get(f'priv_{priv.code}', False)
                    UserPrivilege.objects.update_or_create(
                        user=target,
                        code=priv.code,
                        defaults={'enabled': enabled, 'label': priv.label},
                    )
                log_activity(
                    request=request,
                    action='update',
                    message=f'Updated user privileges: {target.username}',
                )
                messages.success(request, 'User privileges saved.')
                return redirect(f'{reverse("staff_user_privileges")}?user={target.pk}')
        else:
            form = UserPrivilegeToggleForm(role_privs, effective)

    return render(
        request,
        'accounts/admin/user_privileges.html',
        {
            **_admin_context('privileges'),
            **_privileges_admin_context(),
            'privileges_active_tab': 'user',
            'users': users,
            'target': target,
            'selected_user_id': user_id,
            'role': role,
            'role_label': target.profile.get_role_display() if target and getattr(target, 'profile', None) else '',
            'privilege_rows': privilege_rows,
            'form': form,
            'page_header': build_page_header(
                'User-based privileges',
                subtitle='Grant or restrict module access for a single login, on top of their role.',
            ),
        },
    )


@admin_required
def staff_brands(request):
    ensure_default_brands()
    brands = Brand.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        brand_id = request.POST.get('brand_id')
        brand = get_object_or_404(Brand, pk=brand_id) if brand_id else None
        if action == 'preview' and brand:
            request.session[BRAND_SESSION_KEY] = brand.slug
            messages.success(request, f'Previewing brand: {brand.name}. Open the site to see it.')
            return redirect('staff_brands')
        if action == 'clear_preview':
            request.session.pop(BRAND_SESSION_KEY, None)
            messages.info(request, 'Brand preview cleared — using host/default brand.')
            return redirect('staff_brands')
        if action == 'make_default' and brand:
            brand.is_default = True
            brand.save()
            messages.success(request, f'{brand.name} is now the default brand.')
            return redirect('staff_brands')
    preview_slug = request.session.get(BRAND_SESSION_KEY, '')
    return render(
        request,
        'accounts/admin/brands.html',
        {
            **_admin_context('brands'),
            'brands': brands,
            'preview_slug': preview_slug,
            'page_header': build_page_header(
                'Brands',
                subtitle='Multiple brands share this admin panel. Each has its own colors, header/footer, hosts, and base URL.',
                tooltip='PropKeep and CheckPro Data are separate brands under one staff console.',
                actions=[build_button('Add brand', href=reverse('staff_brand_create'), variant='primary')],
            ),
        },
    )


@admin_required
def staff_brand_create(request):
    return _staff_brand_form(request, brand=None)


@admin_required
def staff_brand_edit(request, brand_id):
    brand = get_object_or_404(Brand, pk=brand_id)
    return _staff_brand_form(request, brand=brand)


def _staff_brand_form(request, brand):
    ensure_default_brands()
    if request.method == 'POST':
        form = BrandForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            saved = form.save()
            log_activity(request=request, action='update', message=f'Saved brand {saved.name}')
            messages.success(request, f'Brand “{saved.name}” saved.')
            return redirect('staff_brands')
    else:
        form = BrandForm(instance=brand)
    return render(
        request,
        'accounts/admin/theme.html',
        {
            **_admin_context('brands'),
            'form': form,
            'theme': brand,
            'page_header': build_page_header(
                f'Edit {brand.name}' if brand else 'Add brand',
                subtitle='Logo, colors, header/footer, fonts, hosts, and public base URL for this brand.',
                tooltip='Uploads are stored under media/{brand_slug}/{brand-id}/logo|icon|banner/.',
            ),
        },
    )


@admin_required
def staff_theme(request):
    """Edit the currently active (or default) brand theme — shortcut from Theme settings."""
    ensure_default_brands()
    brand = getattr(request, 'brand', None) or Brand.objects.filter(is_default=True).first() or Brand.objects.first()
    if request.method == 'POST':
        form = BrandForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            form.save()
            log_activity(request=request, action='update', message=f'Updated theme for {brand.name}')
            messages.success(request, 'Theme settings saved. Refresh to see changes.')
            return redirect('staff_theme')
    else:
        form = BrandForm(instance=brand)
    return render(
        request,
        'accounts/admin/theme.html',
        {
            **_admin_context('theme'),
            'form': form,
            'theme': brand,
            'page_header': build_page_header(
                f'Theme — {brand.name}',
                subtitle='Edit colors (including header & footer), fonts, and table style for the active brand.',
                tooltip='To manage all brands, open Brands in the admin sidebar.',
                actions=[
                    build_button('All brands', href=reverse('staff_brands'), variant='secondary'),
                    build_button('UI components', href=reverse('staff_components'), variant='secondary'),
                ],
            ),
        },
    )


@admin_required
def staff_promotions(request):
    brand = get_request_brand(request)
    promotions = SitePromotion.objects.filter(brand=brand).order_by('sort_order', '-created_at')
    promo_rows = [
        {
            'title': promo.title,
            'placement': promo.get_placement_display(),
            'active': 'Yes' if promo.is_active else 'No',
            'sort': promo.sort_order,
            'dates': (
                f'{promo.start_date or "—"} – {promo.end_date or "—"}'
            ),
            'edit': mark_safe(f'<a href="{reverse("staff_promotion_edit", args=[promo.pk])}">Edit</a>'),
        }
        for promo in promotions
    ]
    return render(
        request,
        'accounts/admin/promotions.html',
        {
            **_admin_context('promotions', request),
            'promotions': promotions,
            'page_header': build_page_header(
                'Site promotions',
                subtitle='Brand-wide banners and offers for homepage and marketing page.',
                actions=[build_button('Add promotion', href=reverse('staff_promotion_create'), variant='primary')],
            ),
            'promotions_table': build_table(
                id='admin-promotions',
                columns=[
                    {'key': 'title', 'label': 'Title'},
                    {'key': 'placement', 'label': 'Placement'},
                    {'key': 'active', 'label': 'Active'},
                    {'key': 'sort', 'label': 'Sort'},
                    {'key': 'dates', 'label': 'Dates'},
                    {'key': 'edit', 'label': '', 'html': True},
                ],
                rows=promo_rows,
                empty_text='No promotions for this brand yet.',
            ),
        },
    )


@admin_required
def staff_promotion_create(request):
    return _staff_promotion_form(request, promotion=None)


@admin_required
def staff_promotion_edit(request, promotion_id):
    brand = get_request_brand(request)
    promotion = get_object_or_404(SitePromotion, pk=promotion_id, brand=brand)
    return _staff_promotion_form(request, promotion=promotion)


def _staff_promotion_form(request, promotion):
    brand = get_request_brand(request)
    if request.method == 'POST':
        form = SitePromotionForm(request.POST, request.FILES, instance=promotion)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.brand = brand
            saved.created_by = request.user
            saved.save()
            log_activity(request=request, action='update', message=f'Saved promotion {saved.title}')
            messages.success(request, f'Promotion “{saved.title}” saved.')
            return redirect('staff_promotions')
    else:
        form = SitePromotionForm(instance=promotion)
    return render(
        request,
        'accounts/admin/promotion_form.html',
        {
            **_admin_context('promotions', request),
            'form': form,
            'promotion': promotion,
            'page_header': build_page_header(
                'Edit promotion' if promotion else 'Add promotion',
                subtitle=f'Active brand: {brand.name}',
            ),
        },
    )


@admin_required
def staff_components(request):
    """Live gallery of every shared UI component with examples."""
    sample_table = build_table(
        id='demo-table',
        columns=[
            {'key': 'month', 'label': 'Month', 'tooltip': 'Billing month for the rent row', 'width': '120px'},
            {'key': 'tenant', 'label': 'Tenant', 'tooltip': 'Person currently renting this unit'},
            {'key': 'amount', 'label': 'Amount', 'align': 'right', 'tooltip': 'Amount recorded for this month'},
            {'key': 'status', 'label': 'Status', 'badge': True, 'tooltip': 'Paid / Pending / Partial / Overdue'},
        ],
        rows=[
            {'month': 'Jul 2026', 'tenant': 'Arun', 'amount': '₹22,000', 'status': 'Paid'},
            {'month': 'Aug 2026', 'tenant': 'Arun', 'amount': '₹22,000', 'status': 'Pending'},
        ],
        empty_text='No demo rows.',
    )
    return render(
        request,
        'accounts/admin/components.html',
        {
            **_admin_context('components'),
            'page_header': build_page_header(
                'UI components',
                subtitle='All shared components live under accounts/components.py — use {% load ui %}.',
                tooltip='Use this screen as a living style guide when building new pages.',
            ),
            'demo_heading': build_heading(
                'Heading with tooltip',
                level=2,
                tooltip='Pass text, level (1–4), tooltip, and optional hint.',
                hint='build_heading(text, level=2, tooltip="...", hint="...")',
            ),
            'demo_kpis': build_kpis(
                [
                    {'label': 'Properties', 'value': 12, 'hint': 'Total units'},
                    {'label': 'Unread', 'value': 3, 'tone': 'warn'},
                ]
            ),
            'demo_filter': build_filter(
                [
                    build_search(name='q', value='', placeholder='Search demo...', label='Search'),
                    {
                        'name': 'status',
                        'label': 'Status',
                        'type': 'select',
                        'choices': [('', 'All'), ('paid', 'Paid'), ('pending', 'Pending')],
                        'tooltip': 'Filter rows by payment status',
                    },
                ],
                submit_label='Apply',
            ),
            'demo_table': sample_table,
            'demo_popup': build_popup(
                'demo-popup',
                title='Example popup',
                body='Open with a button that sets open_popup="demo-popup".',
                cancel_label='Close',
            ),
            'demo_empty': build_empty('Nothing here — empty state example.', action_label='Primary action', action_href='#'),
            'demo_buttons': [
                build_button('Primary', variant='primary'),
                build_button('Secondary', variant='secondary'),
                build_button('Danger', variant='danger', size='sm'),
                build_button('Open popup', variant='secondary', open_popup='demo-popup'),
            ],
            'demo_status': build_status_page(
                'Under construction',
                subtitle='Placeholder used when a feature is not ready yet.',
                hint='Open the dedicated screens at /accounts/page-not-found/ and /accounts/under-construction/.',
                level='info',
                empty_text='Coming soon.',
                actions=[
                    {'label': 'Page not found', 'href': reverse('page_not_found'), 'variant': 'primary'},
                    {'label': 'Preview 403', 'href': reverse('error_preview', args=['403']), 'variant': 'secondary'},
                    {'label': 'Preview 500', 'href': reverse('error_preview', args=['500']), 'variant': 'secondary'},
                    {'label': 'Under construction', 'href': reverse('under_construction'), 'variant': 'secondary'},
                ],
            ),
            'demo_404': build_status_page(
                'Page not found',
                code='404',
                subtitle='That address is not in PropKeep.',
                hint='Check the URL, or go back to listings and the dashboard.',
                level='warn',
                empty_text='No page matches this URL.',
                actions=[
                    {'label': 'Open 404 page', 'href': reverse('page_not_found'), 'variant': 'primary'},
                ],
            ),
            'demo_alert': build_alert('Example alert — use for errors, warnings, and tips.', level='info'),
        },
    )
