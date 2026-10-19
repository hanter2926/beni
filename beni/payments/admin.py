from django.contrib import admin

from .models import OrderCancellationRequest, PaymentAttempt, WebhookEvent


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'checkout_attempt',
        'amount',
        'currency',
        'status',
        'provider_order_id',
        'created_at',
    )
    list_filter = ('status', 'currency', 'created_at')
    search_fields = (
        'provider_order_id',
        'provider_payment_id',
        'checkout_attempt__token',
    )
    readonly_fields = (
        'checkout_attempt',
        'amount',
        'currency',
        'status',
        'provider_order_id',
        'provider_payment_id',
        'created_at',
        'updated_at',
    )


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'event_type', 'received_at')
    list_filter = ('event_type', 'received_at')
    search_fields = ('event_id',)
    readonly_fields = ('event_id', 'event_type', 'received_at')


@admin.register(OrderCancellationRequest)
class OrderCancellationRequestAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'requested_at', 'reviewer', 'reviewed_at')
    list_filter = ('status', 'requested_at', 'reviewed_at')
    search_fields = ('order__order_number', 'order__customer__username')
    readonly_fields = (
        'order',
        'reason',
        'status',
        'reviewer',
        'reviewer_notes',
        'requested_at',
        'reviewed_at',
    )
