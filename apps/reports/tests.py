import csv
import io
import json
import re
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import get_stock_balance, issue_stock, receive_stock
from .selectors import stock_balance_rows


class ReportsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="reports-user", password="reports-pass-123")
        cls.category = Category.objects.create(name="Reports category")
        cls.other_category = Category.objects.create(name="Other reports category")
        cls.product = Product.objects.create(
            sku="REPORT-001",
            name="Paper clips",
            category=cls.category,
            unit=Product.Unit.PIECE,
        )
        cls.other_product = Product.objects.create(
            sku="REPORT-002",
            name="Steel sheet",
            category=cls.other_category,
            unit=Product.Unit.KILOGRAM,
        )
        cls.warehouse = Warehouse.objects.create(name="East warehouse")
        cls.other_warehouse = Warehouse.objects.create(name="West warehouse")
        cls.empty_warehouse = Warehouse.objects.create(name="Inactive demo warehouse", is_active=False)

    def setUp(self):
        self.client.force_login(self.user)
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        self._receive_on(self.product, self.warehouse, "5.000", today)
        self._issue_on(self.product, self.warehouse, "2.000", today)
        self._receive_on(self.other_product, self.other_warehouse, "1.750", yesterday)

    def _at(self, day):
        return timezone.make_aware(datetime.combine(day, time(12, 0)), timezone.get_current_timezone())

    def _receive_on(self, product, warehouse, quantity, day):
        with patch("django.utils.timezone.now", return_value=self._at(day)):
            return receive_stock(product.pk, warehouse.pk, quantity, created_by=self.user)

    def _issue_on(self, product, warehouse, quantity, day):
        with patch("django.utils.timezone.now", return_value=self._at(day)):
            return issue_stock(product.pk, warehouse.pk, quantity, created_by=self.user)

    def test_report_routes_render(self):
        for route in ("reports:dashboard", "reports:stock", "reports:movements"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_analytics_counts_daily_chart_top_products_and_warehouse_activity(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(reverse("reports:dashboard"), {"date_from": today, "date_to": today})

        self.assertContains(response, "Paper clips")
        chart_match = re.search(
            r'<script id="reports-chart-data" type="application/json">(.*?)</script>',
            response.content.decode("utf-8"),
        )
        self.assertIsNotNone(chart_match)
        chart_data = json.loads(chart_match.group(1))
        self.assertEqual(chart_data["comparison"]["values"], [1, 1])
        self.assertEqual(chart_data["daily"]["incoming"], [1])
        self.assertEqual(chart_data["daily"]["outgoing"], [1])
        self.assertEqual(chart_data["warehouses"]["values"], [2, 0, 0])
        self.assertEqual(StockMovement.objects.filter(created_at__date=timezone.localdate()).count(), 2)

    def test_analytics_date_filter_excludes_other_days_and_invalid_ranges_are_rejected(self):
        today = timezone.localdate().isoformat()
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.get(reverse("reports:dashboard"), {"date_from": tomorrow, "date_to": today})

        self.assertContains(response, "Проверьте выбранный период")
        self.assertNotContains(response, 'id="reports-chart-data"')

        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.get(reverse("reports:dashboard"), {"date_from": yesterday, "date_to": yesterday})
        chart_match = re.search(r'<script id="reports-chart-data" type="application/json">(.*?)</script>', response.content.decode("utf-8"))
        chart_data = json.loads(chart_match.group(1))
        self.assertEqual(chart_data["comparison"]["values"], [1, 0])

    def test_stock_report_filters_by_warehouse_category_and_product(self):
        response = self.client.get(
            reverse("reports:stock"),
            {"warehouse": self.warehouse.pk, "category": self.category.pk, "product": self.product.pk},
        )

        self.assertContains(response, "Paper clips")
        self.assertContains(response, "East warehouse")
        self.assertContains(response, "3")
        table_body = re.search(r"<tbody>(.*?)</tbody>", response.content.decode("utf-8"), re.DOTALL)
        self.assertIsNotNone(table_body)
        self.assertNotIn("Steel sheet", table_body.group(1))
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("3.000"))

    def test_stock_balances_remain_separate_across_product_units(self):
        response = self.client.get(reverse("reports:stock"))

        self.assertContains(response, "Paper clips")
        self.assertContains(response, "Steel sheet")
        self.assertContains(response, "шт.")
        self.assertContains(response, "кг")
        rows = list(stock_balance_rows())
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["balance"] for row in rows}, {Decimal("3.000"), Decimal("1.750")})

    def test_movement_report_filters_dates_warehouse_product_and_type(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(
            reverse("reports:movements"),
            {
                "date_from": today,
                "date_to": today,
                "warehouse": self.warehouse.pk,
                "product": self.product.pk,
                "movement_type": StockMovement.MovementType.OUT,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Списание")
        self.assertContains(response, "2")
        table_body = re.search(r"<tbody>(.*?)</tbody>", response.content.decode("utf-8"), re.DOTALL)
        self.assertIsNotNone(table_body)
        self.assertNotIn("Steel sheet", table_body.group(1))
        self.assertContains(response, "1 записей")

    def test_movement_csv_is_utf8_and_obeys_filters(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(
            reverse("reports:movement_export"),
            {"date_from": today, "date_to": today, "warehouse": self.warehouse.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        text = response.content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0][0], "Дата операции")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row[3] == "East warehouse" for row in rows[1:]))

    def test_stock_csv_honors_product_filter_and_contains_utf8_bom(self):
        response = self.client.get(reverse("reports:stock_export"), {"product": self.other_product.pk})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["Товар", "SKU", "Склад", "Остаток", "Единица измерения"])
        self.assertEqual(rows[1][0], "Steel sheet")
        self.assertEqual(len(rows), 2)

    def test_invalid_report_filters_do_not_export_unfiltered_data(self):
        response = self.client.get(reverse("reports:movement_export"), {"date_from": "not-a-date"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Некорректные параметры", response.content.decode("utf-8"))
