from django.contrib import admin
from unfold.admin import ModelAdmin

from hrms.models import (
    Attendance,
    Employee,
    OwnerHrmsSettings,
    Site,
    SiteAssignment,
    SiteDailyUpdate,
    SiteMaterialEntry,
)


class SiteAssignmentInline(admin.TabularInline):
    model = SiteAssignment
    extra = 0


class SiteMaterialInline(admin.TabularInline):
    model = SiteMaterialEntry
    extra = 0


@admin.register(OwnerHrmsSettings)
class OwnerHrmsSettingsAdmin(ModelAdmin):
    list_display = ('owner', 'hrms_enabled', 'industry', 'whatsapp_number', 'is_paid', 'brand')
    list_filter = ('hrms_enabled', 'industry', 'is_paid', 'brand')
    search_fields = ('owner__username', 'whatsapp_number')


@admin.register(Site)
class SiteAdmin(ModelAdmin):
    list_display = ('name', 'owner', 'site_type', 'status', 'brand')
    list_filter = ('site_type', 'status', 'brand')
    search_fields = ('name', 'owner__username')
    inlines = [SiteAssignmentInline]


@admin.register(SiteAssignment)
class SiteAssignmentAdmin(ModelAdmin):
    list_display = ('site', 'manager', 'created_at')
    search_fields = ('site__name', 'manager__username')


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = (
        'emp_code',
        'name',
        'owner',
        'mobile',
        'approval_status',
        'status',
        'default_site',
    )
    list_filter = ('approval_status', 'status', 'brand')
    search_fields = ('emp_code', 'name', 'mobile', 'owner__username')


@admin.register(Attendance)
class AttendanceAdmin(ModelAdmin):
    list_display = (
        'date',
        'employee',
        'owner',
        'punch_in',
        'punch_out',
        'status',
        'regularized',
        'approval_status',
    )
    list_filter = ('status', 'regularized', 'approval_status', 'date')
    search_fields = ('employee__emp_code', 'employee__name', 'punch_code_in', 'punch_code_out')


@admin.register(SiteDailyUpdate)
class SiteDailyUpdateAdmin(ModelAdmin):
    list_display = ('date', 'site', 'manager', 'employees_present_count', 'percent_complete')
    list_filter = ('date',)
    inlines = [SiteMaterialInline]
