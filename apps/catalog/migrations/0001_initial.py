import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создана")),
            ],
            options={"verbose_name": "категория", "verbose_name_plural": "категории", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180, unique=True, verbose_name="Название компании")),
                ("contact_name", models.CharField(blank=True, max_length=160, verbose_name="Контактное лицо")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Электронная почта")),
                ("phone", models.CharField(blank=True, max_length=40, verbose_name="Телефон")),
                ("notes", models.TextField(blank=True, verbose_name="Заметки")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Добавлен")),
            ],
            options={"verbose_name": "поставщик", "verbose_name_plural": "поставщики", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku", models.CharField(max_length=64, unique=True, verbose_name="Артикул")),
                ("name", models.CharField(max_length=180, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("unit", models.CharField(choices=[("piece", "шт."), ("kg", "кг"), ("liter", "л"), ("meter", "м")], default="piece", max_length=12, verbose_name="Единица измерения")),
                ("reorder_level", models.DecimalField(decimal_places=3, default=0, help_text="Уровень, ниже которого товар считается требующим пополнения.", max_digits=12, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Порог пополнения")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Добавлен")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="catalog.category", verbose_name="Категория")),
                ("preferred_supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="catalog.supplier", verbose_name="Основной поставщик")),
            ],
            options={"verbose_name": "товар", "verbose_name_plural": "товары", "ordering": ["name", "sku"]},
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(condition=models.Q(("reorder_level__gte", 0)), name="product_reorder_level_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["name"], name="catalog_pro_name_f603c0_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["category", "is_active"], name="catalog_pro_categor_891fe8_idx"),
        ),
    ]
