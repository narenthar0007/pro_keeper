from django.contrib.auth import views as auth_views
from django.urls import path

from . import admin_panel, status_pages, views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.RoleLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('settings/', views.user_settings, name='user_settings'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset.html',
            email_template_name='accounts/password_reset_email.html',
            success_url='/accounts/password-reset/done/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url='/accounts/reset/done/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    # Admin panel (staff / admin role only)
    path('staff/', admin_panel.staff_dashboard, name='staff_dashboard'),
    path('staff/broadcast/', admin_panel.staff_broadcast, name='staff_broadcast'),
    path('staff/users/', admin_panel.staff_users, name='staff_users'),
    path('staff/users/create/', admin_panel.staff_create_user, name='staff_create_user'),
    path('staff/users/<int:user_id>/', admin_panel.staff_user_detail, name='staff_user_detail'),
    path('staff/users/<int:user_id>/toggle/', admin_panel.staff_user_toggle, name='staff_user_toggle'),
    path(
        'staff/users/<int:user_id>/privileges/',
        admin_panel.staff_user_privilege_edit,
        name='staff_user_privilege_edit',
    ),
    path('staff/logs/', admin_panel.staff_activity_logs, name='staff_activity_logs'),
    path('staff/table/<str:table>/', admin_panel.staff_table, name='staff_table'),
    path('staff/privileges/', admin_panel.staff_privileges, name='staff_privileges'),
    path('staff/privileges/users/', admin_panel.staff_user_privileges, name='staff_user_privileges'),
    path('staff/brands/', admin_panel.staff_brands, name='staff_brands'),
    path('staff/brands/new/', admin_panel.staff_brand_create, name='staff_brand_create'),
    path('staff/brands/<int:brand_id>/', admin_panel.staff_brand_edit, name='staff_brand_edit'),
    path('staff/theme/', admin_panel.staff_theme, name='staff_theme'),
    path('staff/promotions/', admin_panel.staff_promotions, name='staff_promotions'),
    path('staff/promotions/new/', admin_panel.staff_promotion_create, name='staff_promotion_create'),
    path('staff/promotions/<int:promotion_id>/edit/', admin_panel.staff_promotion_edit, name='staff_promotion_edit'),
    path('staff/components/', admin_panel.staff_components, name='staff_components'),
    path('error/<str:code>/', status_pages.preview_error, name='error_preview'),
    path('page-not-found/', status_pages.page_not_found, name='page_not_found'),
    path('under-construction/', status_pages.under_construction, name='under_construction'),
]
