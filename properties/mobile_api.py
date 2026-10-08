"""Token-authenticated API used by the Expo mobile app."""

from calendar import month_name

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.brand_scoping import assign_brand, get_request_brand, users_for_brand
from accounts.models import UserProfile
from accounts.privileges import get_user_role, has_privilege, is_admin_user, list_privilege_codes_for_user
from .lead_utils import log_lead_activity
from .mobile_serializers import (
    AmenitySerializer,
    BuildingSerializer,
    EnquirySerializer,
    ExpenseSerializer,
    InboxSerializer,
    JoinRequestSerializer,
    PropertySerializer,
    RentPaymentSerializer,
    TenantSerializer,
)
from .models import (
    Amenity,
    Building,
    Enquiry,
    Expense,
    Property,
    RentPayment,
    Tenant,
    TenantJoinRequest,
    UserNotification,
    ensure_default_amenities,
    income_expense_for_month,
    properties_missing_rent_for_month,
)
from .notifications import notify_user
from .tenant_access import create_login_for_tenant

AUTH = [TokenAuthentication, SessionAuthentication]


def _forbidden(message='Not allowed'):
    return Response({'detail': message}, status=status.HTTP_403_FORBIDDEN)


def _need(user, code):
    return has_privilege(user, code)


def _user_payload(user):
    role = get_user_role(user)
    privileges = list_privilege_codes_for_user(user) if user.is_authenticated else []
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': role,
        'is_admin': is_admin_user(user),
        'privileges': privileges,
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return Response({'detail': 'Invalid username or password.'}, status=400)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': _user_payload(user)})


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response({'ok': True})


