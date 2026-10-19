from django.contrib import admin

from .models import BookingSupportRequest, RepairBooking


@admin.register(RepairBooking)
class RepairBookingAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'assigned_worker',
        'service_category',
        'status',
        'preferred_at',
        'created_at',
    )
    list_filter = ('status', 'preferred_contact_method', 'created_at')
    search_fields = ('customer__username', 'service_category', 'locality')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BookingSupportRequest)
class BookingSupportRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'booking',
        'reporter',
        'request_type',
        'status',
        'created_at',
    )
    list_filter = ('status', 'request_type', 'created_at')
    search_fields = ('booking__id', 'reporter__username', 'description')
    readonly_fields = ('booking', 'reporter', 'request_type', 'description', 'created_at')
