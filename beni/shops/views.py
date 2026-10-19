from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.roles import SHOPKEEPER_GROUP, role_group_required
from notifications.services import notify_active_staff
from products.services import eligible_shop_verifications

from .forms import ShopBankDetailsForm, ShopForm
from .models import Shop, ShopBankDetails
from verification.models import VerificationApplication


REVIEW_REQUIRED_SHOP_FIELDS = {
    'name',
    'category',
    'phone',
    'address',
    'city',
    'state',
    'postal_code',
}


def _require_verification_review_after_identity_change(*, form, shop):
    if not REVIEW_REQUIRED_SHOP_FIELDS.intersection(form.changed_data):
        return False

    application = VerificationApplication.objects.select_for_update().filter(
        shop=shop,
        status=VerificationApplication.STATUS_APPROVED,
    ).first()
    if application is None:
        return False

    shop.is_active = False
    shop.save(update_fields=('is_active', 'updated_at'))
    application.status = VerificationApplication.STATUS_PENDING
    application.decision_reason = (
        'Shop identity or contact details changed and require staff review.'
    )
    application.reviewed_by = None
    application.save(
        update_fields=('status', 'decision_reason', 'reviewed_by', 'updated_at')
    )
    notify_active_staff(
        event_key=(
            f'verification-application:{application.pk}:'
            f'shop-details:{shop.updated_at.isoformat()}:admin'
        ),
        title='Updated shop details need review',
        message='A verified Shopkeeper changed identity or contact details.',
        destination_name='verification:admin_list',
    )
    return True


@role_group_required(SHOPKEEPER_GROUP)
def shop_list(request):
    shops = list(
        Shop.objects.filter(owner=request.user)
        .select_related('verification_applications')
        .prefetch_related('photos')
    )
    owned_shop_ids = tuple(shop.pk for shop in shops)
    eligible_shop_ids = set(
        eligible_shop_verifications(
            shop_ids=owned_shop_ids,
        ).values_list('shop_id', flat=True)
    )
    for shop in shops:
        try:
            shop.verification_application = shop.verification_applications
        except VerificationApplication.DoesNotExist:
            shop.verification_application = None
        shop.marketable = shop.is_active and shop.pk in eligible_shop_ids
    return render(
        request,
        'shopkeeper/shops/list.html',
        {
            'shops': shops,
            'role_label': 'Shopkeeper',
            'active_nav': 'shops',
        },
    )


@role_group_required(SHOPKEEPER_GROUP)
def shop_create(request):
    form = ShopForm(request.POST or None, request.FILES or None)
    bank_form = ShopBankDetailsForm(request.POST or None)
    if (
        request.method == 'POST'
        and form.is_valid()
        and bank_form.is_valid()
    ):
        with transaction.atomic():
            shop = form.save(commit=False)
            shop.owner = request.user
            shop.is_active = False
            shop.save()
            form.save_photos(shop)
            bank_form.save_for_shop(shop)
        messages.success(
            request,
            'Shop created. Submit its verification application before it can be listed.',
        )
        return redirect('verification:shopkeeper_application', shop_id=shop.pk)

    return render(
        request,
        'shopkeeper/shops/form.html',
        {
            'form': form,
            'bank_form': bank_form,
            'role_label': 'Shopkeeper',
            'page_title': 'Add a shop',
            'active_nav': 'shops',
        },
    )


@role_group_required(SHOPKEEPER_GROUP)
def shop_update(request, shop_id):
    shop = get_object_or_404(Shop, pk=shop_id, owner=request.user)
    form = ShopForm(request.POST or None, request.FILES or None, instance=shop)
    bank_details = ShopBankDetails.objects.filter(shop=shop).first()
    bank_form = ShopBankDetailsForm(
        request.POST or None,
        instance=bank_details,
    )
    if (
        request.method == 'POST'
        and form.is_valid()
        and bank_form.is_valid()
    ):
        with transaction.atomic():
            shop = form.save()
            bank_form.save_for_shop(shop)
            needs_review = _require_verification_review_after_identity_change(
                form=form,
                shop=shop,
            )
        if needs_review:
            messages.info(
                request,
                'Shop identity details changed. Staff review is required before '
                'the shop can be listed again.',
            )
        else:
            messages.success(request, 'Shop details updated.')
        return redirect('shops:list')

    return render(
        request,
        'shopkeeper/shops/form.html',
        {
            'form': form,
            'bank_form': bank_form,
            'role_label': 'Shopkeeper',
            'page_title': 'Edit shop',
            'shop': shop,
            'active_nav': 'shops',
        },
    )

# Create your views here.