@api_view(['GET'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(_user_payload(request.user))


@api_view(['GET'])
@permission_classes([AllowAny])
def options_view(request):
    ensure_default_amenities()
    brand = get_request_brand(request)
    buildings = Building.objects.none()
    if request.user.is_authenticated:
        buildings = Building.for_user(request.user, brand=brand).order_by('name')
    return Response(
        {
            'amenities': AmenitySerializer(
                Amenity.objects.exclude(code='others').order_by('label'), many=True
            ).data,
            'buildings': BuildingSerializer(buildings, many=True).data,
            'property_types': [{'value': k, 'label': v} for k, v in Property.PROPERTY_TYPES],
            'listing_types': [{'value': k, 'label': v} for k, v in Property.LISTING_TYPE_CHOICES],
            'furnishing': [{'value': k, 'label': v} for k, v in Property.FURNISHING_CHOICES],
        }
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def listings_view(request):
    brand = get_request_brand(request)
    qs = (
        Property.for_brand(brand)
        .filter(is_listed_publicly=True)
        .exclude(listing_type='sale', sale_status='sold')
        .select_related('owner', 'building')
        .prefetch_related('amenities')
    )
    city = request.GET.get('city', '').strip()
    q = request.GET.get('q', '').strip()
    if city:
        qs = qs.filter(city__icontains=city)
    if q:
        qs = qs.filter(title__icontains=q)
    return Response(PropertySerializer(qs[:80], many=True).data)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def listing_detail_view(request, pk):
    brand = get_request_brand(request)
    prop = Property.objects.filter(pk=pk, brand=brand, is_listed_publicly=True).first()
    if prop is None:
        return Response({'detail': 'Not found'}, status=404)
    if request.method == 'GET':
        data = PropertySerializer(prop).data
        data['can_request_join'] = False
        if (
            request.user.is_authenticated
            and get_user_role(request.user) == UserProfile.ROLE_TENANT
            and prop.is_for_rent
            and not prop.is_occupied
            and not prop.tenants.filter(user=request.user, is_active=True).exists()
        ):
            pending = prop.join_requests.filter(user=request.user, status='pending').exists()
            data['can_request_join'] = not pending
            data['join_request_pending'] = pending
        return Response(data)

    action = request.data.get('action')
    if action == 'join':
        if not request.user.is_authenticated:
            return Response({'detail': 'Login as a tenant first.'}, status=401)
        if get_user_role(request.user) != UserProfile.ROLE_TENANT:
            return _forbidden('Only tenant accounts can request a vacant property.')
        if not prop.is_for_rent or prop.is_occupied:
            return Response({'detail': 'This property is not vacant.'}, status=400)
        if prop.join_requests.filter(user=request.user, status='pending').exists():
            return Response({'detail': 'Request already sent.'}, status=400)
        TenantJoinRequest.objects.create(
            property=prop,
            brand=brand,
            user=request.user,
            message=request.data.get('message') or '',
        )
        notify_user(
            user=prop.owner,
            brand=brand,
            kind='join_request',
            title=f'{request.user.username} asked to join {prop.title}',
            url=f'/my-properties/{prop.pk}/',
        )
        return Response({'ok': True})

    enquiry = Enquiry(
        property=prop,
        name=request.data.get('name') or '',
        email=request.data.get('email') or '',
        phone=request.data.get('phone') or '',
        message=request.data.get('message') or '',
    )
    assign_brand(enquiry, brand)
    if not enquiry.name or not enquiry.email or not enquiry.message:
        return Response({'detail': 'Name, email, and message are required.'}, status=400)
    enquiry.save()
    log_lead_activity(enquiry, verb='created', message='Mobile enquiry')
    if prop.owner_id:
        notify_user(
            user=prop.owner,
            brand=brand,
            kind='enquiry',
            title=f'New lead: {enquiry.name} on {prop.title}',
        )
    return Response(EnquirySerializer(enquiry).data, status=201)


@api_view(['GET'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    if not _need(request.user, 'view_dashboard'):
        return _forbidden()
    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    rent_props = props.filter(listing_type='rent')
    today = timezone.localdate()
    income, expenses, net = income_expense_for_month(
        request.user, today.year, today.month, brand=brand
    )
    due = properties_missing_rent_for_month(request.user, brand=brand)
    return Response(
        {
            'property_count': props.count(),
            'occupied': rent_props.filter(is_occupied=True).count(),
            'vacant': rent_props.filter(is_occupied=False).count(),
            'month_label': f'{month_name[today.month]} {today.year}',
            'month_income': str(income),
            'month_expenses': str(expenses),
            'month_net': str(net),
            'rent_due': PropertySerializer(due, many=True).data,
        }
    )


@api_view(['GET', 'POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def properties_view(request):
    if not _need(request.user, 'manage_properties'):
        return _forbidden()
    brand = get_request_brand(request)
    if request.method == 'GET':
        qs = Property.for_user(request.user, brand=brand).select_related('building').prefetch_related(
            'amenities', 'tenants'
        )
        return Response(PropertySerializer(qs, many=True).data)

    ensure_default_amenities()
    serializer = PropertySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    prop = serializer.save(owner=request.user)
    assign_brand(prop, brand)
    prop.save(update_fields=['brand'])
    return Response(PropertySerializer(prop).data, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def property_detail_view(request, pk):
    brand = get_request_brand(request)
    prop = Property.objects.filter(pk=pk, brand=brand).first()
    if prop is None or not prop.user_can_manage(request.user, brand=brand):
        return _forbidden()
    if request.method == 'GET':
        data = PropertySerializer(prop).data
        data['tenants'] = TenantSerializer(prop.tenants.all(), many=True).data
        data['payments'] = RentPaymentSerializer(prop.payments.all()[:30], many=True).data
        data['expenses'] = ExpenseSerializer(prop.expenses.all()[:30], many=True).data
        data['join_requests'] = JoinRequestSerializer(
            prop.join_requests.filter(status='pending'), many=True
        ).data
        return Response(data)
    if request.method == 'DELETE':
        if prop.owner_id != request.user.id:
            return _forbidden()
        prop.delete()
        return Response(status=204)
    serializer = PropertySerializer(prop, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    serializer.save()
    return Response(PropertySerializer(prop).data)


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def property_vacate_view(request, pk):
    if not _need(request.user, 'manage_properties'):
        return _forbidden()
    brand = get_request_brand(request)
    prop = Property.objects.filter(pk=pk, brand=brand).first()
    if prop is None or not prop.user_can_manage(request.user, brand=brand):
        return _forbidden()
    value = request.data.get('planned_vacate_date')
    if not value:
        return Response({'detail': 'Pick a future vacate date.'}, status=400)
    prop.planned_vacate_date = value
    tenant = prop.current_tenant
    if tenant:
        tenant.lease_end_date = value
        tenant.save(update_fields=['lease_end_date'])
    prop.save(update_fields=['planned_vacate_date'])
    return Response(PropertySerializer(prop).data)


@api_view(['GET', 'POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def tenants_view(request):
    if not _need(request.user, 'manage_tenants'):
        return _forbidden()
    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    if request.method == 'GET':
        qs = Tenant.objects.filter(property__in=props, brand=brand).select_related('property', 'user')
        return Response(TenantSerializer(qs, many=True).data)

    prop = props.filter(pk=request.data.get('property')).first()
    if prop is None:
        return Response({'detail': 'Choose a property you manage.'}, status=400)
    if prop.is_for_sale:
        return Response({'detail': 'Tenants cannot be added to sale listings.'}, status=400)
    serializer = TenantSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    extra = {
        'existing_username': serializer.validated_data.pop('existing_username', ''),
        'create_username': serializer.validated_data.pop('create_username', ''),
        'create_password': serializer.validated_data.pop('create_password', ''),
    }
    tenant = serializer.save(property=prop)
    _apply_login(tenant, extra, brand)
    if tenant.is_active:
        prop.is_occupied = True
        prop.save(update_fields=['is_occupied'])
    return Response(TenantSerializer(tenant).data, status=201)


def _apply_login(tenant, extra, brand):
    existing = (extra.get('existing_username') or '').strip()
    create_username = (extra.get('create_username') or '').strip()
    password = extra.get('create_password') or ''
    if existing:
        user = User.objects.filter(username=existing).first()
        if user:
            tenant.user = user
            tenant.save(update_fields=['user'])
    elif create_username and password:
        create_login_for_tenant(tenant, create_username, password, brand=brand, email=tenant.email)


@api_view(['PATCH'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def tenant_detail_view(request, pk):
    if not _need(request.user, 'manage_tenants'):
        return _forbidden()
    brand = get_request_brand(request)
    tenant = Tenant.objects.filter(
        pk=pk, brand=brand, property__in=Property.for_user(request.user, brand=brand)
    ).first()
    if tenant is None:
        return Response({'detail': 'Not found'}, status=404)
    serializer = TenantSerializer(tenant, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    extra = {
        'existing_username': serializer.validated_data.pop('existing_username', ''),
        'create_username': serializer.validated_data.pop('create_username', ''),
        'create_password': serializer.validated_data.pop('create_password', ''),
    }
    serializer.save()
    _apply_login(tenant, extra, brand)
    tenant.property.is_occupied = tenant.property.tenants.filter(is_active=True).exists()
    tenant.property.save(update_fields=['is_occupied'])
    return Response(TenantSerializer(tenant).data)


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def tenant_login_view(request, pk):
    if not _need(request.user, 'manage_tenants'):
        return _forbidden()
    brand = get_request_brand(request)
    tenant = Tenant.objects.filter(
        pk=pk, brand=brand, property__in=Property.for_user(request.user, brand=brand)
    ).first()
    if tenant is None:
        return Response({'detail': 'Not found'}, status=404)
    if tenant.user_id:
        return Response({'detail': f'Already has login: {tenant.user.username}'}, status=400)
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''
    if not username or not password:
        return Response({'detail': 'Username and password are required.'}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({'detail': 'Username already exists.'}, status=400)
    create_login_for_tenant(tenant, username, password, brand=brand, email=tenant.email)
    return Response(TenantSerializer(tenant).data)


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def join_request_review_view(request, pk):
    if not _need(request.user, 'manage_tenants'):
        return _forbidden()
    brand = get_request_brand(request)
    join = TenantJoinRequest.objects.filter(
        pk=pk, brand=brand, property__in=Property.for_user(request.user, brand=brand)
    ).first()
    if join is None:
        return Response({'detail': 'Not found'}, status=404)
    action = request.data.get('action')
    join.reviewed_at = timezone.now()
    if action == 'accept':
        join.status = 'accepted'
        join.save(update_fields=['status', 'reviewed_at'])
        Tenant.objects.create(
            property=join.property,
            user=join.user,
            name=join.user.get_full_name() or join.user.username,
            email=join.user.email or '',
            is_active=True,
            move_in_date=timezone.localdate(),
        )
        join.property.is_occupied = True
        join.property.save(update_fields=['is_occupied'])
        notify_user(
            user=join.user,
            brand=brand,
            kind='join_request',
            title=f'You were added to {join.property.title}',
        )
    else:
        join.status = 'rejected'
        join.save(update_fields=['status', 'reviewed_at'])
    return Response({'ok': True, 'status': join.status})


@api_view(['GET', 'POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def payments_view(request):
    if not _need(request.user, 'manage_payments') and not _need(request.user, 'view_own_payments'):
        return _forbidden()
    brand = get_request_brand(request)
    if request.method == 'GET':
        if _need(request.user, 'manage_payments'):
            qs = RentPayment.objects.filter(
                brand=brand, property__in=Property.for_user(request.user, brand=brand)
            )
        else:
            qs = RentPayment.objects.filter(brand=brand, tenant__user=request.user)
        return Response(RentPaymentSerializer(qs[:80], many=True).data)

    if not _need(request.user, 'manage_payments'):
        return _forbidden()
    serializer = RentPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    prop = Property.for_user(request.user, brand=brand).filter(
        pk=serializer.validated_data['property'].pk
    ).first()
    if prop is None:
        return _forbidden()
    payment = serializer.save()
    assign_brand(payment, brand)
    payment.save()
    return Response(RentPaymentSerializer(payment).data, status=201)


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def expenses_view(request):
    if not _need(request.user, 'manage_expenses'):
        return _forbidden()
    brand = get_request_brand(request)
    serializer = ExpenseSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    prop = Property.for_user(request.user, brand=brand).filter(
        pk=serializer.validated_data['property'].pk
    ).first()
    if prop is None:
        return _forbidden()
    expense = serializer.save()
    assign_brand(expense, brand)
    expense.save()
    return Response(ExpenseSerializer(expense).data, status=201)


@api_view(['GET', 'POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def inbox_view(request):
    if not _need(request.user, 'view_inbox'):
        return _forbidden()
    brand = get_request_brand(request)
    notes = UserNotification.objects.filter(user=request.user, brand=brand)
    if request.method == 'POST' and request.data.get('mark_all'):
        notes.filter(is_read=False).update(is_read=True)
        return Response({'ok': True})
    return Response(InboxSerializer(notes[:80], many=True).data)


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def rent_reminder_view(request):
    if not _need(request.user, 'manage_rent_reminders'):
        return _forbidden()
    brand = get_request_brand(request)
    ids = request.data.get('tenant_ids') or []
    body = (request.data.get('message') or 'Please pay this month’s rent.').strip()
    tenants = Tenant.objects.filter(
        pk__in=ids,
        is_active=True,
        property__in=Property.for_user(request.user, brand=brand),
    )
    sent = 0
    for tenant in tenants:
        if not tenant.user_id:
            continue
        notify_user(user=tenant.user, brand=brand, kind='rent_reminder', title=body[:200])
        sent += 1
    return Response({'sent': sent})


@api_view(['GET'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def tenant_portal_view(request):
    if not _need(request.user, 'view_tenant_portal'):
        return _forbidden()
    brand = get_request_brand(request)
    tenants = Tenant.objects.filter(user=request.user, brand=brand).select_related('property')
    return Response(
        {
            'tenants': TenantSerializer(tenants, many=True).data,
            'payments': RentPaymentSerializer(
                RentPayment.objects.filter(tenant__in=tenants).order_by('-month_for')[:40],
                many=True,
            ).data,
        }
    )


@api_view(['GET'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def enquiries_view(request):
    if not _need(request.user, 'view_enquiries'):
        return _forbidden()
    brand = get_request_brand(request)
    qs = Enquiry.objects.filter(
        brand=brand, property__in=Property.for_user(request.user, brand=brand)
    )
    return Response(EnquirySerializer(qs[:80], many=True).data)


@api_view(['GET'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def buildings_view(request):
    if not _need(request.user, 'view_buildings'):
        return _forbidden()
    brand = get_request_brand(request)
    qs = Building.for_user(request.user, brand=brand)
    return Response(BuildingSerializer(qs, many=True).data)


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def broadcast_view(request):
    if not is_admin_user(request.user):
        return _forbidden()
    brand = get_request_brand(request)
    audience = request.data.get('audience') or 'all'
    title = request.data.get('title') or 'Message from admin'
    body = request.data.get('body') or ''
    if not body:
        return Response({'detail': 'Message is required.'}, status=400)
    qs = users_for_brand(brand).filter(is_active=True)
    if audience == 'owners':
        qs = qs.filter(profile__role=UserProfile.ROLE_OWNER)
    elif audience == 'tenants':
        qs = qs.filter(profile__role=UserProfile.ROLE_TENANT)
    elif audience == 'selected':
        qs = qs.filter(pk__in=request.data.get('user_ids') or [])
    count = 0
    for user in qs:
        notify_user(
            user=user,
            brand=brand,
            kind='admin_message',
            title=f'{title}: {body}'[:200],
        )
        count += 1
    return Response({'sent': count})
