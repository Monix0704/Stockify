from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate

from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import signed_stock_quantity_expression


def filtered_movements(*, date_from=None, date_to=None, warehouse=None, product=None, movement_type=None):
    movements = StockMovement.objects.select_related("product", "warehouse", "created_by")
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)
    if warehouse:
        movements = movements.filter(warehouse=warehouse)
    if product:
        movements = movements.filter(product=product)
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    return movements


def stock_balance_rows(*, warehouse=None, category=None, product=None):
    rows = StockMovement.objects.order_by()
    if warehouse:
        rows = rows.filter(warehouse=warehouse)
    if category:
        rows = rows.filter(product__category=category)
    if product:
        rows = rows.filter(product=product)
    return (
        rows.values(
            "product_id",
            "product__name",
            "product__sku",
            "product__unit",
            "warehouse_id",
            "warehouse__name",
        )
        .annotate(balance=Sum(signed_stock_quantity_expression()))
        .order_by("warehouse__name", "product__name", "product__sku")
    )


def movement_totals(movements):
    return movements.aggregate(
        total=Count("pk"),
        incoming=Count("pk", filter=Q(movement_type=StockMovement.MovementType.IN)),
        outgoing=Count("pk", filter=Q(movement_type=StockMovement.MovementType.OUT)),
    )


def daily_activity(movements):
    return (
        movements.order_by()
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            incoming=Count("pk", filter=Q(movement_type=StockMovement.MovementType.IN)),
            outgoing=Count("pk", filter=Q(movement_type=StockMovement.MovementType.OUT)),
        )
        .order_by("day")
    )


def top_moved_products(movements, limit=8):
    return (
        movements.order_by()
        .values("product_id", "product__name", "product__sku", "product__unit")
        .annotate(operation_count=Count("pk"), handled_quantity=Sum("quantity"))
        .order_by("-operation_count", "product__name", "product__sku")[:limit]
    )


def warehouse_activity(movements):
    activity_by_warehouse = {
        row["warehouse_id"]: row
        for row in (
            movements.order_by()
            .values("warehouse_id")
            .annotate(
                total=Count("pk"),
                incoming=Count("pk", filter=Q(movement_type=StockMovement.MovementType.IN)),
                outgoing=Count("pk", filter=Q(movement_type=StockMovement.MovementType.OUT)),
            )
        )
    }
    return [
        {
            "warehouse": warehouse,
            "total": activity_by_warehouse.get(warehouse.pk, {}).get("total", 0),
            "incoming": activity_by_warehouse.get(warehouse.pk, {}).get("incoming", 0),
            "outgoing": activity_by_warehouse.get(warehouse.pk, {}).get("outgoing", 0),
        }
        for warehouse in Warehouse.objects.order_by("name")
    ]
