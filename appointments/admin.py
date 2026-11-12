from django.contrib import admin

from appointments.models import (
    Appointment,
    AppointmentAuditLog,
    AppointmentAvailability,
    AppointmentHoliday,
    AppointmentNotification,
    AppointmentSettings,
)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'host', 'appointment_date', 'start_time', 'status', 'booked_by')
    list_filter = ('status', 'booked_by', 'appointment_date')
    search_fields = ('title', 'guest_name', 'guest_email')


admin.site.register(AppointmentAvailability)
admin.site.register(AppointmentSettings)
admin.site.register(AppointmentHoliday)
admin.site.register(AppointmentAuditLog)
admin.site.register(AppointmentNotification)
