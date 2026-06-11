from django.urls import path

from . import views

urlpatterns = [
    path("", views.customer_list, name="customer-list"),
    path("nuevo/", views.customer_create, name="customer-create"),
    path("<int:pk>/", views.customer_detail, name="customer-detail"),
    path("<int:pk>/editar/", views.customer_update, name="customer-update"),
    path("<int:pk>/archivar/", views.customer_archive, name="customer-archive"),
    path("<int:customer_pk>/vehiculos/nuevo/", views.vehicle_create, name="vehicle-create"),
    path("vehiculos/<int:pk>/editar/", views.vehicle_update, name="vehicle-update"),
    path("vehiculos/<int:pk>/archivar/", views.vehicle_archive, name="vehicle-archive"),
]
