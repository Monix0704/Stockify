from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When

from apps.catalog.models import Product
from .models import StockMovement, Warehouse


class InsufficientStockError(Exception):
    """Raised when a requested issue is larger than the available balance."""


class InactiveInventoryItemError(Exception):
    """Raised when stock is moved for an inactive product or warehouse."""


def _as_positive_quantity(value):
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({"quantity": "Введите корректное положительное количество."}) from exc

    if not quantity.is_finite() or quantity <= 0:
        raise ValidationError({"quantity": "Количество должно быть больше нуля."})
    if quantity.as_tuple().exponent < -3 or quantity.adjusted() > 8:
        raise ValidationError({"quantity": "Количество должно помещаться в формат 9 цифр и 3 знака после запятой."})
    return quantity


def signed_stock_quantity_expression(prefix=""):
    movement_type_field = f"{prefix}movement_type"
    quantity_field = f"{prefix}quantity"
    return Case(
        When(**{movement_type_field: StockMovement.MovementType.IN}, then=F(quantity_field)),
        When(**{movement_type_field: StockMovement.MovementType.OUT}, then=-F(quantity_field)),
        default=Value(Decimal("0")),
        output_field=DecimalField(max_digits=12, decimal_places=3),
    )


def get_stock_balance(product, warehouse):
    """Return the current quantity for one product in one warehouse."""
    product_id = getattr(product, "pk", product)
    warehouse_id = getattr(warehouse, "pk", warehouse)
    balance = StockMovement.objects.filter(product_id=product_id, warehouse_id=warehouse_id).aggregate(
        balance=Sum(signed_stock_quantity_expression())
    )["balance"]
    return balance or Decimal("0.000")


def get_stock_balances():
    """Return calculated balances keyed by (product_id, warehouse_id)."""
    rows = (
        StockMovement.objects.order_by()
        .values("product_id", "warehouse_id")
        .annotate(balance=Sum(signed_stock_quantity_expression()))
    )
    return {
        (row["product_id"], row["warehouse_id"]): row["balance"]
        for row in rows
    }


def _record_movement(product_id, warehouse_id, movement_type, quantity, *, note="", created_by=None):
    quantity = _as_positive_quantity(quantity)

    with transaction.atomic():
        # Locking the product row serializes all operations for that product,
        # including the case where no movement rows exist yet for this warehouse.
        product = Product.objects.select_for_update().get(pk=product_id)
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)

        if not product.is_active or not warehouse.is_active:
            raise InactiveInventoryItemError("Нельзя проводить операции для неактивного товара или склада.")

        if movement_type == StockMovement.MovementType.OUT:
            available = get_stock_balance(product.pk, warehouse.pk)
            if quantity > available:
                raise InsufficientStockError(
                    f"Недостаточно товара на складе «{warehouse.name}»: доступно {available}, запрошено {quantity}."
                )

        movement = StockMovement(
            product=product,
            warehouse=warehouse,
            movement_type=movement_type,
            quantity=quantity,
            note=note,
            created_by=created_by,
        )
        movement.full_clean()
        movement.save(force_insert=True)
        return movement


def receive_stock(product_id, warehouse_id, quantity, *, note="", created_by=None):
    """Record an incoming stock movement atomically."""
    return _record_movement(
        product_id,
        warehouse_id,
        StockMovement.MovementType.IN,
        quantity,
        note=note,
        created_by=created_by,
    )


def issue_stock(product_id, warehouse_id, quantity, *, note="", created_by=None):
    """Record an outgoing movement only when the locked balance is sufficient."""
    return _record_movement(
        product_id,
        warehouse_id,
        StockMovement.MovementType.OUT,
        quantity,
        note=note,
        created_by=created_by,
    )
