"""PropKeep UI inclusion tags: button, kpi, search, filter, field, popup, table."""

from django import template

from accounts.components import (
    TableConfig,
    build_alert,
    build_alerts,
    build_badge,
    build_button,
    build_empty,
    build_field,
    build_filter,
    build_form,
    build_heading,
    build_kpi,
    build_kpis,
    build_listing,
    build_listings,
    build_page_header,
    build_pagination,
    build_panel,
    build_popup,
    build_search,
    cell_value,
)

register = template.Library()


def _button_from(config=None, **kwargs):
    if isinstance(config, dict):
        data = {**kwargs, **config}
        label = data.pop('label', 'Button')
        return build_button(label, **{
            k: data.get(k, default)
            for k, default in (
                ('href', ''),
                ('variant', 'primary'),
                ('size', ''),
                ('type', 'button'),
                ('name', ''),
                ('value', ''),
                ('disabled', False),
                ('full_width', False),
                ('class_name', ''),
                ('attrs', ''),
                ('open_popup', ''),
                ('id', ''),
            )
        })
    label = kwargs.pop('label', None)
    if label is None and config is not None:
        label = str(config)
    return build_button(label or 'Button', **kwargs)


@register.inclusion_tag('includes/ui_button.html')
def ui_button(
    config=None,
    label='',
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
    """
    {% ui_button label="Save" variant="primary" type="submit" %}
    {% ui_button btn_config %}
    {% ui_button label="Help" open_popup="help-modal" %}
    """
    if isinstance(config, dict):
        button = _button_from(config)
    elif config is not None and not label:
        button = build_button(
            str(config),
            href=href,
            variant=variant,
            size=size,
            type=type,
            name=name,
            value=value,
            disabled=disabled,
            full_width=full_width,
            class_name=class_name,
            attrs=attrs,
            open_popup=open_popup,
            id=id,
        )
    else:
        button = build_button(
            label or 'Button',
            href=href,
            variant=variant,
            size=size,
            type=type,
            name=name,
            value=value,
            disabled=disabled,
            full_width=full_width,
            class_name=class_name,
            attrs=attrs,
            open_popup=open_popup,
            id=id,
        )
    return {'button': button}


@register.inclusion_tag('includes/ui_kpi.html')
def ui_kpi(config=None, label='', value='', hint='', tone='', href='', id=''):
    if isinstance(config, dict):
        kpi = build_kpi(
            config.get('label', label),
            config.get('value', value),
            hint=config.get('hint', hint),
            tone=config.get('tone', tone),
            href=config.get('href', href),
            id=config.get('id', id),
        )
    else:
        kpi = build_kpi(label or str(config or ''), value, hint=hint, tone=tone, href=href, id=id)
    return {'kpi': kpi}


@register.inclusion_tag('includes/ui_kpis.html')
def ui_kpis(items):
    return {'kpis': build_kpis(items or [])}


@register.inclusion_tag('includes/ui_field.html')
def ui_field(
    config=None,
    name='',
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
):
    if isinstance(config, dict):
        field_name = config.get('name', name or 'field')
        kwargs = {k: v for k, v in config.items() if k != 'name'}
        field = build_field(field_name, **kwargs)
    else:
        field = build_field(
            name or (str(config) if config else 'field'),
            label=label,
            type=type,
            value=value,
            placeholder=placeholder,
            choices=choices,
            required=required,
            disabled=disabled,
            help_text=help_text,
            tooltip=tooltip,
            id=id,
            rows=rows,
            min=min,
            max=max,
            step=step,
            checked=checked,
            span=span,
            class_name=class_name,
            attrs=attrs,
        )
    return {'field': field}


@register.inclusion_tag('includes/ui_search.html')
def ui_search(
    config=None,
    name='q',
    value='',
    placeholder='Search...',
    label='Search',
    id='',
    span='',
):
    if isinstance(config, dict):
        field = build_search(
            name=config.get('name', name),
            value=config.get('value', value),
            placeholder=config.get('placeholder', placeholder),
            label=config.get('label', label),
            id=config.get('id', id),
            span=config.get('span', span),
        )
    else:
        field = build_search(
            name=name,
            value=value,
            placeholder=placeholder,
            label=label,
            id=id,
            span=span,
        )
    return {'field': field}


@register.inclusion_tag('includes/ui_filter.html')
def ui_filter(
    config=None,
    fields=None,
    method='get',
    action='',
    submit_label='Filter',
    submit_variant='primary',
    aria_label='Filters',
    class_name='',
    id='',
    show_submit=True,
):
    if isinstance(config, dict) and ('fields' in config or 'method' in config or 'submit_label' in config):
        filt = build_filter(
            config.get('fields') or fields,
            method=config.get('method', method),
            action=config.get('action', action),
            submit_label=config.get('submit_label', submit_label),
            submit_variant=config.get('submit_variant', submit_variant),
            aria_label=config.get('aria_label', aria_label),
            class_name=config.get('class_name', class_name),
            id=config.get('id', id),
            show_submit=config.get('show_submit', show_submit),
        )
    elif isinstance(config, list):
        filt = build_filter(
            config,
            method=method,
            action=action,
            submit_label=submit_label,
            submit_variant=submit_variant,
            aria_label=aria_label,
            class_name=class_name,
            id=id,
            show_submit=show_submit,
        )
    else:
        filt = build_filter(
            fields or [],
            method=method,
            action=action,
            submit_label=submit_label,
            submit_variant=submit_variant,
            aria_label=aria_label,
            class_name=class_name,
            id=id,
            show_submit=show_submit,
        )
    return {'filter': filt}


@register.inclusion_tag('includes/ui_popup.html')
def ui_popup(
    config=None,
    id='',
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
    if isinstance(config, dict):
        popup = build_popup(
            config.get('id', id or 'popup'),
            title=config.get('title', title),
            body=config.get('body', body),
            body_html=config.get('body_html', body_html),
            size=config.get('size', size),
            confirm_label=config.get('confirm_label', confirm_label),
            cancel_label=config.get('cancel_label', cancel_label),
            confirm_href=config.get('confirm_href', confirm_href),
            confirm_variant=config.get('confirm_variant', confirm_variant),
            form_action=config.get('form_action', form_action),
            form_method=config.get('form_method', form_method),
            include_csrf=config.get('include_csrf', include_csrf),
            open=config.get('open', open),
            footer_buttons=config.get('footer_buttons', footer_buttons),
        )
    else:
        popup = build_popup(
            id or 'popup',
            title=title,
            body=body,
            body_html=body_html,
            size=size,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            confirm_href=confirm_href,
            confirm_variant=confirm_variant,
            form_action=form_action,
            form_method=form_method,
            include_csrf=include_csrf,
            open=open,
            footer_buttons=footer_buttons,
        )
    return {'popup': popup}


@register.inclusion_tag('includes/ui_table.html')
def ui_table(table):
    """Available via {% load ui %} (same as {% load ui_table %})."""
    if isinstance(table, TableConfig):
        config = table.as_dict()
    elif isinstance(table, dict):
        config = TableConfig(
            id=table.get('id', 'table'),
            columns=table.get('columns') or table.get('headers') or [],
            rows=table.get('rows') or [],
            empty_text=table.get('empty_text', 'No rows.'),
            striped=table.get('striped', True),
            compact=table.get('compact', False),
            hover=table.get('hover', True),
            sticky_header=table.get('sticky_header', False),
            caption=table.get('caption', ''),
        ).as_dict()
    else:
        config = TableConfig(columns=[], rows=[]).as_dict()

    prepared_rows = []
    for row in config['rows']:
        cells = []
        for col in config['columns']:
            cells.append(
                {
                    'value': cell_value(row, col),
                    'align': col.get('align') or 'left',
                    'width': col.get('width') or '',
                    'class': col.get('class') or '',
                    'html': True,
                }
            )
        prepared_rows.append(cells)

    return {
        'table': config,
        'prepared_rows': prepared_rows,
    }


@register.inclusion_tag('includes/ui_badge.html')
def ui_badge(config=None, label='', tone='', class_name=''):
    if isinstance(config, dict):
        badge = build_badge(
            config.get('label', label),
            tone=config.get('tone', tone),
            class_name=config.get('class_name', class_name),
        )
    else:
        badge = build_badge(label or str(config or ''), tone=tone, class_name=class_name)
    return {'badge': badge}


@register.inclusion_tag('includes/ui_empty.html')
def ui_empty(config=None, text='Nothing here yet.', action_label='', action_href=''):
    if isinstance(config, dict):
        empty = build_empty(
            config.get('text', text),
            action_label=config.get('action_label', action_label),
            action_href=config.get('action_href', action_href),
            action=config.get('action'),
        )
    else:
        empty = build_empty(text if config is None else str(config), action_label=action_label, action_href=action_href)
    return {'empty': empty}


@register.inclusion_tag('includes/ui_heading.html')
def ui_heading(config=None, text='', level=1, tooltip='', hint='', class_name='', id='', tag=''):
    """
    {% ui_heading text="Users" level=1 tooltip="All accounts in the system" %}
    {% ui_heading heading_config %}
    """
    if isinstance(config, dict):
        heading = build_heading(
            config.get('text', text),
            level=config.get('level', level),
            tooltip=config.get('tooltip', tooltip),
            hint=config.get('hint', hint),
            class_name=config.get('class_name', class_name),
            id=config.get('id', id),
            tag=config.get('tag', tag),
        )
    else:
        heading = build_heading(
            text or (str(config) if config is not None else ''),
            level=level,
            tooltip=tooltip,
            hint=hint,
            class_name=class_name,
            id=id,
            tag=tag,
        )
    return {'heading': heading}


@register.inclusion_tag('includes/ui_tip.html')
def ui_tip(tip=''):
    return {'tip': tip}


@register.inclusion_tag('includes/ui_page_header.html')
def ui_page_header(config=None, title='', subtitle='', actions=None, level=1, tooltip=''):
    if isinstance(config, dict):
        header = build_page_header(
            config.get('title', title),
            subtitle=config.get('subtitle', subtitle),
            actions=config.get('actions', actions),
            level=config.get('level', level),
            tooltip=config.get('tooltip', tooltip),
        )
    else:
        header = build_page_header(
            title or str(config or ''),
            subtitle=subtitle,
            actions=actions,
            level=level,
            tooltip=tooltip,
        )
    return {'header': header}


@register.inclusion_tag('includes/ui_panel.html')
def ui_panel(
    config=None,
    title='',
    meta='',
    actions=None,
    body='',
    body_html=False,
    empty=None,
    id='',
    class_name='',
    tooltip='',
):
    if isinstance(config, dict):
        panel = build_panel(
            config.get('title', title),
            meta=config.get('meta', meta),
            actions=config.get('actions', actions),
            body=config.get('body', body),
            body_html=config.get('body_html', body_html),
            empty=config.get('empty', empty),
            id=config.get('id', id),
            class_name=config.get('class_name', class_name),
            tooltip=config.get('tooltip', tooltip),
        )
    else:
        panel = build_panel(
            title or str(config or ''),
            meta=meta,
            actions=actions,
            body=body,
            body_html=body_html,
            empty=empty,
            id=id,
            class_name=class_name,
            tooltip=tooltip,
        )
    return {'panel': panel}


@register.inclusion_tag('includes/ui_alert.html')
def ui_alert(config=None, text='', level='info', id=''):
    if isinstance(config, dict):
        alert = build_alert(config.get('text', text), level=config.get('level', level), id=config.get('id', id))
    else:
        alert = build_alert(text or str(config or ''), level=level, id=id)
    return {'alert': alert}


@register.inclusion_tag('includes/ui_alerts.html', takes_context=True)
def ui_alerts(context, items=None):
    if items is None:
        items = context.get('messages')
    return {'alerts': build_alerts(items)}


@register.inclusion_tag('includes/ui_listing.html')
def ui_listing(config=None, **kwargs):
    if isinstance(config, dict):
        listing = build_listing(**{**kwargs, **config})
    else:
        listing = build_listing(kwargs.get('title') or str(config or 'Listing'), **{k: v for k, v in kwargs.items() if k != 'title'})
    return {'listing': listing}


@register.inclusion_tag('includes/ui_listings.html')
def ui_listings(items=None, empty=None, empty_text=''):
    listings = build_listings(items or [])
    empty_cfg = empty
    if empty_cfg is None and empty_text:
        empty_cfg = build_empty(empty_text)
    elif isinstance(empty_cfg, str):
        empty_cfg = build_empty(empty_cfg)
    return {'listings': listings, 'empty': empty_cfg}


@register.inclusion_tag('includes/ui_pagination.html')
def ui_pagination(paging=None, page=None, filter_query=''):
    return {
        'pagination': build_pagination(paging=paging, page=page, filter_query=filter_query),
    }


@register.inclusion_tag('includes/ui_form.html')
def ui_form(
    config=None,
    form=None,
    fields=None,
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
    {% ui_form form=form title="Sign in" submit_label="Login" %}
    {% ui_form login_form %}
    """
    if isinstance(config, dict) and ('fields' in config or 'django_form' in config or 'title' in config):
        form_cfg = build_form(
            config.get('fields', fields),
            django_form=config.get('django_form', form),
            method=config.get('method', method),
            action=config.get('action', action),
            submit_label=config.get('submit_label', submit_label),
            cancel_label=config.get('cancel_label', cancel_label),
            cancel_href=config.get('cancel_href', cancel_href),
            title=config.get('title', title),
            subtitle=config.get('subtitle', subtitle),
            kicker=config.get('kicker', kicker),
            include_csrf=config.get('include_csrf', include_csrf),
            class_name=config.get('class_name', class_name),
            id=config.get('id', id),
            footer_html=config.get('footer_html', footer_html),
        )
    else:
        django_form = form if form is not None else (config if hasattr(config, 'fields') else None)
        form_cfg = build_form(
            fields,
            django_form=django_form,
            method=method,
            action=action,
            submit_label=submit_label,
            cancel_label=cancel_label,
            cancel_href=cancel_href,
            title=title,
            subtitle=subtitle,
            kicker=kicker,
            include_csrf=include_csrf,
            class_name=class_name,
            id=id,
            footer_html=footer_html,
        )
    return {'form': form_cfg}
