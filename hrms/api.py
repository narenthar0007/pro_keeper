from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.brand_scoping import get_request_brand
from accounts.models import UserProfile
from accounts.privileges import get_user_role, is_admin_user
from django.core.exceptions import ValidationError

from hrms.models import Attendance, Employee, Site, SiteAssignment, SiteDailyUpdate
from hrms.services.attendance import (
    apply_regularize,
    approve_employee,
    decide_regularize,
    mark_attendance,
    punch,
)
from hrms.services.punch_codes import decode_punch_code
from hrms.services.scoping import (
    attendance_for_user,
    employees_for_user,
    get_owner_for_user,
    sites_for_user,
    user_can_access_hrms,
)
from hrms.services.users import ensure_employee_login


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            'id',
            'emp_code',
            'name',
            'mobile',
            'joining_date',
            'job_role',
            'team',
            'leader',
            'gender',
            'company_name',
            'employment_type',
            'status',
            'email',
            'emergency',
            'address',
            'remarks',
            'latitude',
            'longitude',
            'default_site',
            'approval_status',
            'is_not_working',
            'owner',
        ]
        read_only_fields = ['owner', 'approval_status']


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['owner', 'punch_code_in', 'punch_code_out', 'working_hours']


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = '__all__'
        read_only_fields = ['owner', 'created_by']


def _deny_if_no_hrms(request):
    if not user_can_access_hrms(request.user):
        return Response({'detail': 'HRMS not enabled.'}, status=status.HTTP_403_FORBIDDEN)
    return None


class EmployeeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        return employees_for_user(self.request.user, self.request)

    def create(self, request, *args, **kwargs):
        denied = _deny_if_no_hrms(request)
        if denied:
            return denied
        role = get_user_role(request.user)
        if role not in (UserProfile.ROLE_OWNER, UserProfile.ROLE_MANAGER) and not is_admin_user(request.user):
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        owner = request.user if role == UserProfile.ROLE_OWNER else get_owner_for_user(request.user)
        emp = serializer.save(
            owner=owner,
            brand=get_request_brand(request),
            created_by=request.user,
            approval_status=Employee.APPROVAL_PENDING,
        )
        ensure_employee_login(
            emp,
            role=UserProfile.ROLE_EMPLOYEE,
            brand=get_request_brand(request),
            created_by=request.user,
        )
        return Response(self.get_serializer(emp).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        emp = self.get_object()
        try:
            approve_employee(actor=request.user, employee=emp, approve=True)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(emp).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        emp = self.get_object()
        try:
            approve_employee(actor=request.user, employee=emp, approve=False)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(emp).data)


class AttendanceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AttendanceSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return attendance_for_user(self.request.user, self.request)

    @action(detail=False, methods=['post'])
    def punch(self, request):
        denied = _deny_if_no_hrms(request)
        if denied:
            return denied
        try:
            att, wa_link, warn = punch(
                user=request.user,
                punch_type=request.data.get('type') or request.data.get('punch_type'),
                lat=request.data.get('lat') or request.data.get('latitude'),
                lng=request.data.get('lng') or request.data.get('longitude'),
                site=None,
                request=request,
            )
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = AttendanceSerializer(att).data
        data['whatsapp_url'] = wa_link
        data['whatsapp_warning'] = warn
        return Response(data)

    @action(detail=False, methods=['post'])
    def regularize(self, request):
        emp = get_object_or_404_emp(request, request.data.get('employee'))
        try:
            att = apply_regularize(
                actor=request.user,
                employee=emp,
                date=request.data.get('date'),
                reason=request.data.get('reason') or '',
                request=request,
            )
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AttendanceSerializer(att).data)

    @action(detail=True, methods=['post'], url_path='approve-regularize')
    def approve_regularize(self, request, pk=None):
        att = self.get_object()
        try:
            decide_regularize(actor=request.user, attendance=att, approve=True)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AttendanceSerializer(att).data)

    @action(detail=True, methods=['post'], url_path='reject-regularize')
    def reject_regularize(self, request, pk=None):
        att = self.get_object()
        try:
            decide_regularize(actor=request.user, attendance=att, approve=False)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AttendanceSerializer(att).data)


def get_object_or_404_emp(request, pk):
    from django.shortcuts import get_object_or_404

    return get_object_or_404(employees_for_user(request.user, request), pk=pk)


class SiteViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = SiteSerializer

    def get_queryset(self):
        return sites_for_user(self.request.user, self.request)

    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user,
            brand=get_request_brand(self.request),
            created_by=self.request.user,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def punch_code_decode(request):
    try:
        data = decode_punch_code(request.data.get('code') or '')
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(data)
