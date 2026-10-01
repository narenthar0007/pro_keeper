"""HTTP error and under-construction screens (shared UI kit)."""

from django.http import HttpResponse
from django.middleware.csrf import REASON_NO_CSRF_COOKIE, REASON_NO_REFERER
from django.shortcuts import render
from django.template import loader
from django.urls import reverse
from django.views.decorators.csrf import requires_csrf_token

from accounts.components import build_status_page


def _status_context(
    request,
    *,
    title,
    code='',
    subtitle='',
    hint='',
    level='info',
    empty_text='',
    extra_actions=None,
):
    home = reverse('public_listings')
    actions = [{'label': 'Go home', 'href': home, 'variant': 'primary'}]
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        actions.append({'label': 'Dashboard', 'href': reverse('dashboard'), 'variant': 'secondary'})
    else:
        actions.append({'label': 'Sign in', 'href': reverse('login'), 'variant': 'secondary'})
    actions.append({'label': 'Browse listings', 'href': home, 'variant': 'secondary'})
    if extra_actions:
        actions.extend(extra_actions)
    status = build_status_page(
        title,
        code=code,
        subtitle=subtitle,
        hint=hint,
        level=level,
        actions=actions,
        empty_text=empty_text or subtitle or title,
    )
    return {
        'status': status,
        'code': str(code or ''),
        'page_title': title,
    }


def page_not_found(request, exception=None):
    ctx = _status_context(
        request,
        title='Page not found',
        code='404',
        subtitle='That address is not in PropKeep.',
        hint='Check the URL, or go back to listings and the dashboard.',
        level='warn',
        empty_text='No page matches this URL.',
    )
    return render(request, 'accounts/status.html', ctx, status=404)


def permission_denied(request, exception=None):
    ctx = _status_context(
        request,
        title='Access denied',
        code='403',
        subtitle='You do not have permission to open this page.',
        hint='Ask an admin to grant the privilege, or sign in with a different account.',
        level='error',
        empty_text='This screen is blocked for your login.',
    )
    return render(request, 'accounts/status.html', ctx, status=403)


@requires_csrf_token
def server_error(request):
    """Standalone 500 page — must not depend on the database or theme processors."""
    template = loader.get_template('500.html')
    return HttpResponse(template.render({}, request), status=500)


def csrf_failure(request, reason=''):
    hint = (
        'Refresh this page and try again. This often happens if you logged out '
        'and back in while the form was still open.'
    )
    if reason in {REASON_NO_REFERER, REASON_NO_CSRF_COOKIE}:
        hint = 'Go back, refresh the page, and submit the form again.'
    ctx = _status_context(
        request,
        title='Form expired',
        code='403',
        subtitle='Security check failed, so the request was blocked.',
        hint=hint,
        level='error',
        empty_text='The form token is no longer valid.',
    )
    return render(request, 'accounts/status.html', ctx, status=403)


def under_construction(request):
    feature = (request.GET.get('feature') or '').strip()
    title = f'{feature} is under construction' if feature else 'Under construction'
    ctx = _status_context(
        request,
        title=title,
        subtitle='This part of PropKeep is still being built.',
        hint='Listings, rent, leads, and marketing are available now. Check back soon for this feature.',
        level='info',
        empty_text='Coming soon.',
    )
    return render(request, 'accounts/status.html', ctx)


def preview_error(request, code):
    """Visible in DEBUG so the designed error pages can be reviewed."""
    code = str(code or '').lower()
    if code == '404':
        return page_not_found(request)
    if code == '403':
        return permission_denied(request)
    if code in {'csrf', 'csrf_failure'}:
        return csrf_failure(request)
    if code == '500':
        ctx = _status_context(
            request,
            title='Something went wrong',
            code='500',
            subtitle='The server hit an unexpected error.',
            hint='Try again in a moment. If this keeps happening, contact support.',
            level='error',
            empty_text='We could not finish this request.',
        )
        return render(request, 'accounts/status.html', ctx, status=500)
    return page_not_found(request)
