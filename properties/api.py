from rest_framework import permissions, viewsets

from accounts.brand_scoping import assign_brand, get_request_brand

from .models import Expense, Property, RentPayment, Tenant
from .serializers import (
    ExpenseSerializer,
    PropertySerializer,
    RentPaymentSerializer,
    TenantSerializer,
)


class IsOwnerOrReadOnlyPublic(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        brand = get_request_brand(request)
        if request.method in permissions.SAFE_METHODS:
            if isinstance(obj, Property):
                return obj.is_listed_publicly and obj.brand_id == brand.id and (
                    obj.user_can_manage(request.user, brand=brand) or obj.is_listed_publicly
                )
            return True
        return obj.user_can_manage(request.user, brand=brand) if hasattr(obj, 'user_can_manage') else False


class PropertyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        brand = get_request_brand(self.request)
        qs = Property.for_brand(brand).filter(is_listed_publicly=True)
        city = self.request.query_params.get('city')
        if city:
            qs = qs.filter(city__icontains=city)
        return qs


class MyPropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        brand = get_request_brand(self.request)
        return Property.for_user(self.request.user, brand=brand)

    def perform_create(self, serializer):
        brand = get_request_brand(self.request)
        prop = serializer.save(owner=self.request.user)
        assign_brand(prop, brand)
        prop.save(update_fields=['brand'])


class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        brand = get_request_brand(self.request)
        return Tenant.objects.filter(
            brand=brand,
            property__in=Property.for_user(self.request.user, brand=brand),
        )


class RentPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RentPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        brand = get_request_brand(self.request)
        return RentPayment.objects.filter(
            brand=brand,
            property__in=Property.for_user(self.request.user, brand=brand),
        )


class ExpenseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        brand = get_request_brand(self.request)
        return Expense.objects.filter(
            brand=brand,
            property__in=Property.for_user(self.request.user, brand=brand),
        )
