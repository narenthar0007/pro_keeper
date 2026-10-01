"""Reusable UI config helpers for PropKeep pages."""

from __future__ import annotations

from django.forms.widgets import (
    CheckboxInput,
    ClearableFileInput,
    DateInput,
    EmailInput,
    FileInput,
    HiddenInput,
    NumberInput,
    PasswordInput,
    Select,
    SelectMultiple,
    Textarea,
)


def build_button(
    label,
    *,
    href='',
    variant='primary',
    size='',
    type='button',
    name='',
    value='',
    disabled=False,
    full_width=False,
    class_name='',
    attrs='',
    open_popup='',
    id='',
):
    """Button / link config for {% ui_button %}."""
    return {
        'id': id,
        'label': label,
        'href': href,
        'variant': variant or 'primary',
        'size': size or '',
        'type': type or 'button',
        'name': name,
        'value': value,
        'disabled': bool(disabled),
        'full_width': bool(full_width),
        'class_name': class_name,
        'attrs': attrs,
        'open_popup': open_popup,
    }


def build_kpi(label, value, *, hint='', tone='', href='', id=''):
    """Single KPI / count card for {% ui_kpi %}."""
    return {
        'id': id,
        'label': label,
        'value': value,
        'hint': hint,
        'tone': tone,
        'href': href,
    }


def build_kpis(items):
    """List of KPI dicts for {% ui_kpis %}."""
    return [
        build_kpi(**item) if isinstance(item, dict) and 'label' in item else item
        for item in (items or [])
    ]


def build_field(
    name,
    *,
    label='',
    type='text',
    value='',
    placeholder='',
    choices=None,
    required=False,
    disabled=False,
    help_text='',
    tooltip='',
    id='',
    rows=3,
    min='',
    max='',
    step='',
    checked=None,
    span='',
    class_name='',
    attrs='',
    errors=None,
):
    """
    Form field config for {% ui_field %}.

    type: text | number | email | password | search | select | select-multiple | textarea | checkbox | date | file | hidden
    """
    normalized_choices = []
    for choice in choices or []:
        if isinstance(choice, dict):
            normalized_choices.append(
                {'value': choice.get('value', ''), 'label': choice.get('label', '')}
            )
        elif isinstance(choice, (list, tuple)) and len(choice) >= 2:
            normalized_choices.append({'value': choice[0], 'label': choice[1]})
        else:
            normalized_choices.append({'value': choice, 'label': str(choice)})

    field_id = id or name
    is_checked = checked if checked is not None else bool(value) if type == 'checkbox' else False

    return {
        'id': field_id,
        'name': name,
        'label': label,
        'type': type or 'text',
        'value': '' if value is None else value,
        'placeholder': placeholder,
        'choices': normalized_choices,
        'required': bool(required),
        'disabled': bool(disabled),
        'help_text': help_text,
        'rows': rows,
        'min': min,
        'max': max,
        'step': step,
        'checked': bool(is_checked),
        'span': str(span) if span else '',
        'class_name': class_name,
        'attrs': attrs,
        'errors': list(errors or []),
        'tooltip': tooltip or help_text or '',
    }


def build_search(
    name='q',
    *,
    value='',
    placeholder='Search...',
    label='Search',
    id='',
    span='',
):
    """Search input config (alias of build_field type=search)."""
    return build_field(
        name,
        label=label,
        type='search',
        value=value,
        placeholder=placeholder,
        id=id or name,
        span=span,
    )


def build_filter(
    fields=None,
    *,
    method='get',
    action='',
    submit_label='Filter',
    submit_variant='primary',
    aria_label='Filters',
    class_name='',
    id='',
    show_submit=True,
):
    """Filter / search bar config for {% ui_filter %}."""
    normalized = []
    for field in fields or []:
        if isinstance(field, dict) and 'name' in field:
            kwargs = {k: v for k, v in field.items() if k != 'name'}
            normalized.append(build_field(field['name'], **kwargs))
        else:
            normalized.append(field)

    return {
        'id': id,
        'method': method or 'get',
        'action': action,
        'aria_label': aria_label,
        'class_name': class_name,
        'fields': normalized,
        'show_submit': bool(show_submit),
        'submit': build_button(submit_label, variant=submit_variant, type='submit', full_width=True),
    }


def build_popup(
    id,
    *,
    title='',
    body='',
    body_html=False,
    size='md',
    confirm_label='',
    cancel_label='Close',
    confirm_href='',
    confirm_variant='primary',
    form_action='',
    form_method='post',
    include_csrf=True,
    open=False,
    footer_buttons=None,
):
    """Modal / popup config for {% ui_popup %}."""
    buttons = list(footer_buttons or [])
    if confirm_label:
        buttons.append(
            build_button(
                confirm_label,
                href=confirm_href,
                variant=confirm_variant,
                type='submit' if form_action and not confirm_href else 'button',
            )
        )
    if cancel_label:
        buttons.append(
            build_button(
                cancel_label,
                variant='secondary',
                type='button',
                attrs='data-ui-close',
            )
        )

    return {
        'id': id,
        'title': title,
        'body': body,
        'body_html': bool(body_html),
        'size': size or 'md',
        'open': bool(open),
        'form_action': form_action,
        'form_method': form_method,
        'include_csrf': bool(include_csrf),
        'footer_buttons': buttons,
    }


