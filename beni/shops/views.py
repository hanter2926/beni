from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.roles import SHOPKEEPER_GROUP, role_group_required

from .forms import ShopForm
from .models import Shop


@role_group_required(SHOPKEEPER_GROUP)
def shop_list(request):
    shops = Shop.objects.filter(owner=request.user)
    return render(
        request,
        'shopkeeper/shops/list.html',
        {'shops': shops, 'role_label': 'Shopkeeper', 'active_nav': 'shops'},
    )


@role_group_required(SHOPKEEPER_GROUP)
def shop_create(request):
    form = ShopForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        shop = form.save(commit=False)
        shop.owner = request.user
        shop.save()
        messages.success(request, 'Shop created.')
        return redirect('shops:list')

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
        messages.success(request, 'Shop updated.')
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
