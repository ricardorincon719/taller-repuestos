from django.contrib import admin

from .models import Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "next_quote_number", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "email", "tax_id")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (MembershipInline,)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "organization__name")
