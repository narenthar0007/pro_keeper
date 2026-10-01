"""Punch code encode / decode (15 chars)."""

from __future__ import annotations

import re
from datetime import datetime


def _digits(value, width):
    try:
        n = abs(int(float(value))) % (10**width)
    except (TypeError, ValueError):
        n = 0
    return str(n).zfill(width)


def _name_letters(name):
    letters = re.sub(r'[^A-Za-z]', '', name or '')[:3].upper()
    return letters.ljust(3, 'X')


def generate_punch_code(*, emp_code, name, lat, lng, when: datetime, punch_type: str) -> str:
    """
    15-char punch code:
    empId last 3 + name first 3 A-Z + lat%100 (2) + lng%100 (2) + day (2) + hour (2) + I/O
    """
    emp_part = re.sub(r'\D', '', str(emp_code or ''))[-3:].zfill(3)
    name_part = _name_letters(name)
    lat_part = _digits(lat, 2)
    lng_part = _digits(lng, 2)
    day_part = str(when.day).zfill(2)
    hour_part = str(when.hour).zfill(2)
    type_part = 'I' if str(punch_type).lower() in ('in', 'i') else 'O'
    code = f'{emp_part}{name_part}{lat_part}{lng_part}{day_part}{hour_part}{type_part}'
    return code[:15].ljust(15, '0')


def decode_punch_code(code: str) -> dict:
    code = (code or '').strip().upper()
    if len(code) != 15:
        raise ValueError('Punch code must be exactly 15 characters.')
    return {
        'emp_id_last3': code[0:3],
        'name_first3': code[3:6],
        'lat_mod100': code[6:8],
        'lng_mod100': code[8:10],
        'day_of_month': code[10:12],
        'hour': code[12:14],
        'type': 'In' if code[14] == 'I' else 'Out' if code[14] == 'O' else code[14],
        'raw': code,
    }
