from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.roles import SHOPKEEPER_GROUP, role_group_required

from .forms import ShopForm
from .models import Shop
from verification.models import VerificationApplication


@role_group_required(SHOPKEEPER_GROUP)
def shop_list(request):
    shops = list(
        Shop.objects.filter(owner=request.user).select_related(
            'verification_applications'
        )
    )
    for shop in shops:
        try:
            shop.verification_application = shop.verification_applications
        except VerificationApplication.DoesNotExist:
            shop.verification_application = None
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
    form = ShopForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        shop = form.save(commit=False)
        shop.owner = request.user
        shop.is_active = False
        shop.save()
        VerificationApplication.objects.get_or_create(
            applicant=request.user,
            shop=shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
        )
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
            'role_label': 'Shopkeeper',
            'page_title': 'Add a shop',
            'active_nav': 'shops',
        },
    )


@role_group_required(SHOPKEEPER_GROUP)
def shop_update(request, shop_id):
    shop = get_object_or_404(Shop, pk=shop_id, owner=request.user)
    form = ShopForm(request.POST or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Shop details updated.')
        return redirect('shops:list')

    return render(
        request,
        'shopkeeper/shops/form.html',
        {
            'form': form,
            'role_label': 'Shopkeeper',
            'page_title': 'Edit shop',
            'shop': shop,
            'active_nav': 'shops',
        },
    )

# Create your views here.
