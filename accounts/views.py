from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import RegisterForm, RentReminderSettingsForm, RoleLoginForm
from .logging_utils import log_activity
from .models import UserProfile
from .privileges import get_user_role, has_privilege, home_for_user, privilege_required
from .brand_scoping import get_request_brand
from .reminders import reminder_due_date, reminder_window_start


def register(request):
    if request.user.is_authenticated:
        return redirect(home_for_user(request.user))

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(brand=get_request_brand(request))
            login(request, user)
            log_activity(
                request=request,
                user=user,
                action='register',
                message=f'New owner registered: {user.username}',
            )
            messages.success(request, 'Account created as Owner. Welcome!')
            return redirect(home_for_user(user))
    else:
        form = RegisterForm()

    from django.urls import reverse
    from django.utils.safestring import mark_safe

    return render(
        request,
        'accounts/register.html',
        {
            'form': form,
            'register_footer': mark_safe(
                f'<p class="meta" style="margin-top:1.1rem">Already have an account? '
                f'<a href="{reverse("login")}">Login</a></p>'
            ),
        },
    )


class RoleLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = RoleLoginForm

    def get_context_data(self, **kwargs):
        from django.urls import reverse
        from django.utils.safestring import mark_safe

        context = super().get_context_data(**kwargs)
        register_url = reverse('register')
        context['login_footer'] = mark_safe(
            f'<p class="meta" style="margin-top:1.1rem">New owner? '
            f'<a href="{register_url}">Self-register as Owner</a>'
            f' · <a href="{reverse("password_reset")}">Forgot password</a></p>'
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        hint = form.cleaned_data.get('role_hint')
        role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
        if hint and role and hint != role and not self.request.user.is_staff:
            messages.warning(
                self.request,
                f'You selected {dict(UserProfile.ROLE_CHOICES).get(hint)}, '
                f'but this account is a {self.request.user.profile.get_role_display()}.',
            )
        return response

    def get_success_url(self):
        from django.urls import reverse

        return reverse(home_for_user(self.request.user))


def _can_use_settings(user):
    role = get_user_role(user)
    return role in (UserProfile.ROLE_OWNER, UserProfile.ROLE_TENANT) and has_privilege(
        user, 'view_settings'
    )


@login_required
@privilege_required('view_settings')
def user_settings(request):
    if not _can_use_settings(request.user):
        messages.error(request, 'Settings are available for owner and tenant accounts.')
        return redirect(home_for_user(request.user))

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'role': UserProfile.ROLE_OWNER},
    )
    role = get_user_role(request.user)
    can_manage_reminders = has_privilege(request.user, 'manage_rent_reminders')
    if request.method == 'POST':
        if not can_manage_reminders:
            messages.error(request, 'You do not have permission to change rent reminders.')
            return redirect('user_settings')
        form = RentReminderSettingsForm(request.POST, request.FILES, instance=profile, role=role)
        if form.is_valid():
            form.save()
            log_activity(
                request=request,
                user=request.user,
                action='update',
                message='Updated rent reminder settings',
            )
            messages.success(request, 'Reminder settings saved.')
            return redirect('user_settings')
    else:
        form = RentReminderSettingsForm(instance=profile, role=role)
    if not can_manage_reminders:
        for field in form.fields.values():
            field.disabled = True

    from django.utils import timezone

    today = timezone.localdate()
    due = reminder_due_date(today, profile.rent_due_day)
    start = reminder_window_start(due, profile.reminder_days_before)
    reminder_kind = 'pay rent' if role == UserProfile.ROLE_TENANT else 'collect rent'
    has_email = bool((request.user.email or '').strip())

    from accounts.ui_components import build_page_header
    from django.urls import reverse

    return render(
        request,
        'accounts/settings.html',
        {
            'form': form,
            'page_header': build_page_header(
                'Settings',
                subtitle=f'Set a reminder to {reminder_kind}.',
                tooltip='Owner reminders are for collecting rent. Tenant reminders are for paying rent.',
            ),
            'cancel_href': reverse(home_for_user(request.user)),
            'reminder_kind': reminder_kind,
            'next_due_date': due,
            'next_reminder_date': start,
            'has_email': has_email,
            'settings_role': role,
            'can_manage_reminders': can_manage_reminders,
        },
    )