def build_badge(label, *, tone='', class_name=''):
    """Status badge for {% ui_badge %}."""
    tone_class = (tone or '').strip().lower().replace(' ', '-')
    return {
        'label': label,
        'tone': tone_class,
        'class_name': class_name,
    }


def build_empty(text='Nothing here yet.', *, action_label='', action_href='', action=None):
    """Empty-state message for {% ui_empty %}."""
    btn = action
    if btn is None and action_label:
        btn = build_button(action_label, href=action_href, variant='primary', size='sm')
    return {
        'text': text,
        'action': btn,
    }


def build_page_header(title, *, subtitle='', actions=None, level=1, tooltip=''):
    """Page / section header for {% ui_page_header %}."""
    normalized_actions = []
    for item in actions or []:
        if isinstance(item, dict) and 'label' in item:
            normalized_actions.append(build_button(item['label'], **{k: v for k, v in item.items() if k != 'label'}))
        else:
            normalized_actions.append(item)
    return {
        'title': title,
        'subtitle': subtitle,
        'actions': normalized_actions,
        'level': 1 if level == 1 else 2,
        'tooltip': tooltip or '',
    }


def build_panel(
    title='',
    *,
    meta='',
    actions=None,
    body='',
    body_html=False,
    empty=None,
    id='',
    class_name='',
    tooltip='',
):
    """Panel / card shell for {% ui_panel %}."""
    normalized_actions = []
    for item in actions or []:
        if isinstance(item, dict) and 'label' in item:
            normalized_actions.append(build_button(item['label'], **{k: v for k, v in item.items() if k != 'label'}))
        else:
            normalized_actions.append(item)
    empty_cfg = empty
    if isinstance(empty, str):
        empty_cfg = build_empty(empty)
    return {
        'id': id,
        'title': title,
        'meta': meta,
        'actions': normalized_actions,
        'body': body,
        'body_html': bool(body_html),
        'empty': empty_cfg,
        'class_name': class_name,
        'tooltip': tooltip or '',
    }


def build_alert(text, *, level='info', id=''):
    """Single alert for {% ui_alert %}."""
    return {
        'id': id,
        'text': text,
        'level': level or 'info',
    }


def build_alerts(items=None):
    """List of alerts for {% ui_alerts %}."""
    result = []
    for item in items or []:
        if isinstance(item, dict):
            result.append(build_alert(item.get('text', ''), level=item.get('level', 'info'), id=item.get('id', '')))
        else:
            # Django message object
            level = getattr(item, 'tags', None) or getattr(item, 'level_tag', 'info') or 'info'
            result.append(build_alert(str(item), level=str(level).split()[0] if level else 'info'))
    return result


def build_listing(
    title,
    *,
    href='',
    meta='',
    price='',
    price_suffix='',
    badges=None,
    image_url='',
    actions=None,
    lines=None,
    id='',
    class_name='',
):
    """Listing / property card for {% ui_listing %}."""
    badge_list = []
    for badge in badges or []:
        if isinstance(badge, dict) and 'label' in badge:
            badge_list.append(build_badge(badge['label'], tone=badge.get('tone', ''), class_name=badge.get('class_name', '')))
        else:
            badge_list.append(badge)

    action_list = []
    for item in actions or []:
        if isinstance(item, dict) and 'label' in item:
            action_list.append(build_button(item['label'], **{k: v for k, v in item.items() if k != 'label'}))
        else:
            action_list.append(item)

    return {
        'id': id,
        'title': title,
        'href': href,
        'meta': meta,
        'price': price,
        'price_suffix': price_suffix,
        'badges': badge_list,
        'image_url': image_url,
        'actions': action_list,
        'lines': list(lines or []),
        'class_name': class_name,
        'is_photo': bool(image_url),
    }


def build_listings(items):
    """List of listing cards for {% ui_listings %}."""
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            result.append(item)
            continue
        # Already normalized by build_listing()
        if 'is_photo' in item and 'badges' in item:
            result.append(item)
            continue
        if 'title' in item:
            result.append(
                build_listing(
                    item['title'],
                    href=item.get('href', ''),
                    meta=item.get('meta', ''),
                    price=item.get('price', ''),
                    price_suffix=item.get('price_suffix', ''),
                    badges=item.get('badges'),
                    image_url=item.get('image_url', ''),
                    actions=item.get('actions'),
                    lines=item.get('lines'),
                    id=item.get('id', ''),
                    class_name=item.get('class_name', ''),
                )
            )
        else:
            result.append(item)
    return result


