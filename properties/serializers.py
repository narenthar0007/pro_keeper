from rest_framework import serializers

from .models import Expense, Property, RentPayment, Tenant


class PropertySerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    display_price = serializers.CharField(read_only=True)

    class Meta:
        model = Property
        fields = [
            'id',
            'title',
            'description',
            'listing_type',
            'address',
            'city',
            'state',
            'pincode',
            'property_type',
            'bedrooms',
            'bathrooms',
            'area_sqft',
            'monthly_rent',
            'sale_price',
            'sale_status',
            'price_negotiable',
            'furnishing',
            'display_price',
            'advance_amount',
            'is_listed_publicly',
            'is_occupied',
            'year_of_building',
            'owner_username',
        ]


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            'id',
            'property',
            'name',
            'phone',
            'email',
            'is_active',
            'move_in_date',
            'lease_end_date',
            'advance_paid',
            'advance_refunded',
            'advance_deduction',
        ]


class RentPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentPayment
        fields = [
            'id',
            'property',
            'tenant',
            'amount',
            'payment_date',
            'month_for',
            'status',
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
