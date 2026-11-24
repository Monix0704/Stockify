from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)
    description = models.TextField("Описание", blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "категория"
        verbose_name_plural = "категории"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField("Название компании", max_length=180, unique=True)
    contact_name = models.CharField("Контактное лицо", max_length=160, blank=True)
    email = models.EmailField("Электронная почта", blank=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    notes = models.TextField("Заметки", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "поставщик"
        verbose_name_plural = "поставщики"

    def __str__(self):
        return self.name


class Product(models.Model):
    class Unit(models.TextChoices):
        PIECE = "piece", "шт."
        KILOGRAM = "kg", "кг"
        LITER = "liter", "л"
        METER = "meter", "м"

    sku = models.CharField("Артикул", max_length=64, unique=True)
    name = models.CharField("Название", max_length=180)
    description = models.TextField("Описание", blank=True)
    category = models.ForeignKey(
        Category,
        verbose_name="Категория",
        on_delete=models.PROTECT,
        related_name="products",
    )
    preferred_supplier = models.ForeignKey(
        Supplier,
        verbose_name="Основной поставщик",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    unit = models.CharField("Единица измерения", max_length=12, choices=Unit.choices, default=Unit.PIECE)
    reorder_level = models.DecimalField(
        "Порог пополнения",
        max_digits=12,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Уровень, ниже которого товар считается требующим пополнения.",
    )
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ["name", "sku"]
        verbose_name = "товар"
        verbose_name_plural = "товары"
        constraints = [
            models.CheckConstraint(condition=models.Q(reorder_level__gte=0), name="product_reorder_level_nonnegative"),
        ]
        indexes = [models.Index(fields=["name"]), models.Index(fields=["category", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.sku})"
