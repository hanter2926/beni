from django.conf import settings
from django.db import models


class RepairBooking(models.Model):
    STATUS_REQUESTED = 'requested'
    STATUS_ASSIGNED = 'assigned'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_bookings',
    )
    assigned_worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_repair_bookings',
        null=True,
        blank=True,
    )
    service_category = models.CharField(max_length=100)
    problem_description = models.TextField()
    service_address = models.TextField(max_length=500)
    preferred_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('customer', 'created_at')),
            models.Index(fields=('assigned_worker', 'status')),
            models.Index(fields=('status', 'preferred_at')),
        ]

    def __str__(self):
        return f'Repair booking #{self.pk} ({self.get_status_display()})'
