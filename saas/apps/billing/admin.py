from django.contrib import admin

from .models import Subscription, WebhookEvent


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("organization", "plan", "status", "current_period_ends_at")
    list_filter = ("plan", "status")
    search_fields = ("organization__name", "provider_customer_id")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider_event_id", "event_type", "processed_at", "created_at")
    search_fields = ("provider_event_id", "event_type")
    readonly_fields = ("provider_event_id", "event_type", "payload", "created_at")
