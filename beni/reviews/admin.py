from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'rating',
        'status',
        'created_at',
        'moderator',
    )
    list_filter = ('status', 'rating')
    search_fields = (
        'customer__username',
        'body',
        'order__order_number',
    )
    readonly_fields = ('created_at', 'updated_at')
