from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, TransactionTestCase

from apps.catalog.models import Category, Product
from .models import StockMovement, Warehouse
from .services import InsufficientStockError, get_stock_balance, get_stock_balances, issue_stock, receive_stock


class InventoryServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Inventory test category")
        cls.product = Product.objects.create(sku="INV-TEST-001", name="Inventory test product", category=cls.category)
        cls.warehouse = Warehouse.objects.create(name="Inventory test warehouse")
        cls.other_warehouse = Warehouse.objects.create(name="Second inventory test warehouse")

    def test_successful_receipt(self):
        movement = receive_stock(self.product.pk, self.warehouse.pk, "12.500", note="delivery")

        self.assertEqual(movement.movement_type, StockMovement.MovementType.IN)
        self.assertEqual(movement.quantity, Decimal("12.500"))
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("12.500"))

    def test_successful_issue(self):
        receive_stock(self.product.pk, self.warehouse.pk, "8.000")

        movement = issue_stock(self.product.pk, self.warehouse.pk, "3.250", note="damaged")

        self.assertEqual(movement.movement_type, StockMovement.MovementType.OUT)
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("4.750"))

    def test_balance_is_sum_of_receipts_minus_issues(self):
        receive_stock(self.product.pk, self.warehouse.pk, "10.000")
        receive_stock(self.product.pk, self.warehouse.pk, "2.500")
        issue_stock(self.product.pk, self.warehouse.pk, "4.250")

        self.assertEqual(get_stock_balance(self.product.pk, self.warehouse.pk), Decimal("8.250"))

    def test_issue_is_rejected_when_stock_is_insufficient_and_writes_nothing(self):
        receive_stock(self.product.pk, self.warehouse.pk, "2.000")

        with self.assertRaises(InsufficientStockError):
            issue_stock(self.product.pk, self.warehouse.pk, "2.001")

        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("2.000"))
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_same_product_balances_are_independent_per_warehouse(self):
        receive_stock(self.product.pk, self.warehouse.pk, "5.000")
        receive_stock(self.product.pk, self.other_warehouse.pk, "9.000")
        issue_stock(self.product.pk, self.warehouse.pk, "2.000")

        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("3.000"))
        self.assertEqual(get_stock_balance(self.product, self.other_warehouse), Decimal("9.000"))
        self.assertEqual(
            get_stock_balances(),
            {(self.product.pk, self.warehouse.pk): Decimal("3.000"), (self.product.pk, self.other_warehouse.pk): Decimal("9.000")},
        )

    def test_zero_and_negative_quantities_are_rejected(self):
        for quantity in (Decimal("0"), Decimal("-1")):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                receive_stock(self.product.pk, self.warehouse.pk, quantity)

        self.assertEqual(StockMovement.objects.count(), 0)

    def test_database_rejects_non_positive_quantity(self):
        for quantity in (Decimal("0"), Decimal("-1")):
            with self.subTest(quantity=quantity), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    StockMovement.objects.create(
                        product=self.product,
                        warehouse=self.warehouse,
                        movement_type=StockMovement.MovementType.IN,
                        quantity=quantity,
                    )

    def test_failed_movement_rolls_back_transaction(self):
        with self.assertRaises(InsufficientStockError):
            with transaction.atomic():
                receive_stock(self.product.pk, self.warehouse.pk, "4.000")
                issue_stock(self.product.pk, self.warehouse.pk, "5.000")

        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("0.000"))

    def test_saved_movement_cannot_be_changed_or_deleted(self):
        movement = receive_stock(self.product.pk, self.warehouse.pk, "1.000")
        movement.note = "rewritten"

        with self.assertRaises(ValidationError):
            movement.save()
        with self.assertRaises(ValidationError):
            movement.delete()
        with self.assertRaises(ValidationError):
            StockMovement.objects.filter(pk=movement.pk).update(note="queryset edit")
        with self.assertRaises(ValidationError):
            StockMovement.objects.filter(pk=movement.pk).delete()

        movement.refresh_from_db()
        self.assertEqual(movement.note, "")
        self.assertTrue(StockMovement.objects.filter(pk=movement.pk).exists())

    def test_created_by_is_recorded(self):
        user = get_user_model().objects.create_user(username="inventory-operator")

        movement = receive_stock(self.product.pk, self.warehouse.pk, "1.000", created_by=user)

        self.assertEqual(movement.created_by, user)

    def test_admin_can_view_balances_but_cannot_mutate_movement_history(self):
        movement = receive_stock(self.product.pk, self.warehouse.pk, "6.000")
        admin_user = get_user_model().objects.create_superuser(
            username="inventory-admin",
            email="inventory-admin@example.test",
            password="test-password-123",
        )
        client = Client()
        client.force_login(admin_user)

        list_url = "/admin/inventory/stockmovement/"
        response = client.get(list_url, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_list[0]._current_balance, Decimal("6.000"))
        self.assertEqual(client.get(f"{list_url}{movement.pk}/change/", HTTP_HOST="localhost").status_code, 200)
        self.assertEqual(client.get(f"{list_url}add/", HTTP_HOST="localhost").status_code, 403)
        self.assertEqual(client.get(f"{list_url}{movement.pk}/delete/", HTTP_HOST="localhost").status_code, 403)
        self.assertEqual(
            client.post(
                f"{list_url}{movement.pk}/change/",
                {"note": "attempted edit"},
                HTTP_HOST="localhost",
            ).status_code,
            403,
        )


class InventoryConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        category = Category.objects.create(name="Concurrency test category")
        self.product = Product.objects.create(sku="INV-CONCURRENT-001", name="Concurrency test product", category=category)
        self.warehouse = Warehouse.objects.create(name="Concurrency test warehouse")
        receive_stock(self.product.pk, self.warehouse.pk, "10.000")

    def test_parallel_issues_cannot_overdraw_the_balance(self):
        start_together = Barrier(2)

        def issue_seven_units():
            close_old_connections()
            try:
                start_together.wait(timeout=5)
                issue_stock(self.product.pk, self.warehouse.pk, "7.000")
                return "issued"
            except InsufficientStockError:
                return "insufficient"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: issue_seven_units(), range(2)))

        self.assertCountEqual(results, ["issued", "insufficient"])
        self.assertEqual(get_stock_balance(self.product, self.warehouse), Decimal("3.000"))
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.MovementType.OUT).count(), 1)
