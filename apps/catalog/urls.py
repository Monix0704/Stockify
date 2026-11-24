from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("products/", views.product_list, name="products"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("categories/", views.category_list, name="categories"),
    path("suppliers/", views.supplier_list, name="suppliers"),
]
