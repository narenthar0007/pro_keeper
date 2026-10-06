from rest_framework import serializers

from .forms import get_or_create_custom_amenity
from .models import (
    Amenity,
    Building,
    Enquiry,
    Expense,
    Property,
    RentPayment,
    Tenant,
    TenantJoinRequest,
    UserNotification,
    OTHERS_AMENITY_CODE,
)


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'code', 'label']


class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = ['id', 'name', 'address', 'city', 'is_active']


class PropertySerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    display_price = serializers.CharField(read_only=True)
    building_name = serializers.CharField(source='building.name', read_only=True, default='')
    amenity_ids = serializers.PrimaryKeyRelatedField(
        source='amenities',
        many=True,
        queryset=Amenity.objects.exclude(code=OTHERS_AMENITY_CODE),
        required=False,
    )
    amenity_labels = serializers.SerializerMethodField()
    current_tenant_name = serializers.SerializerMethodField()
    other_amenity = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Property
        fields = [
            'id',
            'title',
            'description',
            'listing_type',
            'door_number',
            'street',
            'landmark',
            'address',
            'city',
            'state',
            'pincode',
            'country',
            'contact_phone',
            'property_type',
            'bedrooms',
            'bathrooms',
            'rooms',
            'kitchens',
            'area_sqft',
            'year_of_building',
            'monthly_rent',
            'advance_amount',
            'sale_price',
            'sale_status',
            'price_negotiable',
            'furnishing',
            'display_price',
            'is_listed_publicly',
            'is_occupied',
            'planned_vacate_date',
            'building',
            'building_name',
            'unit_number',
            'floor_number',
            'owner_username',
            'amenity_ids',
            'amenity_labels',
            'current_tenant_name',
            'other_amenity',
        ]

    def get_amenity_labels(self, obj):
        return list(obj.amenities.exclude(code=OTHERS_AMENITY_CODE).values_list('label', flat=True))

    def get_current_tenant_name(self, obj):
        tenant = obj.current_tenant
        return tenant.name if tenant else ''

    def create(self, validated_data):
        extra = validated_data.pop('other_amenity', '')
        amenities = validated_data.pop('amenities', [])
        prop = super().create(validated_data)
        if amenities:
            prop.amenities.set(amenities)
        extra_obj = get_or_create_custom_amenity(extra)
        if extra_obj:
            prop.amenities.add(extra_obj)
        return prop

    def update(self, instance, validated_data):
        extra = validated_data.pop('other_amenity', '')
        amenities = validated_data.pop('amenities', None)
        prop = super().update(instance, validated_data)
        if amenities is not None:
            prop.amenities.set(amenities)
        extra_obj = get_or_create_custom_amenity(extra)
        if extra_obj:
            prop.amenities.add(extra_obj)
        return prop


class TenantSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')
    existing_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    create_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    create_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Tenant
        fields = [
            'id',
            'property',
            'property_title',
            'name',
            'phone',
            'email',
            'is_active',
            'move_in_date',
            'lease_end_date',
            'advance_paid',
            'advance_refunded',
            'advance_deduction',
            'notes',
            'username',
            'existing_username',
            'create_username',
            'create_password',
        ]


class RentPaymentSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True, default='')

    class Meta:
        model = RentPayment
        fields = [
            'id',
            'property',
            'property_title',
            'tenant',
            'tenant_name',
            'amount',
            'payment_date',
            'month_for',
            'due_date',
            'status',
            'late_fee',
            'notes',
        ]


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'id',
            'property',
            'title',
            'category',
            'amount',
            'expense_date',
            'notes',
        ]


class EnquirySerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)

    class Meta:
        model = Enquiry
        fields = [
            'id',
            'property',
            'property_title',
            'name',
            'email',
            'phone',
            'message',
            'is_read',
            'status',
            'created_at',
        ]
        read_only_fields = ['is_read', 'status', 'created_at']


class InboxSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = UserNotification
        fields = ['id', 'kind', 'kind_label', 'title', 'url', 'is_read', 'created_at']


class JoinRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)

    class Meta:
        model = TenantJoinRequest
        fields = ['id', 'property', 'property_title', 'username', 'message', 'status', 'created_at']
