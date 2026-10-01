"""
PropKeep UI components — single import surface for all builders.

Usage:
    from accounts.components import build_button, build_heading, build_table, ...
"""

from accounts.ui_components import (  # noqa: F401
    build_alert,
    build_alerts,
    build_badge,
    build_button,
    build_empty,
    build_field,
    build_filter,
    build_form,
    build_kpi,
    build_kpis,
    build_listing,
    build_listings,
    build_page_header,
    build_pagination,
    build_panel,
    build_popup,
    build_search,
    build_status_page,
    fields_from_django_form,
)
from accounts.ui_table import TableConfig, build_table, cell_value  # noqa: F401


def build_heading(
    text,
    *,
    level=1,
    tooltip='',
    hint='',
    class_name='',
    id='',
    tag='',
):
    """
    Heading with optional info tooltip for {% ui_heading %}.

    Args:
        text: Heading label
        level: 1–3 (h1/h2/h3) when tag not set
        tooltip: Shown on the small (i) icon hover/focus
        hint: Optional muted line under the heading
        class_name: Extra CSS classes
        id: Optional element id
        tag: Force tag name (h1|h2|h3|h4|p|span); default from level
    """
    level = int(level or 1)
    if level < 1:
        level = 1
    if level > 4:
        level = 4
    return {
        'text': text,
        'level': level,
        'tag': tag or f'h{level}',
        'tooltip': tooltip or '',
        'hint': hint or '',
        'class_name': class_name,
        'id': id,
    }


# Keep page header / panel / field tooltips aligned with heading helper
def with_tooltip(config, tooltip):
    """Attach a tooltip string onto any component config dict."""
    if isinstance(config, dict):
        config = {**config, 'tooltip': tooltip}
    return config


__all__ = [
    'TableConfig',
    'build_alert',
    'build_alerts',
    'build_badge',
    'build_button',
    'build_empty',
    'build_field',
    'build_filter',
    'build_form',
    'build_heading',
    'build_kpi',
    'build_kpis',
    'build_listing',
    'build_listings',
    'build_page_header',
    'build_pagination',
    'build_panel',
    'build_popup',
    'build_search',
    'build_status_page',
    'build_table',
    'cell_value',
    'fields_from_django_form',
    'with_tooltip',
]
