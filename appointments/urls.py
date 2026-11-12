from django.urls import path

from appointments import views

urlpatterns = [
    path('', views.dashboard, name='appointments_dashboard'),
    path('create/', views.create_appointment, name='appointments_create'),
    path('settings/', views.settings_view, name='appointments_settings'),
    path('calendar/', views.calendar_view, name='appointments_calendar'),
    path('<int:pk>/', views.detail, name='appointments_detail'),
    path('<int:pk>/approve/', views.approve, name='appointments_approve'),
    path('<int:pk>/reject/', views.reject, name='appointments_reject'),
    path('<int:pk>/cancel/', views.cancel, name='appointments_cancel'),
    path('link/toggle/', views.toggle_public_link, name='appointments_toggle_link'),
    path('link/regenerate/', views.regenerate_link, name='appointments_regenerate_link'),
]
