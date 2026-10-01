from django import template

from accounts.ui_table import TableConfig, cell_value

register = template.Library()


@register.inclusion_tag('includes/ui_table.html')
def ui_table(table):
    """
    Render a configured table.

    Usage:
        {% load ui_table %}
        {% ui_table my_table %}
    """
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
                    'html': True,  # already escaped / marked safe in cell_value
                }
            )
        prepared_rows.append(cells)

    return {
        'table': config,
        'prepared_rows': prepared_rows,
    }
