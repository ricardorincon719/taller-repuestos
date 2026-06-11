from django.contrib import admin

from .models import Quote, QuoteItem


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    readonly_fields = ("line_total",)

    @admin.display(description="Total")
    def line_total(self, obj):
        return obj.total_amount if obj.pk else "-"


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "display_number",
        "organization",
        "customer",
        "status",
        "total_amount",
        "created_at",
    )
    list_filter = ("organization", "status")
    search_fields = ("customer__name", "number", "vehicle__license_plate")
    readonly_fields = (
        "legacy_source",
        "legacy_id",
        "items_amount",
        "total_amount",
        "created_at",
        "updated_at",
    )
    inlines = (QuoteItemInline,)


@admin.register(QuoteItem)
class QuoteItemAdmin(admin.ModelAdmin):
    list_display = ("description", "quote", "quantity", "unit_price", "total_amount")
    search_fields = ("description", "quote__customer__name")
