from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from accounts import status_pages
from hrms.api import AttendanceViewSet, EmployeeViewSet, SiteViewSet, punch_code_decode
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
    path('api/', include(router.urls)),
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
