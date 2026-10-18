from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ImmutableWalletLedgerQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Wallet ledger entries are immutable.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('Wallet ledger entries are immutable.')

    def delete(self):
        raise ValidationError('Wallet ledger entries cannot be deleted.')


class WalletAccount(models.Model):
    ROLE_SHOPKEEPER = 'shopkeeper'
    ROLE_REPAIR_WORKER = 'repair_worker'
    ROLE_CHOICES = [
        (ROLE_SHOPKEEPER, 'Shopkeeper'),
        (ROLE_REPAIR_WORKER, 'Repair Worker'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet_accounts',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('owner', 'role'),
                name='wallet_owner_role_unique',
            ),
        ]

    def __str__(self):
        return f'{self.get_role_display()} wallet for {self.owner_id}'


class WalletLedgerEntry(models.Model):
    objects = ImmutableWalletLedgerQuerySet.as_manager()

    TYPE_EARNING_CREDIT = 'earning_credit'
    TYPE_WITHDRAWAL_RESERVATION = 'withdrawal_reservation'
    TYPE_RESERVATION_RELEASE = 'reservation_release'
    TYPE_WITHDRAWAL_DEBIT = 'withdrawal_debit'
    TYPE_ADJUSTMENT = 'adjustment'
    TYPE_CHOICES = [
        (TYPE_EARNING_CREDIT, 'Earning credit'),
        (TYPE_WITHDRAWAL_RESERVATION, 'Withdrawal reservation'),
        (TYPE_RESERVATION_RELEASE, 'Reservation release'),
        (TYPE_WITHDRAWAL_DEBIT, 'Completed withdrawal'),
        (TYPE_ADJUSTMENT, 'Adjustment'),
    ]

    wallet = models.ForeignKey(
        WalletAccount,
        on_delete=models.PROTECT,
        related_name='entries',
    )
    entry_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    amount_minor = models.BigIntegerField()
    reference_key = models.CharField(max_length=200)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet_ledger_actions',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        constraints = [
            models.UniqueConstraint(
                fields=('wallet', 'reference_key'),
                name='wallet_ledger_reference_unique',
            ),
            models.CheckConstraint(
                condition=~Q(amount_minor=0),
                name='wallet_ledger_amount_nonzero',
            ),
        ]
        indexes = [
            models.Index(
                fields=('wallet', 'created_at'),
                name='wallet_ledger_history_idx',
            ),
            models.Index(
                fields=('entry_type', 'created_at'),
                name='wallet_ledger_type_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Wallet ledger entries are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Wallet ledger entries cannot be deleted.')

    def __str__(self):
        return f'{self.entry_type} ({self.amount_minor} minor units)'
