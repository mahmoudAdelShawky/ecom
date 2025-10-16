from django.contrib import admin
from .models import Item, Review
from import_export.admin import ExportActionMixin
from .models import Category, Item

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")



class ItemAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = (
        "vendor",
        "category",
        "item_title",
        "item_image",
        "item_price",
        "item_description",
        "item_stock",
        "item_orders",
        "item_discount",
    )


class ReviewAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("item", "owner", "audit", "rating")


admin.site.register(Item, ItemAdmin)
admin.site.register(Review, ReviewAdmin)
