"""WhatsApp wa.me deep-link helpers."""

from __future__ import annotations

from urllib.parse import quote

from hrms.models import OwnerHrmsSettings


def owner_whatsapp_number(owner) -> str:
    if owner is None:
        return ''
    row = OwnerHrmsSettings.objects.filter(owner=owner).first()
    if not row:
        return ''
    digits = ''.join(c for c in (row.whatsapp_number or '') if c.isdigit())
    if len(digits) == 10:
        return f'91{digits}'
    if len(digits) == 12 and digits.startswith('91'):
        return digits
    return ''


def build_wa_link(phone_e164: str, message: str) -> str | None:
    if not phone_e164:
        return None
    return f'https://wa.me/{phone_e164}?text={quote(message)}'


def punch_whatsapp_message(*, punch_label, attendance, employee) -> str:
    lines = [
        punch_label,
        f'Code: {attendance.punch_code_in if "In" in punch_label else attendance.punch_code_out}',
        f'Employee: {employee.name} ({employee.emp_code})',
        f'Mobile: {employee.mobile}',
        f'Date: {attendance.date}',
    ]
    if 'In' in punch_label and attendance.punch_in:
        lines.append(f'Time: {attendance.punch_in}')
        lines.append(f'Lat/Lng: {attendance.lat_in}, {attendance.long_in}')
    if 'Out' in punch_label and attendance.punch_out:
        lines.append(f'Time: {attendance.punch_out}')
        lines.append(f'Lat/Lng: {attendance.lat_out}, {attendance.long_out}')
        if attendance.working_hours is not None:
            lines.append(f'Working hours: {attendance.working_hours}')
    if attendance.project:
        lines.append(f'Project: {attendance.project}')
    if attendance.company_name:
        lines.append(f'Company: {attendance.company_name}')
    return '\n'.join(lines)


def punch_whatsapp_link(*, owner, punch_label, attendance, employee):
    phone = owner_whatsapp_number(owner)
    if not phone:
        return None, 'Owner WhatsApp number is not set; punch saved without alert.'
    msg = punch_whatsapp_message(
        punch_label=punch_label,
        attendance=attendance,
        employee=employee,
    )
    return build_wa_link(phone, msg), None
