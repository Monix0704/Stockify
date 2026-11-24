from django.contrib import admin

from .models import Category, Product, Supplier


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_name", "email", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_name", "email", "phone")
    ordering = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "preferred_supplier", "unit", "reorder_level", "is_active")
    list_filter = ("is_active", "category", "unit")
    search_fields = ("sku", "name", "category__name", "preferred_supplier__name")
    autocomplete_fields = ("category", "preferred_supplier")
    list_select_related = ("category", "preferred_supplier")
    ordering = ("name",)
