from django.contrib import admin

from .models import Customer, Vehicle


class VehicleInline(admin.TabularInline):
    model = Vehicle
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "phone", "email", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("name", "phone", "email", "tax_id")
    inlines = (VehicleInline,)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("license_plate", "make", "model", "customer", "organization")
    list_filter = ("organization", "make")
    search_fields = ("license_plate", "make", "model", "customer__name")
