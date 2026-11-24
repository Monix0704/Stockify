from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.catalog.models import Category, Product, Supplier
from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import signed_stock_quantity_expression


@login_required
def home(request):
    signed_quantity = signed_stock_quantity_expression()
    recent_movements = StockMovement.objects.select_related("product", "warehouse", "created_by")[:8]
    balance_rows = (
        StockMovement.objects.order_by()
        .values(
            "product_id",
            "product__name",
            "product__sku",
            "product__unit",
            "warehouse_id",
            "warehouse__name",
        )
        .annotate(balance=Sum(signed_quantity))
        .order_by("warehouse__name", "product__name")
    )
    context = {
        "product_count": Product.objects.count(),
        "warehouse_count": Warehouse.objects.filter(is_active=True).count(),
        "category_count": Category.objects.count(),
        "supplier_count": Supplier.objects.count(),
        "recent_movements": recent_movements,
        "balance_rows": balance_rows[:12],
        # Product currently has no unit price, so valuation cannot be calculated honestly.
        "stock_value_available": False,
    }
    return render(request, "dashboard/home.html", context)