def build_pagination(paging=None, page=None, filter_query=''):
    """Pagination config for {% ui_pagination %}."""
    if not paging or not paging.get('total'):
        return {
            'show': False,
            'paging': paging or {},
            'page': page,
            'filter_query': filter_query or '',
            'pages': [],
        }

    page_obj = page or paging.get('page')
    pages = []
    if page_obj and page_obj.paginator.num_pages > 1:
        num_pages = page_obj.paginator.num_pages
        current = page_obj.number
        for num in page_obj.paginator.page_range:
            near = abs(num - current) <= 2
            edge = num in (1, num_pages)
            if num_pages <= 9 or near or edge:
                pages.append({'type': 'page', 'num': num, 'active': num == current})
            elif pages and pages[-1]['type'] != 'ellipsis':
                if num in (current - 3, current + 3):
                    pages.append({'type': 'ellipsis'})

    return {
        'show': True,
        'paging': paging,
        'page': page_obj,
        'filter_query': filter_query or '',
        'pages': pages,
        'has_multiple_pages': bool(page_obj and page_obj.paginator.num_pages > 1),
    }


def _widget_type(widget):
    if isinstance(widget, CheckboxInput):
        return 'checkbox'
    if isinstance(widget, Textarea):
        return 'textarea'
    if isinstance(widget, SelectMultiple):
        return 'select-multiple'
    if isinstance(widget, Select):
        return 'select'
    if isinstance(widget, (FileInput, ClearableFileInput)):
        return 'file'
    if isinstance(widget, NumberInput):
        return 'number'
    if isinstance(widget, EmailInput):
        return 'email'
    if isinstance(widget, PasswordInput):
        return 'password'
    if isinstance(widget, DateInput):
        return 'date'
    if isinstance(widget, HiddenInput):
        return 'hidden'
    input_type = getattr(widget, 'input_type', None)
    return input_type or 'text'


def fields_from_django_form(form):
    """Convert a Django form into ui_field configs."""
    fields = []
    for name, bound in form.fields.items():
        bf = form[name]
        widget = bound.widget
        ftype = _widget_type(widget)
        choices = None
        if ftype in {'select', 'select-multiple'}:
            choices = list(bound.choices)
        value = bf.value()
        if ftype == 'file':
            value = ''
        elif ftype == 'select-multiple':
            value = list(value or [])
        elif value is None:
            value = ''
        fields.append(
            build_field(
                name,
                label=str(bound.label or name),
                type=ftype,
                value=value,
                placeholder=bound.widget.attrs.get('placeholder', ''),
                choices=choices,
                required=bound.required,
                disabled=bound.disabled,
                help_text=str(bound.help_text or ''),
                id=bf.id_for_label or name,
                errors=[str(e) for e in bf.errors],
                checked=bool(value) if ftype == 'checkbox' else None,
                min=widget.attrs.get('min', ''),
                max=widget.attrs.get('max', ''),
                step=widget.attrs.get('step', ''),
            )
        )
    return fields


def build_form(
    fields=None,
    *,
    django_form=None,
    method='post',
    action='',
    submit_label='Save',
    cancel_label='Cancel',
    cancel_href='',
    title='',
    subtitle='',
    kicker='',
    include_csrf=True,
    class_name='form-card',
    id='',
    footer_html='',
):
    """
    Form layout config for {% ui_form %}.

    Pass django_form=MyForm(...) to auto-map fields, or pass fields=[build_field(...), ...].
    """
    form_errors = []
    mapped = list(fields or [])
    enctype = ''
    if django_form is not None:
        mapped = fields_from_django_form(django_form)
        form_errors = [str(e) for e in django_form.non_field_errors()]
        if getattr(django_form, 'is_multipart', lambda: False)():
            enctype = 'multipart/form-data'

    actions = [build_button(submit_label, variant='primary', type='submit')]
    if cancel_href:
        actions.append(build_button(cancel_label, href=cancel_href, variant='secondary'))

    return {
        'id': id,
        'method': method or 'post',
        'action': action,
        'include_csrf': bool(include_csrf),
        'title': title,
        'subtitle': subtitle,
        'kicker': kicker,
        'fields': mapped,
        'errors': form_errors,
        'actions': actions,
        'class_name': class_name,
        'footer_html': footer_html,
        'enctype': enctype,
    }


def build_status_page(
    title,
    *,
    code='',
    subtitle='',
    hint='',
    level='info',
    actions=None,
    empty_text='',
):
    """Shared config for error / under-construction screens."""
    buttons = []
    for item in actions or []:
        if isinstance(item, dict) and 'label' in item:
            buttons.append(build_button(item['label'], **{k: v for k, v in item.items() if k != 'label'}))
        else:
            buttons.append(item)
    primary = buttons[0] if buttons else None
    return {
        'code': str(code or ''),
        'title': title,
        'subtitle': subtitle,
        'hint': hint,
        'level': level or 'info',
        'header': build_page_header(title, subtitle=subtitle, tooltip=hint or subtitle),
        'alert': build_alert(hint, level=level) if hint else None,
        'empty': build_empty(empty_text or subtitle or title),
        'actions': buttons,
        'kpis': build_kpis(
            [
                {
                    'label': 'Status',
                    'value': code or 'Soon',
                    'tone': 'warn' if str(code) in ('403', '404', '500') else '',
                    'hint': 'HTTP status when this is an error page',
                }
            ]
        ),
        'primary': primary,
    }
