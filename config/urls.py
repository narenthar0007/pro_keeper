from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from accounts import status_pages
from hrms.api import AttendanceViewSet, EmployeeViewSet, SiteViewSet, punch_code_decode
from appointments import api as appointments_api
from appointments.views import public_book
from storefront.views import public_site
from properties.api import (
    ExpenseViewSet,
    MyPropertyViewSet,
    PropertyViewSet,
    RentPaymentViewSet,
    TenantViewSet,
)

router = DefaultRouter()
router.register('properties', PropertyViewSet, basename='api-properties')
router.register('my-properties', MyPropertyViewSet, basename='api-my-properties')
router.register('tenants', TenantViewSet, basename='api-tenants')
router.register('payments', RentPaymentViewSet, basename='api-payments')
router.register('expenses', ExpenseViewSet, basename='api-expenses')
router.register('hrms/employees', EmployeeViewSet, basename='api-hrms-employees')
router.register('hrms/attendance', AttendanceViewSet, basename='api-hrms-attendance')
router.register('hrms/sites', SiteViewSet, basename='api-hrms-sites')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('hrms/', include('hrms.urls')),
    path('marketplace/', include('marketplace.urls')),
    path('business/', include('storefront.urls')),
    path('appointments/', include('appointments.urls')),
    path('book/<slug:booking_slug>/', public_book, name='public_book'),
    path('w/<slug:slug>/', public_site, name='storefront_public'),
    path('api/', include(router.urls)),
    path('api/appointments/', appointments_api.appointments_list_create, name='api_appointments'),
    path('api/appointments/<int:pk>/status/', appointments_api.appointment_status, name='api_appointment_status'),
    path('api/appointments/availability/', appointments_api.availability_rules, name='api_appointment_availability'),
    path('api/appointments/generate-link/', appointments_api.generate_link, name='api_appointment_generate_link'),
    path('api/public/booking/<slug:booking_slug>/', appointments_api.public_booking_endpoint, name='api_public_booking'),
    path('api/mobile/', include('properties.mobile_urls')),
    path('api/hrms/punch-code/decode/', punch_code_decode, name='api-hrms-punch-decode'),
    path('api-auth/', include('rest_framework.urls')),
    path('', include('properties.urls')),
]

handler403 = 'accounts.status_pages.permission_denied'
handler404 = 'accounts.status_pages.page_not_found'
handler500 = 'accounts.status_pages.server_error'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Last: unknown paths use the designed 404 (also when DEBUG is on).
urlpatterns += [
    re_path(r'^.*$', status_pages.page_not_found),
]
