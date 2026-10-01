"""Reusable table config helper for PropKeep pages."""

from __future__ import annotations

from django.utils.html import escape
from django.utils.safestring import mark_safe


class TableConfig:
    """
    Build a table config dict for {% ui_table %}.

    Example:
        table = TableConfig(
            id='payments',
            columns=[
                {'key': 'month', 'label': 'Month', 'width': '120px'},
                {'key': 'amount', 'label': 'Amount', 'align': 'right'},
                {'key': 'status', 'label': 'Status', 'badge': True},
            ],
            rows=[{'month': 'Jul 2026', 'amount': '₹22,000', 'status': 'Paid'}],
        ).as_dict()
    """

    def __init__(
        self,
        *,
        columns=None,
        rows=None,
        id='table',
        empty_text='No rows.',
        striped=True,
        compact=False,
        hover=True,
        sticky_header=False,
        caption='',
        headers=None,
    ):
        # Allow headers=['A','B'] + rows=[[1,2], ...] shorthand
        if headers is not None and columns is None:
            columns = headers
        if columns and isinstance(columns[0], str):
            columns = [{'key': f'c{i}', 'label': h} for i, h in enumerate(columns)]

        self.id = id
        self.columns = [self._normalize_column(c, i) for i, c in enumerate(columns or [])]
        self.rows = self._normalize_rows(rows or [])
        self.empty_text = empty_text
        self.striped = striped
        self.compact = compact
        self.hover = hover
        self.sticky_header = sticky_header
        self.caption = caption

    @staticmethod
    def _normalize_column(col, index):
        if isinstance(col, str):
            return {
                'key': f'c{index}',
                'label': col,
                'width': '',
                'align': 'left',
                'badge': False,
                'html': False,
            }
        return {
            'key': col.get('key', f'c{index}'),
            'label': col.get('label', col.get('key', f'Col {index + 1}')),
            'width': col.get('width', ''),
            'align': col.get('align', 'left'),
            'badge': bool(col.get('badge', False)),
            'html': bool(col.get('html', False)),
            'class': col.get('class', ''),
            'tooltip': col.get('tooltip', ''),
        }

    def _normalize_rows(self, rows):
        normalized = []
        keys = [c['key'] for c in self.columns]
        for row in rows:
            if isinstance(row, dict):
                normalized.append(row)
            else:
                # list / tuple in column order
                item = {}
                for i, key in enumerate(keys):
                    item[key] = row[i] if i < len(row) else ''
                normalized.append(item)
        return normalized

    def as_dict(self):
        return {
            'id': self.id,
            'columns': self.columns,
            'rows': self.rows,
            'empty_text': self.empty_text,
            'striped': self.striped,
            'compact': self.compact,
            'hover': self.hover,
            'sticky_header': self.sticky_header,
            'caption': self.caption,
        }


def build_table(columns=None, rows=None, headers=None, **kwargs):
    """Shortcut: build_table(headers=[...], rows=[[...], ...]) or columns+dict rows."""
    if headers is not None and columns is None:
        columns = headers
    return TableConfig(columns=columns, rows=rows, headers=None, **kwargs).as_dict()


def cell_value(row, column):
    value = row.get(column['key'], '')
    if value is None:
        value = ''
    if column.get('html'):
        return mark_safe(str(value))
    if column.get('badge'):
        text = escape(str(value))
        css = escape(str(value).lower().replace(' ', '-'))
        return mark_safe(f'<span class="badge {css}">{text}</span>')
    return escape(str(value))
