from django.urls import path

from . import mobile_api as api

urlpatterns = [
    path('auth/login/', api.login_view),
    path('auth/logout/', api.logout_view),
    path('auth/me/', api.me_view),
    path('options/', api.options_view),
    path('listings/', api.listings_view),
    path('listings/<int:pk>/', api.listing_detail_view),
    path('dashboard/', api.dashboard_view),
    path('properties/', api.properties_view),
    path('properties/<int:pk>/', api.property_detail_view),
    path('properties/<int:pk>/vacate/', api.property_vacate_view),
    path('tenants/', api.tenants_view),
    path('tenants/<int:pk>/', api.tenant_detail_view),
    path('tenants/<int:pk>/login/', api.tenant_login_view),
    path('join-requests/<int:pk>/', api.join_request_review_view),
    path('payments/', api.payments_view),
    path('expenses/', api.expenses_view),
    path('inbox/', api.inbox_view),
    path('rent-reminder/', api.rent_reminder_view),
    path('tenant-portal/', api.tenant_portal_view),
    path('enquiries/', api.enquiries_view),
    path('buildings/', api.buildings_view),
    path('broadcast/', api.broadcast_view),
]
