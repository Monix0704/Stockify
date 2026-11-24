from datetime import timedelta

from django import forms
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.inventory.models import StockMovement, Warehouse


class DateRangeForm(forms.Form):
    date_from = forms.DateField(
        label="С даты",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        label="По дату",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to:
            if date_from > date_to:
                self.add_error("date_to", "Дата окончания должна быть не раньше даты начала.")
            elif (date_to - date_from).days > 365:
                self.add_error("date_to", "Для диаграммы выберите период не длиннее одного года.")
        return cleaned_data


class AnalyticsPeriodForm(DateRangeForm):
    def __init__(self, *args, **kwargs):
        if not args and "initial" not in kwargs:
            today = timezone.localdate()
            kwargs["initial"] = {"date_from": today - timedelta(days=29), "date_to": today}
        super().__init__(*args, **kwargs)


class StockReportFilterForm(forms.Form):
    warehouse = forms.ModelChoiceField(
        label="Склад",
        queryset=Warehouse.objects.order_by("name"),
        required=False,
        empty_label="Все склады",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    category = forms.ModelChoiceField(
        label="Категория",
        queryset=Category.objects.order_by("name"),
        required=False,
        empty_label="Все категории",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    product = forms.ModelChoiceField(
        label="Товар",
        queryset=Product.objects.order_by("name"),
        required=False,
        empty_label="Все товары",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class MovementReportFilterForm(forms.Form):
    date_from = forms.DateField(
        label="С даты",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        label="По дату",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    warehouse = forms.ModelChoiceField(
        label="Склад",
        queryset=Warehouse.objects.order_by("name"),
        required=False,
        empty_label="Все склады",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    product = forms.ModelChoiceField(
        label="Товар",
        queryset=Product.objects.order_by("name"),
        required=False,
        empty_label="Все товары",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    movement_type = forms.ChoiceField(
        label="Тип операции",
        choices=[("", "Все типы"), *StockMovement.MovementType.choices],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "Дата окончания должна быть не раньше даты начала.")
        return cleaned_data
