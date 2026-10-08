from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import BooleanRadioFilter, ChoicesDropdownFilter, RelatedDropdownFilter
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .admin_mixins import BrandScopedModelAdmin
from .brand_scoping import get_request_brand, users_for_brand
from .models import ActivityLog, Brand, RolePrivilege, UserPrivilege, UserProfile

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    warn_unsaved_form = True
    list_filter_submit = True
    search_help_text = 'Search username, email, or name.'

    def get_queryset(self, request):
        brand = get_request_brand(request)
        if request.user.is_superuser and not request.session.get('preview_brand_slug'):
            return super().get_queryset(request)
        return users_for_brand(brand)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    warn_unsaved_form = True


@admin.register(UserProfile)
class UserProfileAdmin(BrandScopedModelAdmin):
    list_display = ('user', 'role', 'brand', 'avatar_thumb', 'rent_reminder_enabled', 'rent_due_day')
    list_filter = (
        ('role', ChoicesDropdownFilter),
        ('rent_reminder_enabled', BooleanRadioFilter),
        ('brand', RelatedDropdownFilter),
    )
    search_fields = ('user__username', 'user__email')
    search_help_text = 'Search username or email.'
    autocomplete_fields = ('user', 'created_by', 'brand')
    readonly_fields = ('avatar_preview',)

    @admin.display(description=_('Avatar'))
    def avatar_thumb(self, obj):
        if not obj.avatar:
            return '—'
        return format_html('<img src="{}" style="height:32px;width:32px;border-radius:999px;object-fit:cover"/>', obj.avatar.url)

    @admin.display(description=_('Avatar preview'))
    def avatar_preview(self, obj):
        if not obj.avatar:
            return '—'
        return format_html('<img src="{}" style="max-height:96px;border-radius:999px"/>', obj.avatar.url)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        brand = get_request_brand(request)
        if brand is None:
            return qs.none()
        return qs.filter(brand=brand)


@admin.register(RolePrivilege)
class RolePrivilegeAdmin(ModelAdmin):
    list_display = ('role', 'code', 'label', 'enabled')
    list_filter = (
        ('role', ChoicesDropdownFilter),
        ('enabled', BooleanRadioFilter),
    )
    list_editable = ('enabled',)
    list_filter_submit = True
    search_fields = ('code', 'label')


@admin.register(UserPrivilege)
class UserPrivilegeAdmin(ModelAdmin):
    list_display = ('user', 'code', 'label', 'enabled')
    list_filter = (('enabled', BooleanRadioFilter),)
    search_fields = ('user__username', 'code', 'label')
    autocomplete_fields = ('user',)


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = (
        'name',
        'slug',
        'logo_thumb',
        'is_default',
        'is_active',
        'primary_color',
        'updated_at',
    )
    list_filter = (
        ('is_active', BooleanRadioFilter),
        ('is_default', BooleanRadioFilter),
    )
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug', 'hostnames')
    list_filter_submit = True
    warn_unsaved_form = True
    readonly_fields = ('logo_preview', 'icon_preview', 'banner_preview')
    fieldsets = (
        (_('Identity'), {'fields': ('name', 'slug', 'tagline', 'footer_text', 'hostnames', 'base_url')}),
        (_('Brand images'), {'fields': ('logo', 'logo_preview', 'icon', 'icon_preview', 'banner', 'banner_preview')}),
        (_('Status'), {'fields': ('is_default', 'is_active')}),
        (_('Colors'), {
            'fields': (
                'primary_color', 'secondary_color', 'button_color', 'button_text_color',
                'background_color', 'surface_color', 'text_color',
                'header_color', 'header_text_color', 'header_active_color',
                'footer_bg_color', 'footer_text_color',
            ),
            'classes': ('collapse',),
        }),
        (_('Typography & tables'), {'fields': ('font_style', 'table_format', 'border_radius'), 'classes': ('collapse',)}),
    )

    @admin.display(description=_('Logo'))
    def logo_thumb(self, obj):
        if not obj.logo:
            return '—'
        return format_html('<img src="{}" style="height:28px;border-radius:4px"/>', obj.logo.url)

    @admin.display(description=_('Logo preview'))
    def logo_preview(self, obj):
        if not obj.logo:
            return '—'
        return format_html('<img src="{}" style="max-height:80px;border-radius:8px"/>', obj.logo.url)

    @admin.display(description=_('Icon preview'))
    def icon_preview(self, obj):
        if not obj.icon:
            return '—'
        return format_html('<img src="{}" style="max-height:48px;border-radius:8px"/>', obj.icon.url)

    @admin.display(description=_('Banner preview'))
    def banner_preview(self, obj):
        if not obj.banner:
            return '—'
        return format_html('<img src="{}" style="max-height:100px;border-radius:8px"/>', obj.banner.url)


@admin.register(ActivityLog)
class ActivityLogAdmin(BrandScopedModelAdmin):
    list_display = (
        'created_at',
        'username',
        'action',
        'method',
        'path',
        'status_code',
        'ip_address',
    )
    list_filter = (
        ('action', ChoicesDropdownFilter),
        'method',
        'status_code',
    )
    search_fields = ('username', 'path', 'message', 'ip_address')
    search_help_text = 'Search user, path, message, or IP.'
    readonly_fields = (
        'user',
        'username',
        'action',
        'method',
        'path',
        'status_code',
        'ip_address',
        'user_agent',
        'message',
        'created_at',
        'brand',
    )
    date_hierarchy = 'created_at'
    list_filter_submit = True

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
