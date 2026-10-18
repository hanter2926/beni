from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from beni.upload_paths import verification_document_path
from .storage import private_storage

class VerificationApplication(models.Model):
    TYPE_SHOPKEEPER = 'shopkeeper'
    TYPE_REPAIR_WORKER = 'repair_worker'
    TYPE_CHOICES = [
        (TYPE_SHOPKEEPER, 'Shopkeeper'),
        (TYPE_REPAIR_WORKER, 'Repair Worker'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    CHECK_NOT_SUBMITTED = 'not_submitted'
    CHECK_PENDING = 'pending'
    CHECK_VERIFIED = 'verified'
    CHECK_REJECTED = 'rejected'
    CHECK_CHOICES = [
        (CHECK_NOT_SUBMITTED, 'Not submitted'),
        (CHECK_PENDING, 'Pending'),
        (CHECK_VERIFIED, 'Verified'),
        (CHECK_REJECTED, 'Rejected'),
    ]

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='verification_applications',
    )
    shop = models.OneToOneField(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='verification_applications',
        null=True,
        blank=True,
    )
    worker_application_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    application_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    phone_status = models.CharField(
        max_length=16,
        choices=CHECK_CHOICES,
        default=CHECK_PENDING,
    )
    aadhaar_status = models.CharField(
        max_length=16,
        choices=CHECK_CHOICES,
        default=CHECK_NOT_SUBMITTED,
    )
    pan_status = models.CharField(
        max_length=16,
        choices=CHECK_CHOICES,
        default=CHECK_NOT_SUBMITTED,
    )
    bank_status = models.CharField(
        max_length=16,
        choices=CHECK_CHOICES,
        default=CHECK_NOT_SUBMITTED,
    )
    face_status = models.CharField(
        max_length=16,
        choices=CHECK_CHOICES,
        default=CHECK_NOT_SUBMITTED,
    )
    decision_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_verification_applications',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('status', 'created_at', 'pk')

    def clean(self):
        super().clean()
        if self.application_type == self.TYPE_SHOPKEEPER and not self.shop_id:
            raise ValidationError('A shopkeeper application must reference a shop.')
        if (
            self.application_type == self.TYPE_SHOPKEEPER
            and self.shop_id
            and self.shop.owner_id != self.applicant_id
        ):
            raise ValidationError(
                'A shopkeeper application must belong to the shop owner.'
            )
        if self.application_type == self.TYPE_REPAIR_WORKER and self.shop_id:
            raise ValidationError('A Repair Worker application cannot reference a shop.')

    def save(self, *args, **kwargs):
        if self.application_type == self.TYPE_REPAIR_WORKER:
            if self.shop_id:
                raise ValidationError(
                    'A Repair Worker application cannot reference a shop.'
                )
            if self.applicant_id:
                self.worker_application_key = f'repair-worker:{self.applicant_id}'
        elif self.application_type == self.TYPE_SHOPKEEPER:
            if not self.shop_id:
                raise ValidationError(
                    'A shopkeeper application must reference a shop.'
                )
            if self.shop.owner_id != self.applicant_id:
                raise ValidationError(
                    'A shopkeeper application must belong to the shop owner.'
                )
            self.worker_application_key = None
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_application_type_display()} verification #{self.pk}'


class VerificationDecision(models.Model):
    application = models.ForeignKey(
        VerificationApplication,
        on_delete=models.PROTECT,
        related_name='decisions',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='verification_decisions',
    )
    status = models.CharField(
        max_length=12,
        choices=VerificationApplication.STATUS_CHOICES,
    )
    phone_status = models.CharField(
        max_length=16,
        choices=VerificationApplication.CHECK_CHOICES,
    )
    aadhaar_status = models.CharField(
        max_length=16,
        choices=VerificationApplication.CHECK_CHOICES,
    )
    pan_status = models.CharField(
        max_length=16,
        choices=VerificationApplication.CHECK_CHOICES,
    )
    bank_status = models.CharField(
        max_length=16,
        choices=VerificationApplication.CHECK_CHOICES,
    )
    face_status = models.CharField(
        max_length=16,
        choices=VerificationApplication.CHECK_CHOICES,
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'Decision for verification #{self.application_id}'


class VerificationDocument(models.Model):
    TYPE_IDENTITY = 'identity'
    TYPE_ADDRESS = 'address'
    TYPE_TAX = 'tax'
    TYPE_BANK = 'bank'
    TYPE_BUSINESS = 'business'
    TYPE_QUALIFICATION = 'qualification'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_IDENTITY, 'Identity document'),
        (TYPE_ADDRESS, 'Address document'),
        (TYPE_TAX, 'Tax document'),
        (TYPE_BANK, 'Bank document'),
        (TYPE_BUSINESS, 'Business document'),
        (TYPE_QUALIFICATION, 'Qualification document'),
        (TYPE_OTHER, 'Other supporting document'),
    ]

    application = models.ForeignKey(
        VerificationApplication,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    file = models.FileField(
        upload_to=verification_document_path,
        storage=private_storage,
    )
    document_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='verification_documents',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('uploaded_at', 'pk')

    def __str__(self):
        return f'{self.get_document_type_display()} for application #{self.application_id}'
