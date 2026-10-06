"""
Django settings for Property Manager.

Local defaults work with SQLite. Production reads env vars
(SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL, etc.).
"""

import os
from pathlib import Path

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(key, default=None):
    return os.environ.get(key, default)


def _env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_list(key, default=None):
    raw = os.environ.get(key)
    if not raw:
        return list(default or [])
    return [part.strip() for part in raw.split(',') if part.strip()]


SECRET_KEY = _env(
    'SECRET_KEY',
    'django-insecure-pb%rod5y@j=@tzbj!twxj4s5c0h#5-m5c4j=t2m+6)u@jrnvj*',
)

DEBUG = _env_bool('DEBUG', True)

ALLOWED_HOSTS = _env_list(
    'ALLOWED_HOSTS',
    [
        '127.0.0.1',
        'localhost',
        'testserver',
        'checkpro.localhost',
        'checkpro.local',
        'propkeep.localhost',
        '*',
    ],
)

CSRF_TRUSTED_ORIGINS = _env_list(
    'CSRF_TRUSTED_ORIGINS',
    [
        'http://127.0.0.1:8000',
        'http://localhost:8000',
        'http://checkpro.localhost:8000',
        'http://propkeep.localhost:8000',
    ],
)

CSRF_FAILURE_VIEW = 'accounts.csrf.csrf_failure'

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'unfold.contrib.inlines',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'accounts.apps.AccountsConfig',
    'properties',
    'hrms.apps.HrmsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.BrandMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.ActivityLogMiddleware',
    'accounts.middleware.RentReminderMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.site_theme_and_role',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database: SQLite locally; Postgres in production via DATABASE_URL
DATABASE_URL = _env('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=_env_bool('DB_SSL_REQUIRE', not DEBUG),
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
if DEBUG:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
        },
    }

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'public_listings'

