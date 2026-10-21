from django.conf import settings
from django.db import models

from beni.upload_paths import booking_image_path
from verification.storage import private_storage


class RepairBooking(models.Model):
    STATUS_REQUESTED = 'requested'
    STATUS_ASSIGNED = 'assigned'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_ON_THE_WAY = 'on_the_way'
    STATUS_ARRIVED = 'arrived'
    STATUS_INSPECTION = 'inspection'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_DISPUTED = 'disputed'
    CONTACT_ALLOWED_STATUSES = (
        STATUS_ASSIGNED,
        STATUS_ACCEPTED,
        STATUS_ON_THE_WAY,
        STATUS_ARRIVED,
        STATUS_INSPECTION,
        STATUS_IN_PROGRESS,
        STATUS_COMPLETED,
    )
    WORKER_ADDRESS_VISIBLE_STATUSES = (
        STATUS_ASSIGNED,
        STATUS_ACCEPTED,
        STATUS_ON_THE_WAY,
        STATUS_ARRIVED,
        STATUS_INSPECTION,
        STATUS_IN_PROGRESS,
    )

    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Pending'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_ON_THE_WAY, 'Worker on the way'),
        (STATUS_ARRIVED, 'Worker arrived'),
        (STATUS_INSPECTION, 'Inspection in progress'),
        (STATUS_IN_PROGRESS, 'Repair in progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_DISPUTED, 'Disputed'),
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
    locality = models.CharField(max_length=120, blank=True, default='')
    preferred_contact_method = models.CharField(
        max_length=12,
        choices=(('phone', 'Phone call'), ('whatsapp', 'WhatsApp')),
        default='phone',
    )
    preferred_at = models.DateTimeField()
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def worker_can_view_service_address(self):
        return (
            self.assigned_worker_id is not None
            and self.status in self.WORKER_ADDRESS_VISIBLE_STATUSES
        )

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(
                fields=('customer', 'created_at'),
                name='booking_customer_created_idx',
            ),
            models.Index(
                fields=('assigned_worker', 'status'),
                name='bookings_re_assigne_2d1b47_idx',
            ),
            models.Index(
                fields=('status', 'preferred_at'),
                name='bookings_re_status_5eb4dc_idx',
            ),
        ]

    def __str__(self):
        return f'Repair booking #{self.pk} ({self.get_status_display()})'


class BookingSupportRequest(models.Model):
    TYPE_NOT_RESPONDING = 'not_responding'
    TYPE_LATE_ARRIVAL = 'late_arrival'
    TYPE_BOOKING_PROBLEM = 'booking_problem'
    TYPE_ADMIN_ASSISTANCE = 'admin_assistance'
    TYPE_COMPLAINT = 'complaint'
    TYPE_SAFETY = 'safety'
    TYPE_CHOICES = [
        (TYPE_NOT_RESPONDING, 'Other party is not responding'),
        (TYPE_LATE_ARRIVAL, 'Late arrival'),
        (TYPE_BOOKING_PROBLEM, 'Problem with this booking'),
        (TYPE_ADMIN_ASSISTANCE, 'Request admin assistance'),
        (TYPE_COMPLAINT, 'Submit a complaint'),
        (TYPE_SAFETY, 'Safety concern'),
    ]
    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    booking = models.ForeignKey(
        RepairBooking,
        on_delete=models.PROTECT,
        related_name='support_requests',
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_support_requests',
    )
    request_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    description = models.TextField(max_length=2000)
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        indexes = [
            models.Index(fields=('booking', 'created_at')),
            models.Index(fields=('status', 'created_at')),
        ]

    def __str__(self):
        return f'{self.get_request_type_display()} for booking #{self.booking_id}'


class BookingAssignmentEvent(models.Model):
    booking = models.ForeignKey(
        RepairBooking,
        on_delete=models.PROTECT,
        related_name='assignment_events',
    )
    assigned_worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_assignment_events',
    )
    previous_worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='previous_repair_assignment_events',
        null=True,
        blank=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_repair_assignment_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')
        indexes = [
            models.Index(
                fields=('booking', 'created_at'),
                name='booking_assign_history_idx',
            ),
            models.Index(
                fields=('assigned_worker', 'created_at'),
                name='booking_assign_worker_idx',
            ),
        ]

    def __str__(self):
        return f'Assignment for repair booking #{self.booking_id}'


class RepairBookingImage(models.Model):
    TYPE_CUSTOMER_CONDITION = 'customer_condition'
    TYPE_WORKER_VISIT_PROOF = 'worker_visit_proof'
    TYPE_REPAIR_PROGRESS = 'repair_progress'
    TYPE_COMPLETED_WORK = 'completed_work'
    TYPE_CHOICES = [
        (TYPE_CUSTOMER_CONDITION, 'Condition at request'),
        (TYPE_WORKER_VISIT_PROOF, 'Visit proof'),
        (TYPE_REPAIR_PROGRESS, 'Repair progress'),
        (TYPE_COMPLETED_WORK, 'Completed repair'),
    ]

    booking = models.ForeignKey(
        RepairBooking,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(
        upload_to=booking_image_path,
        storage=private_storage,
    )
    image_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='repair_booking_images',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')
        indexes = [
            models.Index(fields=('booking', 'created_at')),
        ]

    def __str__(self):
        return f'{self.get_image_type_display()} for repair booking #{self.booking_id}'
