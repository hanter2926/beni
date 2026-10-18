from django.contrib import admin

from .models import WalletAccount, WalletLedgerEntry


@admin.register(WalletAccount)
class WalletAccountAdmin(admin.ModelAdmin):
    list_display = ('owner', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('owner__username',)
    readonly_fields = ('owner', 'role', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletLedgerEntry)
class WalletLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'entry_type', 'amount_minor', 'reference_key', 'created_at')
    list_filter = ('entry_type', 'created_at')
    search_fields = ('wallet__owner__username', 'reference_key')
    readonly_fields = (
        'wallet',
        'entry_type',
        'amount_minor',
        'reference_key',
        'actor',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