EMAIL_BACKEND = _env(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL', 'PropKeep <noreply@propkeep.local>')
EMAIL_HOST = _env('EMAIL_HOST', '')
EMAIL_PORT = int(_env('EMAIL_PORT', '587') or 587)
EMAIL_HOST_USER = _env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = _env('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', True)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# HTTPS / proxy (Render, Railway, etc.)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', True)

# django-unfold — enterprise Django admin (does not replace ModelAdmin permissions)
UNFOLD = {
    'SITE_TITLE': 'PropKeep Admin',
    'SITE_HEADER': 'PropKeep',
    'SITE_SUBHEADER': 'Property operations console',
    'SITE_URL': reverse_lazy('public_listings'),
    'SITE_SYMBOL': 'apartment',
    'SHOW_HISTORY': True,
    'SHOW_VIEW_ON_SITE': True,
    'SHOW_BACK_BUTTON': True,
    'ENVIRONMENT': 'accounts.unfold_dashboard.environment_callback',
    'GLOBAL_CALLBACK': 'accounts.unfold_globals.global_callback',
    'DASHBOARD_CALLBACK': 'accounts.unfold_dashboard.dashboard_callback',
    'BORDER_RADIUS': '8px',
    'COLORS': {
        'primary': {
            '50': 'oklch(98.4% 0.014 180.72)',
            '100': 'oklch(95.3% 0.051 180.801)',
            '200': 'oklch(91% 0.096 180.426)',
            '300': 'oklch(85.5% 0.138 181.071)',
            '400': 'oklch(77.7% 0.152 181.912)',
            '500': 'oklch(70.4% 0.14 182.503)',
            '600': 'oklch(60% 0.118 184.704)',
            '700': 'oklch(51.1% 0.096 186.391)',
            '800': 'oklch(43.7% 0.078 188.216)',
            '900': 'oklch(38.6% 0.063 188.416)',
            '950': 'oklch(27.7% 0.046 192.524)',
        },
        'font': {
            'subtle-light': 'var(--color-base-500)',
            'subtle-dark': 'var(--color-base-400)',
            'default-light': 'var(--color-base-600)',
            'default-dark': 'var(--color-base-300)',
            'important-light': 'var(--color-base-900)',
            'important-dark': 'var(--color-base-100)',
        },
    },
    'SITE_DROPDOWN': [
        {
            'icon': 'home',
            'title': _('Open PropKeep'),
            'link': reverse_lazy('public_listings'),
        },
        {
            'icon': 'admin_panel_settings',
            'title': _('Staff console'),
            'link': reverse_lazy('staff_dashboard'),
        },
    ],
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': _('Overview'),
                'separator': True,
                'collapsible': False,
                'items': [
                    {
                        'title': _('Dashboard'),
                        'icon': 'dashboard',
                        'link': reverse_lazy('admin:index'),
                    },
                ],
            },
            {
                'title': _('Portfolio'),
                'separator': True,
                'collapsible': True,
                'items': [
                    {
                        'title': _('Buildings'),
                        'icon': 'domain',
                        'link': reverse_lazy('admin:properties_building_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_building'
                        ),
                    },
                    {
                        'title': _('Listings'),
                        'icon': 'home_work',
                        'link': reverse_lazy('admin:properties_property_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_property'
                        ),
                    },
                    {
                        'title': _('Customers'),
                        'icon': 'group',
                        'link': reverse_lazy('admin:properties_tenant_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_tenant'
                        ),
                    },
                    {
                        'title': _('Invoices'),
                        'icon': 'receipt_long',
                        'link': reverse_lazy('admin:properties_rentpayment_changelist'),
                        'badge': 'accounts.unfold_dashboard.pending_invoices_badge',
                        'badge_variant': 'warning',
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_rentpayment'
                        ),
                    },
                    {
                        'title': _('Expenses'),
                        'icon': 'payments',
                        'link': reverse_lazy('admin:properties_expense_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_expense'
                        ),
                    },
                ],
            },
            {
                'title': _('Pipeline'),
                'collapsible': True,
                'items': [
                    {
                        'title': _('Leads'),
                        'icon': 'handshake',
                        'link': reverse_lazy('admin:properties_enquiry_changelist'),
                        'badge': 'accounts.unfold_dashboard.unread_leads_badge',
                        'badge_variant': 'info',
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_enquiry'
                        ),
                    },
                    {
                        'title': _('Sale deals'),
                        'icon': 'real_estate_agent',
                        'link': reverse_lazy('admin:properties_saledeal_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_saledeal'
                        ),
                    },
                    {
                        'title': _('Campaigns'),
                        'icon': 'campaign',
                        'link': reverse_lazy('admin:properties_marketingcampaign_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_marketingcampaign'
                        ),
                    },
                    {
                        'title': _('Complaints'),
                        'icon': 'support_agent',
                        'link': reverse_lazy('admin:properties_complaint_changelist'),
                        'badge': 'accounts.unfold_dashboard.open_complaints_badge',
                        'badge_variant': 'danger',
                        'permission': lambda request: request.user.has_perm(
                            'properties.view_complaint'
                        ),
                    },
                ],
            },
            {
                'title': _('Access'),
                'collapsible': True,
                'items': [
                    {
                        'title': _('Users'),
                        'icon': 'manage_accounts',
                        'link': reverse_lazy('admin:auth_user_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'auth.view_user'
                        ),
                    },
                    {
                        'title': _('Brands'),
                        'icon': 'palette',
                        'link': reverse_lazy('admin:accounts_brand_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'accounts.view_brand'
                        ),
                    },
                    {
                        'title': _('Activity log'),
                        'icon': 'history',
                        'link': reverse_lazy('admin:accounts_activitylog_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'accounts.view_activitylog'
                        ),
                    },
                ],
            },
        ],
    },
    'TABS': [
        {
            'models': ['properties.tenant', 'properties.rentpayment'],
            'items': [
                {
                    'title': _('Customers'),
                    'link': reverse_lazy('admin:properties_tenant_changelist'),
                    'permission': lambda request: request.user.has_perm(
                        'properties.view_tenant'
                    ),
                },
                {
                    'title': _('Invoices'),
                    'link': reverse_lazy('admin:properties_rentpayment_changelist'),
                    'permission': lambda request: request.user.has_perm(
                        'properties.view_rentpayment'
                    ),
                },
            ],
        },
    ],
}
