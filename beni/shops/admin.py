from django.contrib import admin

from .models import Shop


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
	list_display = ('name', 'owner', 'category', 'city', 'state', 'is_active')
	list_filter = ('is_active', 'category', 'state')
	search_fields = ('name', 'owner__username', 'city', 'state', 'postal_code')
	readonly_fields = ('created_at', 'updated_at')
