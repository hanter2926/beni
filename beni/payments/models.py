from django.conf import settings
from django.db import models


class PaymentAttempt(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_AUTHORIZED = 'authorized'
    STATUS_CAPTURED = 'captured'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_AUTHORIZED, 'Authorized'),
        (STATUS_CAPTURED, 'Captured'),
        (STATUS_FAILED, 'Failed'),
    ]

    checkout_attempt = models.ForeignKey(
        'orders.CheckoutAttempt',
        on_delete=models.PROTECT,
        related_name='payment_attempts',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    provider_order_id = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )
    provider_payment_id = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('checkout_attempt', 'created_at')),
        ]


class WebhookEvent(models.Model):
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-received_at', '-id')


class OrderCancellationRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='cancellation_request',
    )
    reason = models.TextField(max_length=1000)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_order_cancellations',
    )
    reviewer_notes = models.TextField(max_length=1000, blank=True, default='')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('status', 'requested_at')
