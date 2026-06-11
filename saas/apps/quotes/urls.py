from django.urls import path

from . import views

urlpatterns = [
    path("", views.quote_list, name="quote-list"),
    path("nuevo/", views.quote_create, name="quote-create"),
    path("compartir/<uuid:token>/", views.public_quote_detail, name="public-quote-detail"),
    path("compartir/<uuid:token>/pdf/", views.public_quote_pdf, name="public-quote-pdf"),
    path("<int:pk>/", views.quote_detail, name="quote-detail"),
    path("<int:pk>/pdf/", views.quote_pdf, name="quote-pdf"),
    path("<int:pk>/estado/", views.quote_status_update, name="quote-status-update"),
]
