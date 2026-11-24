from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalog.models import Product


class ImmutableStockMovementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("История движений неизменяема. Создайте корректирующую операцию.")

    def delete(self):
        raise ValidationError("Историю движений нельзя удалять. Создайте корректирующую операцию.")


class Warehouse(models.Model):
    name = models.CharField("Название", max_length=160, unique=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "склад"
        verbose_name_plural = "склады"

    def __str__(self):
        return self.name


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = "IN", "Поступление"
        OUT = "OUT", "Списание"

    product = models.ForeignKey(
        Product,
        verbose_name="Товар",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        verbose_name="Склад",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    movement_type = models.CharField("Тип движения", max_length=3, choices=MovementType.choices)
    quantity = models.DecimalField(
        "Количество",
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    note = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Дата операции", auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Операцию выполнил",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    objects = ImmutableStockMovementQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "складское движение"
        verbose_name_plural = "складские движения"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="stock_movement_quantity_positive"),
            models.CheckConstraint(
                condition=models.Q(movement_type__in=["IN", "OUT"]),
                name="stock_movement_type_valid",
            ),
        ]
        indexes = [models.Index(fields=["product", "warehouse", "created_at"])]

    def __str__(self):
        return f"{self.get_movement_type_display()}: {self.product} — {self.quantity}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("История движений неизменяема. Создайте корректирующую операцию.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Историю движений нельзя удалять. Создайте корректирующую операцию.")
