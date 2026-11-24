from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Product, Supplier
from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import get_stock_balance, receive_stock


class WebInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="web-operator", password="test-password-123")
        cls.category = Category.objects.create(name="Web test category")
        cls.supplier = Supplier.objects.create(name="Web test supplier", email="supplier@example.test")
        cls.product = Product.objects.create(
            sku="WEB-TEST-001",
            name="Web test product",
            category=cls.category,
            preferred_supplier=cls.supplier,
        )
        cls.warehouse = Warehouse.objects.create(name="Web test warehouse")

    def setUp(self):
        self.client.force_login(self.user)

    def test_required_pages_and_named_routes_render(self):
        routes = (
            "dashboard:home",
            "catalog:products",
            "catalog:product_detail",
            "catalog:categories",
            "catalog:suppliers",
            "inventory:warehouses",
            "inventory:movements",
            "inventory:receive",
            "inventory:issue",
        )
        for route in routes:
            with self.subTest(route=route):
                args = [self.product.pk] if route == "catalog:product_detail" else []
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)

    def test_dashboard_uses_database_data_and_explains_unavailable_valuation(self):
        receive_stock(self.product.pk, self.warehouse.pk, "4.500", created_by=self.user)

        response = self.client.get(reverse("dashboard:home"))

        self.assertContains(response, "Web test product")
        self.assertContains(response, "4,5")
        self.assertContains(response, "нет цены")
        self.assertContains(response, "Активные склады")
        self.assertContains(response, "Товары по складам")

    def test_catalog_search_filter_and_detail_show_calculated_stock(self):
        receive_stock(self.product.pk, self.warehouse.pk, "7.000")

        listing = self.client.get(reverse("catalog:products"), {"q": "WEB-TEST", "stock": "available"})
        detail = self.client.get(reverse("catalog:product_detail", args=[self.product.pk]))

        self.assertContains(listing, self.product.name)
        self.assertContains(detail, "7")
        self.assertContains(detail, self.warehouse.name)

    def test_receive_form_uses_service_and_records_current_user(self):
        response = self.client.post(
            reverse("inventory:receive"),
            {"product": self.product.pk, "warehouse": self.warehouse.pk, "quantity": "8.250", "note": "Invoice 15"},
        )

        self.assertRedirects(response, reverse("inventory:movements"))
        movement = StockMovement.objects.get()
        self.assertEqual(movement.movement_type, StockMovement.MovementType.IN)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("8.250"))

    def test_issue_form_uses_service_and_displays_insufficient_stock_error(self):
        receive_stock(self.product.pk, self.warehouse.pk, "2.000")
        response = self.client.post(
            reverse("inventory:issue"),
            {"product": self.product.pk, "warehouse": self.warehouse.pk, "quantity": "3.000", "note": "Too much"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Недостаточно товара")
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("2.000"))

    def test_issue_form_records_successful_operation(self):
        receive_stock(self.product.pk, self.warehouse.pk, "5.000")

        response = self.client.post(
            reverse("inventory:issue"),
            {"product": self.product.pk, "warehouse": self.warehouse.pk, "quantity": "1.500", "note": "Order 22"},
        )

        self.assertRedirects(response, reverse("inventory:movements"))
        movement = StockMovement.objects.get(movement_type=StockMovement.MovementType.OUT)
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("3.500"))

    def test_mutating_pages_require_login(self):
        self.client.logout()

        response = self.client.get(reverse("inventory:receive"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('inventory:receive')}")

    def test_login_and_logout_pages_work(self):
        self.client.logout()
        login_page = self.client.get(reverse("login"))
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, 'name="csrfmiddlewaretoken"')

        response = self.client.post(
            reverse("login"),
            {"username": "web-operator", "password": "test-password-123"},
        )
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
