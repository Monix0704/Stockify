from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.analytics_dashboard, name="dashboard"),
    path("stock/", views.stock_report, name="stock"),
    path("stock.csv", views.stock_export, name="stock_export"),
    path("movements/", views.movement_report, name="movements"),
    path("movements.csv", views.movement_export, name="movement_export"),
]
