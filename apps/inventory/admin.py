from decimal import Decimal

from django.contrib import admin
from django.db.models import Case, DecimalField, F, OuterRef, Subquery, Sum, Value, When

from .models import StockMovement, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "address")
    readonly_fields = ("created_at",)
    ordering = ("name",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "movement_type", "product", "warehouse", "quantity", "current_balance", "created_by")
    list_filter = ("movement_type", "product", "warehouse", "created_at")
    search_fields = ("product__name", "product__sku", "note")
    list_select_related = ("product", "warehouse", "created_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-pk")
    readonly_fields = tuple(field.name for field in StockMovement._meta.fields)

    def get_queryset(self, request):
        signed_quantity = Case(
            When(movement_type=StockMovement.MovementType.IN, then=F("quantity")),
            When(movement_type=StockMovement.MovementType.OUT, then=-F("quantity")),
            default=Value(Decimal("0")),
            output_field=DecimalField(max_digits=12, decimal_places=3),
        )
        balances = (
            StockMovement.objects.filter(product_id=OuterRef("product_id"), warehouse_id=OuterRef("warehouse_id"))
            .order_by()
            .values("product_id", "warehouse_id")
            .annotate(balance=Sum(signed_quantity))
            .values("balance")[:1]
        )
        return super().get_queryset(request).annotate(_current_balance=Subquery(balances))

    @admin.display(description="Остаток сейчас", ordering="_current_balance")
    def current_balance(self, obj):
        return obj._current_balance or Decimal("0.000")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
