from django.urls import path

from hrms import views

urlpatterns = [
    path('', views.hrms_dashboard, name='hrms_dashboard'),
    path('employees/', views.employee_list, name='hrms_employees'),
    path('employees/add/', views.employee_create, name='hrms_employee_create'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='hrms_employee_edit'),
    path('employees/<int:pk>/approve/', views.employee_approve_get, name='hrms_employee_approve'),
    path('employees/<int:pk>/reject/', views.employee_reject_get, name='hrms_employee_reject'),
    path('managers/add/', views.manager_create, name='hrms_manager_create'),
    path('sites/', views.site_list, name='hrms_sites'),
    path('sites/add/', views.site_create, name='hrms_site_create'),
    path('sites/<int:pk>/', views.site_detail, name='hrms_site_detail'),
    path('attendance/', views.attendance_list, name='hrms_attendance'),
    path('attendance/mark/', views.attendance_mark, name='hrms_attendance_mark'),
    path('attendance/export/', views.attendance_export, name='hrms_attendance_export'),
    path('punch/', views.punch_view, name='hrms_punch'),
    path('regularize/', views.regularize_view, name='hrms_regularize'),
    path('approvals/', views.approvals, name='hrms_approvals'),
    path('updates/', views.update_list, name='hrms_updates'),
    path('updates/add/', views.update_create, name='hrms_update_create'),
    path('reports/', views.reports, name='hrms_reports'),
    path('employees/export/', views.employees_export, name='hrms_employees_export'),
    path('settings/', views.hrms_settings, name='hrms_settings'),
    path('settings/owner/<int:owner_id>/', views.admin_toggle_owner_hrms, name='hrms_admin_owner_settings'),
]
