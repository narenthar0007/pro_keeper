# PropKeep

Django app for rental property owners and tenants: public listings, private rent/advance books, photos, enquiries, expenses, reports, and a simple REST API.

## Features

- Register / login
- Public browse with search, rent range, bedrooms, availability, sort
- Property photos, map, WhatsApp contact, enquiry form
- Owner dashboard: rent due this month, income/expense snapshot
- Tenants with advance paid / deducted / refunded + lease upload
- Rent payments with printable + PDF receipt
- Expenses, complaints, shared access (agent/co-owner)
- Tenant portal (link a user on the tenant form)
- Monthly income report
- REST API under `/api/`
- Email notifications to owner on enquiry (prints to console in dev)

## Setup

```bash
cd tenant
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional
python manage.py runserver
```

Open http://127.0.0.1:8000/

Demo tip: register two users — use one as owner, link the other on a tenant as **User** for the tenant portal.

## Useful URLs

| URL | Purpose |
|-----|---------|
| `/` | Public listings |
| `/dashboard/` | Owner dashboard |
| `/reports/` | Monthly income vs expenses |
| `/enquiries/` | Enquiry inbox |
| `/tenant-portal/` | Tenant view |
| `/accounts/staff/` | Staff admin panel (sidebar tables, privileges, theme) |
| `/api/properties/` | Public JSON API |
| `/api/my-properties/` | Owner API (auth) |
| `/admin/` | Django admin |

## Role-based header

The shared header in `templates/includes/app_header.html` appears on **all pages** (site + staff admin).

Nav items are built in `accounts/nav.py` via `get_nav_items(user)` and exposed by the context processor:

| Role | Typical header links |
|------|----------------------|
| Guest | Browse, Login, List property |
| Owner | Browse, Dashboard, Properties, Tenants, Reports, Enquiries, Settings, Quick Add |
| Tenant | Browse, My portal, Settings |
| Admin | Browse, Admin, Dashboard, Properties, Reports, Enquiries, Quick Add |

Privileges (on/off) are controlled in **Admin panel → Privileges**. New Settings page codes: `view_settings` (open the page) and `manage_rent_reminders` (set / receive rent pay or collect reminders).

## Multi-brand

Brands (e.g. **PropKeep**, **CheckPro Data**) share one admin panel. Each brand has its own name, tagline, footer, hostnames, base URL, colors (including **header** & **footer**), fonts, and table style.

- Admin → **Brands** — list / preview / set default / edit
- Admin → **Theme settings** — edit the active brand’s theme
- Switch by hostname (`checkpro.localhost`) or **Preview** (session)

## Reusable UI components

Import builders from one module: `accounts.components`. Render with `{% load ui %}`.  
Live gallery: Admin → **UI components**.

| Tag | Builder | Purpose |
|-----|---------|---------|
| `{% ui_heading %}` | `build_heading` | Heading + optional `(i)` tooltip |
| `{% ui_button %}` | `build_button` | Primary/secondary/danger buttons & links |
| `{% ui_kpi %}` / `{% ui_kpis %}` | `build_kpi` / `build_kpis` | Count / metric cards |
| `{% ui_search %}` | `build_search` | Search input |
| `{% ui_field %}` | `build_field` | Form fields (+ `tooltip=`) |
| `{% ui_filter %}` | `build_filter` | Filter / search bar (fields + submit) |
| `{% ui_popup %}` | `build_popup` | Modal dialog (open with `open_popup="id"`) |
| `{% ui_table %}` | `build_table` | Data table (column `tooltip=`) |
| `{% ui_page_header %}` | `build_page_header` | Title + subtitle + actions + tooltip |
| `{% ui_panel %}` | `build_panel` | Panel / card with optional body |
| `{% ui_badge %}` | `build_badge` | Status badges (occupied, paid, …) |
| `{% ui_empty %}` | `build_empty` | Empty-state text + optional CTA |
| `{% ui_pagination %}` | `build_pagination` | Table pagination / load more |
| `{% ui_alerts %}` | `build_alerts` | Flash messages (auto from `messages`) |
| `{% ui_listing %}` / `{% ui_listings %}` | `build_listing(s)` | Property / listing cards |
| `{% ui_form %}` | `build_form` | Form layout (or pass a Django `form=`) |

**Example (view):**

```python
from django.urls import reverse
from accounts.ui_components import (
    build_button, build_filter, build_kpis, build_popup, build_search,
)
from accounts.ui_table import build_table

kpis = build_kpis([
    {'label': 'Properties', 'value': 12},
    {'label': 'Unread', 'value': 3, 'tone': 'warn'},
])
filters = build_filter(
    [
        build_search(name='q', value=q, placeholder='Search...'),
        {'name': 'role', 'label': 'Role', 'type': 'select', 'value': role,
         'choices': [('', 'All'), ('owner', 'Owner')]},
    ],
    submit_label='Filter',
)
actions = [
    build_button('Create', href=reverse('staff_create_user'), variant='primary'),
    build_button('Help', variant='secondary', open_popup='help'),
]
help_popup = build_popup('help', title='Help', body='Short tip…', cancel_label='Close')
table = build_table(
    id='payments',
    columns=[
        {'key': 'month', 'label': 'Month', 'width': '120px'},
        {'key': 'amount', 'label': 'Amount', 'align': 'right'},
        {'key': 'status', 'label': 'Status', 'badge': True},
    ],
    rows=[{'month': 'Jul 2026', 'amount': '₹22,000', 'status': 'Paid'}],
    empty_text='No payments yet.',
)
```

**Example (template):**

```django
{% load ui %}
{% ui_kpis kpis %}
{% ui_filter filters %}
{% for btn in actions %}{% ui_button btn %}{% endfor %}
{% ui_popup help_popup %}
{% ui_table table %}
```

You can also pass simple kwargs in templates:

```django
{% ui_heading text="Users" level=1 tooltip="All Owner, Tenant, and Admin accounts" %}
{% ui_button label="Save" type="submit" variant="primary" %}
{% ui_kpi label="Total" value=42 %}
{% ui_field name="email" label="Email" type="email" value=email tooltip="Login email" %}
{% ui_page_header title="Users" subtitle="All accounts" tooltip="Shared across brands" %}
{% ui_badge label="Occupied" tone="occupied" %}
{% ui_empty text="No rows yet." action_label="Add one" action_href="/add/" %}
{% ui_form form=form title="Sign in" submit_label="Login" %}
{% ui_pagination paging=paging page=page filter_query=filter_query %}
{% ui_alerts %}
```


Popup open/close uses `static/js/ui.js` (`data-ui-open` / `data-ui-close`).

Table column options: `key`, `label`, `width`, `align`, `badge`, `html`.  
Table options: `empty_text`, `striped`, `compact`, `hover`, `sticky_header`, `caption`.  
(`{% load ui_table %}` still works for tables only.)

## Deploy notes (production)

1. Set `DEBUG = False`, a strong `SECRET_KEY`, and real `ALLOWED_HOSTS`
2. Use PostgreSQL instead of SQLite
3. Serve with Gunicorn/Uvicorn + Nginx
4. Set `EMAIL_BACKEND` to SMTP for real enquiry emails
5. Collect static files: `python manage.py collectstatic`
6. Hosts that work well for Django: Render, Railway, PythonAnywhere

This project ships with SQLite + console email for local learning.
