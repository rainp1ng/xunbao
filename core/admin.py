from django.contrib import admin

from .models import MarketListing, Profile, TreasureTask


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "points", "gold", "silver")
    search_fields = ("user__username",)


@admin.register(TreasureTask)
class TreasureTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "value_points", "status", "creator", "assignee", "created_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("title", "creator__username", "assignee__username")


@admin.register(MarketListing)
class MarketListingAdmin(admin.ModelAdmin):
    list_display = ("title", "price_points", "is_active", "seller", "buyer", "created_at", "sold_at")
    list_filter = ("is_active",)
    search_fields = ("title", "seller__username", "buyer__username")

from django.contrib import admin

# Register your models here.
