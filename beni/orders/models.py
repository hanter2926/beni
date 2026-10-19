from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


class CheckoutAttempt(models.Model):
    PAYMENT_METHOD_COD = 'cod'
    PAYMENT_METHOD_RAZORPAY = 'razorpay'
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_COD, 'Cash on delivery'),
        (PAYMENT_METHOD_RAZORPAY, 'Online payment'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='checkout_attempts',
        db_index=False,
    )
    token = models.UUIDField(unique=True, editable=False)
    cart_digest = models.CharField(max_length=64)
    payment_method = models.CharField(
        max_length=12,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_COD,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=('customer', 'created_at'))]

    def __str__(self):
        return str(self.token)


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PROCESSING = 'processing'
    STATUS_READY_FOR_PICKUP = 'ready_for_pickup'
    STATUS_OUT_FOR_DELIVERY = 'out_for_delivery'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'

    PAYMENT_NOT_STARTED = 'not_started'
    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID = 'paid'
    PAYMENT_FAILED = 'failed'
    PAYMENT_REFUNDED = 'refunded'

    ORDER_STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY_FOR_PICKUP, 'Ready for pickup'),
        (STATUS_OUT_FOR_DELIVERY, 'Out for delivery'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUNDED, 'Refunded'),
    ]
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_NOT_STARTED, 'Not started'),
        (PAYMENT_PENDING, 'Pending'),
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_FAILED, 'Failed'),
        (PAYMENT_REFUNDED, 'Refunded'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
        db_index=False,
    )
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='orders',
        db_index=False,
    )
    checkout_attempt = models.ForeignKey(
        CheckoutAttempt,
        on_delete=models.PROTECT,
        related_name='orders',
        db_index=False,
    )
    order_number = models.CharField(max_length=40, unique=True)
    status = models.CharField(
        max_length=24,
        choices=ORDER_STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=False,
    )
    payment_status = models.CharField(
        max_length=18,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_NOT_STARTED,
        db_index=False,
    )
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=30)
    address_line1 = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    delivery_notes = models.TextField(blank=True, default='')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = [
            models.UniqueConstraint(
                fields=('checkout_attempt', 'shop'),
                name='order_attempt_shop_unique',
            ),
            models.CheckConstraint(
                condition=Q(total__gte=Decimal('0.00')),
                name='order_total_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=Decimal('0.00')),
                name='order_subtotal_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(delivery_fee__gte=Decimal('0.00')),
                name='order_delivery_fee_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(service_fee__gte=Decimal('0.00')),
                name='order_service_fee_nonnegative',
            ),
        ]
        indexes = [
            models.Index(fields=('customer', 'created_at')),
            models.Index(fields=('shop', 'status')),
            models.Index(fields=('status', 'payment_status')),
        ]

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        db_index=False,
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    product_name = models.CharField(max_length=150)
    product_category = models.CharField(max_length=100, blank=True, default='')
    product_sku = models.CharField(max_length=64, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('order_id', 'id')
        constraints = [
            models.CheckConstraint(
                condition=Q(unit_price__gte=Decimal('0.00')),
                name='orderitem_unit_price_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name='orderitem_quantity_positive',
            ),
            models.CheckConstraint(
                condition=Q(line_total__gte=Decimal('0.00')),
                name='orderitem_line_total_nonnegative',
            ),
        ]
        indexes = [models.Index(fields=('order', 'product'))]
