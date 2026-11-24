from decimal import Decimal

from django import forms

from apps.catalog.models import Product
from .models import Warehouse


class StockMovementForm(forms.Form):
    warehouse = forms.ModelChoiceField(
        label="Склад",
        queryset=Warehouse.objects.none(),
        empty_label="Выберите склад",
    )
    product = forms.ModelChoiceField(
        label="Товар",
        queryset=Product.objects.none(),
        empty_label="Выберите товар",
    )
    quantity = forms.DecimalField(
        label="Количество",
        min_value=Decimal("0.001"),
        max_digits=12,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"step": "0.001", "placeholder": "Например, 12.500"}),
    )
    note = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Причина или номер документа"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True).order_by("name")
        self.fields["product"].queryset = Product.objects.filter(is_active=True).order_by("name")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
