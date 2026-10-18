from django.contrib import admin

from .models import CheckoutAttempt, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    max_num = 0
    readonly_fields = (
        'product',
        'product_name',
        'product_category',
        'product_sku',
        'unit_price',
        'quantity',
        'line_total',
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'shop', 'status', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('order_number', 'customer__username', 'shop__name')
    readonly_fields = tuple(field.name for field in Order._meta.fields)
    inlines = (OrderItemInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CheckoutAttempt)
class CheckoutAttemptAdmin(admin.ModelAdmin):
    list_display = ('token', 'customer', 'created_at')
    search_fields = ('token', 'customer__username')
    readonly_fields = ('customer', 'token', 'cart_digest', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
