from django.urls import path

from . import views

urlpatterns = [
    path("", views.billing_status, name="billing-status"),
    path("portal/", views.billing_portal, name="billing-portal"),
    path("webhook/paddle/", views.paddle_webhook, name="paddle-webhook"),
    path(
        "webhooks/paddle/",
        views.paddle_webhook,
        name="paddle-webhook-legacy",
    ),
]
