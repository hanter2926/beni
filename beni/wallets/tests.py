from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import WalletAccount, WalletLedgerEntry


class WalletFoundationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
        self.worker_group, _ = Group.objects.get_or_create(name='Repair Worker')
        self.shopkeeper = user_model.objects.create_user(username='wallet-shopkeeper')
        self.shopkeeper.groups.add(self.shopkeeper_group)
        self.worker = user_model.objects.create_user(username='wallet-worker')
        self.worker.groups.add(self.worker_group)
        self.other_shopkeeper = user_model.objects.create_user(
            username='wallet-other-shopkeeper',
        )
        self.other_shopkeeper.groups.add(self.shopkeeper_group)
        self.shopkeeper_wallet = WalletAccount.objects.create(
            owner=self.shopkeeper,
            role=WalletAccount.ROLE_SHOPKEEPER,
        )
        self.worker_wallet = WalletAccount.objects.create(
            owner=self.worker,
            role=WalletAccount.ROLE_REPAIR_WORKER,
        )
        self.entry = WalletLedgerEntry.objects.create(
            wallet=self.shopkeeper_wallet,
            entry_type=WalletLedgerEntry.TYPE_EARNING_CREDIT,
            amount_minor=1250,
            reference_key='future-source:one',
        )

    def test_wallet_history_is_owner_and_role_scoped(self):
        self.client.force_login(self.shopkeeper)

        response = self.client.get(reverse('wallets:shopkeeper'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Earnings and withdrawals are not enabled')
        self.assertContains(response, self.entry.reference_key)
        self.assertNotContains(response, 'wallet-worker')

        self.client.force_login(self.other_shopkeeper)
        other_response = self.client.get(reverse('wallets:shopkeeper'))
        self.assertEqual(other_response.status_code, 200)
        self.assertNotContains(other_response, self.entry.reference_key)

    def test_wallet_roles_are_separate_and_wrong_role_route_is_forbidden(self):
        self.assertNotEqual(self.shopkeeper_wallet.pk, self.worker_wallet.pk)
        self.client.force_login(self.shopkeeper)

        response = self.client.get(reverse('wallets:repair_worker'))

        self.assertEqual(response.status_code, 403)

    def test_ledger_entries_reject_mutation_and_deletion(self):
        self.entry.amount_minor = 999999

        with self.assertRaises(ValidationError):
            self.entry.save()
        with self.assertRaises(ValidationError):
            self.entry.delete()
        with self.assertRaises(ValidationError):
            WalletLedgerEntry.objects.filter(pk=self.entry.pk).update(
                amount_minor=999999,
            )
        with self.assertRaises(ValidationError):
            WalletLedgerEntry.objects.bulk_update(
                [self.entry],
                ('amount_minor',),
            )
        with self.assertRaises(ValidationError):
            WalletLedgerEntry.objects.filter(pk=self.entry.pk).delete()

        self.entry.refresh_from_db()
        self.assertEqual(self.entry.amount_minor, 1250)

    def test_wallet_account_is_unique_per_owner_and_role(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                WalletAccount.objects.create(
                    owner=self.shopkeeper,
                    role=WalletAccount.ROLE_SHOPKEEPER,
                )
