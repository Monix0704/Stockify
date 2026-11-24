from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render

from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import signed_stock_quantity_expression
from .models import Category, Product, Supplier


def _page(request, queryset, page_size=12):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return page_obj, query.urlencode()


@login_required
def product_list(request):
    total_stock = Coalesce(
        Sum(signed_stock_quantity_expression("stock_movements__")),
        Value(Decimal("0.000"), output_field=DecimalField(max_digits=16, decimal_places=3)),
    )
    products = (
        Product.objects.select_related("category", "preferred_supplier")
        .annotate(stock_total=total_stock)
        .order_by("name", "sku")
    )
    search = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "")
    stock_status = request.GET.get("stock", "")

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if category_id.isdigit():
        products = products.filter(category_id=category_id)
    if stock_status == "low":
        products = products.filter(stock_total__lte=F("reorder_level"))
    elif stock_status == "available":
        products = products.filter(stock_total__gt=0)

    page_obj, page_query = _page(request, products)
    return render(
        request,
        "catalog/products.html",
        {
            "page_obj": page_obj,
            "page_query": page_query,
            "categories": Category.objects.order_by("name"),
            "search": search,
            "selected_category": category_id,
            "stock_status": stock_status,
        },
    )


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related("category", "preferred_supplier"), pk=pk)
    balance_by_warehouse = {
        row["warehouse_id"]: row["balance"]
        for row in (
            StockMovement.objects.filter(product=product)
            .order_by()
            .values("warehouse_id")
            .annotate(balance=Sum(signed_stock_quantity_expression()))
        )
    }
    warehouse_balances = [
        {"warehouse": warehouse, "balance": balance_by_warehouse.get(warehouse.pk, Decimal("0.000"))}
        for warehouse in Warehouse.objects.order_by("name")
    ]
    movements = StockMovement.objects.filter(product=product).select_related("warehouse", "created_by")[:10]
    return render(
        request,
        "catalog/product_detail.html",
        {"product": product, "warehouse_balances": warehouse_balances, "recent_movements": movements},
    )


@login_required
def category_list(request):
    categories = Category.objects.annotate(product_count=Count("products")).order_by("name")
    search = request.GET.get("q", "").strip()
    if search:
        categories = categories.filter(Q(name__icontains=search) | Q(description__icontains=search))
    page_obj, page_query = _page(request, categories)
    return render(
        request,
        "catalog/categories.html",
        {"page_obj": page_obj, "page_query": page_query, "search": search},
    )


@login_required
def supplier_list(request):
    suppliers = Supplier.objects.annotate(product_count=Count("products")).order_by("name")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if search:
        suppliers = suppliers.filter(
            Q(name__icontains=search) | Q(contact_name__icontains=search) | Q(email__icontains=search)
        )
    if status in {"active", "inactive"}:
        suppliers = suppliers.filter(is_active=(status == "active"))
    page_obj, page_query = _page(request, suppliers)
    return render(
        request,
        "catalog/suppliers.html",
        {"page_obj": page_obj, "page_query": page_query, "search": search, "status": status},
    )
