from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import Q


class Review(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PUBLISHED = 'published'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending moderation'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_REJECTED, 'Not published'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='marketplace_reviews',
    )
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='customer_review',
        null=True,
        blank=True,
    )
    booking = models.OneToOneField(
        'bookings.RepairBooking',
        on_delete=models.PROTECT,
        related_name='customer_review',
        null=True,
        blank=True,
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    body = models.TextField(
        blank=True,
        validators=[MaxLengthValidator(2000)],
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='moderated_marketplace_reviews',
        null=True,
        blank=True,
    )
    moderation_note = models.TextField(
        blank=True,
        validators=[MaxLengthValidator(2000)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name='review_rating_1_to_5',
            ),
            models.CheckConstraint(
                condition=(
                    Q(order__isnull=False, booking__isnull=True)
                    | Q(order__isnull=True, booking__isnull=False)
                ),
                name='review_one_source_only',
            ),
        ]
        indexes = [
            models.Index(fields=('status', 'created_at')),
        ]

    def clean(self):
        super().clean()
        if bool(self.order_id) == bool(self.booking_id):
            raise ValidationError(
                'A review must reference exactly one order or repair booking.'
            )
        target_customer_id = (
            self.order.customer_id if self.order_id
            else self.booking.customer_id
        )
        if self.customer_id and self.customer_id != target_customer_id:
            raise ValidationError(
                'The review customer must own the related order or booking.'
            )

    @property
    def reviewed_shop(self):
        return self.order.shop if self.order_id else None

    @property
    def reviewed_worker(self):
        return self.booking.assigned_worker if self.booking_id else None

    def __str__(self):
        target = (
            f'order {self.order_id}'
            if self.order_id
            else f'repair booking {self.booking_id}'
        )
        return f'{self.rating}/5 review for {target}'
