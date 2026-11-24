from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("warehouses/", views.warehouse_list, name="warehouses"),
    path("movements/", views.movement_list, name="movements"),
    path("receive/", views.receive, name="receive"),
    path("issue/", views.issue, name="issue"),
]
