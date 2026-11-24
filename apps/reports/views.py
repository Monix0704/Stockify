import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

from apps.catalog.models import Product
from apps.inventory.models import StockMovement
from .forms import AnalyticsPeriodForm, MovementReportFilterForm, StockReportFilterForm
from .selectors import (
    daily_activity,
    filtered_movements,
    movement_totals,
    stock_balance_rows,
    top_moved_products,
    warehouse_activity,
)


def _unit_label(value):
    return dict(Product.Unit.choices).get(value, value)


def _csv_response(filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    return response


def _apply_page(request, queryset, page_size=25):
    page_obj = Paginator(queryset, page_size).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return page_obj, query.urlencode()


@login_required
def analytics_dashboard(request):
    today = timezone.localdate()
    initial = {"date_from": today - timedelta(days=29), "date_to": today}
    form = AnalyticsPeriodForm(request.GET if request.GET else None, initial=initial)
    is_valid = form.is_valid() if request.GET else True
    totals = {"total": 0, "incoming": 0, "outgoing": 0}
    top_products = []
    activity = []
    chart_data = {
        "daily": {"labels": [], "incoming": [], "outgoing": []},
        "comparison": {"labels": ["Поступления", "Списания"], "values": [0, 0]},
        "warehouses": {"labels": [], "values": []},
    }

    if is_valid:
        date_from = form.cleaned_data["date_from"] if request.GET else initial["date_from"]
        date_to = form.cleaned_data["date_to"] if request.GET else initial["date_to"]
        movements = filtered_movements(date_from=date_from, date_to=date_to)
        totals = movement_totals(movements)
        top_products = list(top_moved_products(movements))
        for row in top_products:
            row["unit_label"] = _unit_label(row["product__unit"])
        activity = warehouse_activity(movements)

        daily_rows = {row["day"]: row for row in daily_activity(movements)}
        current_day = date_from
        while current_day <= date_to:
            row = daily_rows.get(current_day, {})
            chart_data["daily"]["labels"].append(current_day.strftime("%d.%m"))
            chart_data["daily"]["incoming"].append(row.get("incoming", 0))
            chart_data["daily"]["outgoing"].append(row.get("outgoing", 0))
            current_day += timedelta(days=1)

        chart_data["comparison"]["values"] = [totals["incoming"], totals["outgoing"]]
        chart_data["warehouses"] = {
            "labels": [row["warehouse"].name for row in activity],
            "values": [row["total"] for row in activity],
        }

    return render(
        request,
        "reports/dashboard.html",
        {
            "form": form,
            "is_valid": is_valid,
            "totals": totals,
            "top_products": top_products,
            "warehouse_activity": activity,
            "chart_data": chart_data,
        },
    )


@login_required
def stock_report(request):
    form = StockReportFilterForm(request.GET if request.GET else None)
    is_valid = form.is_valid() if request.GET else True
    if is_valid:
        cleaned = form.cleaned_data if request.GET else {}
        rows = stock_balance_rows(
            warehouse=cleaned.get("warehouse"),
            category=cleaned.get("category"),
            product=cleaned.get("product"),
        )
        page_obj, page_query = _apply_page(request, rows)
    else:
        page_obj, page_query = _apply_page(request, [])

    for row in page_obj.object_list:
        row["unit_label"] = _unit_label(row["product__unit"])

    return render(
        request,
        "reports/stock.html",
        {"form": form, "page_obj": page_obj, "page_query": page_query, "is_valid": is_valid},
    )


@login_required
def stock_export(request):
    form = StockReportFilterForm(request.GET or None)
    if request.GET and not form.is_valid():
        return HttpResponseBadRequest("Некорректные параметры фильтра отчёта по остаткам.")
    cleaned = form.cleaned_data if request.GET else {}
    rows = stock_balance_rows(
        warehouse=cleaned.get("warehouse"),
        category=cleaned.get("category"),
        product=cleaned.get("product"),
    )
    response = _csv_response("stockify-stock-report.csv")
    writer = csv.writer(response)
    writer.writerow(["Товар", "SKU", "Склад", "Остаток", "Единица измерения"])
    for row in rows.iterator():
        writer.writerow(
            [
                row["product__name"],
                row["product__sku"],
                row["warehouse__name"],
                row["balance"],
                _unit_label(row["product__unit"]),
            ]
        )
    return response


def _movement_form_from_request(request):
    form = MovementReportFilterForm(request.GET if request.GET else None)
    is_valid = form.is_valid() if request.GET else True
    if not is_valid:
        return form, False, StockMovement.objects.none()
    cleaned = form.cleaned_data if request.GET else {}
    return (
        form,
        True,
        filtered_movements(
            date_from=cleaned.get("date_from"),
            date_to=cleaned.get("date_to"),
            warehouse=cleaned.get("warehouse"),
            product=cleaned.get("product"),
            movement_type=cleaned.get("movement_type"),
        ),
    )


@login_required
def movement_report(request):
    form, is_valid, movements = _movement_form_from_request(request)
    page_obj, page_query = _apply_page(request, movements)
    return render(
        request,
        "reports/movements.html",
        {"form": form, "is_valid": is_valid, "page_obj": page_obj, "page_query": page_query},
    )


@login_required
def movement_export(request):
    form, is_valid, movements = _movement_form_from_request(request)
    if not is_valid:
        return HttpResponseBadRequest("Некорректные параметры фильтра отчёта по движениям.")

    response = _csv_response("stockify-movement-report.csv")
    writer = csv.writer(response)
    writer.writerow(["Дата операции", "Товар", "SKU", "Склад", "Тип операции", "Количество", "Единица измерения", "Пользователь"])
    for movement in movements.iterator():
        operator = ""
        if movement.created_by:
            operator = movement.created_by.get_short_name() or movement.created_by.username
        writer.writerow(
            [
                timezone.localtime(movement.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                movement.product.name,
                movement.product.sku,
                movement.warehouse.name,
                movement.get_movement_type_display(),
                movement.quantity,
                movement.product.get_unit_display(),
                operator,
            ]
        )
    return response
