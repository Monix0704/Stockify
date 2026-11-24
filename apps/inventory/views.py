from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from apps.catalog.models import Product
from .forms import StockMovementForm
from .models import StockMovement, Warehouse
from .services import (
    InactiveInventoryItemError,
    InsufficientStockError,
    issue_stock,
    receive_stock,
)


@login_required
def warehouse_list(request):
    warehouses = Warehouse.objects.annotate(
        movement_count=Count("stock_movements"),
        product_count=Count("stock_movements__product", distinct=True),
    ).order_by("name")
    return render(request, "inventory/warehouses.html", {"warehouses": warehouses})


@login_required
def movement_list(request):
    movements = StockMovement.objects.select_related("product", "warehouse", "created_by")
    movement_type = request.GET.get("type", "")
    product_id = request.GET.get("product", "")
    warehouse_id = request.GET.get("warehouse", "")
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    if movement_type in StockMovement.MovementType.values:
        movements = movements.filter(movement_type=movement_type)
    if product_id.isdigit():
        movements = movements.filter(product_id=product_id)
    if warehouse_id.isdigit():
        movements = movements.filter(warehouse_id=warehouse_id)
    parsed_from = parse_date(date_from)
    parsed_to = parse_date(date_to)
    if parsed_from:
        movements = movements.filter(created_at__date__gte=parsed_from)
    if parsed_to:
        movements = movements.filter(created_at__date__lte=parsed_to)

    page_obj = Paginator(movements, 20).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "inventory/movements.html",
        {
            "page_obj": page_obj,
            "page_query": query.urlencode(),
            "products": Product.objects.order_by("name"),
            "warehouses": Warehouse.objects.order_by("name"),
            "movement_type": movement_type,
            "selected_product": product_id,
            "selected_warehouse": warehouse_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
def _movement_form(request, movement_type):
    is_receipt = movement_type == StockMovement.MovementType.IN
    form = StockMovementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        operation = receive_stock if is_receipt else issue_stock
        try:
            operation(
                form.cleaned_data["product"].pk,
                form.cleaned_data["warehouse"].pk,
                form.cleaned_data["quantity"],
                note=form.cleaned_data["note"],
                created_by=request.user,
            )
        except InsufficientStockError as exc:
            form.add_error("quantity", str(exc))
        except InactiveInventoryItemError as exc:
            form.add_error(None, str(exc))
        except (ValidationError, ObjectDoesNotExist) as exc:
            message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Товар или склад уже недоступен."
            form.add_error(None, message)
        else:
            messages.success(
                request,
                "Поступление сохранено." if is_receipt else "Списание сохранено.",
            )
            return redirect("inventory:movements")

    return render(
        request,
        "inventory/movement_form.html",
        {
            "form": form,
            "is_receipt": is_receipt,
            "page_title": "Поступление товара" if is_receipt else "Списание товара",
            "submit_label": "Провести поступление" if is_receipt else "Провести списание",
            "has_choices": form.fields["warehouse"].queryset.exists() and form.fields["product"].queryset.exists(),
        },
    )


def receive(request):
    return _movement_form(request, StockMovement.MovementType.IN)


def issue(request):
    return _movement_form(request, StockMovement.MovementType.OUT)
