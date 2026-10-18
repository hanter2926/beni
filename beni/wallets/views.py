from django.shortcuts import render

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    role_group_required,
)

from .models import WalletAccount


def _wallet_history(request, role):
    wallet = (
        WalletAccount.objects.filter(owner=request.user, role=role)
        .first()
    )
    entries = wallet.entries.all() if wallet is not None else ()
    return render(
        request,
        'wallets/account.html',
        {
            'wallet': wallet,
            'entries': entries,
            'wallet_role': role,
            'role_label': (
                'Shopkeeper'
                if role == WalletAccount.ROLE_SHOPKEEPER
                else 'Repair worker'
            ),
            'active_nav': 'wallet',
        },
    )


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_wallet(request):
    return _wallet_history(request, WalletAccount.ROLE_SHOPKEEPER)


@role_group_required(REPAIR_WORKER_GROUP)
def repair_worker_wallet(request):
    return _wallet_history(request, WalletAccount.ROLE_REPAIR_WORKER)
