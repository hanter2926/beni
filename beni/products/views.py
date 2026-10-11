from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.roles import SHOPKEEPER_GROUP, role_group_required

from .forms import ProductForm
from .models import Product


@role_group_required(SHOPKEEPER_GROUP)
def product_list(request):
	products = Product.objects.filter(shop__owner=request.user).select_related('shop')
	return render(
		request,
		'shopkeeper/products/list.html',
		{
			'products': products,
			'has_shops': request.user.shops.exists(),
			'role_label': 'Shopkeeper',
			'active_nav': 'products',
		},
	)


@role_group_required(SHOPKEEPER_GROUP)
def product_create(request):
	form = ProductForm(request.POST or None, request.FILES or None, user=request.user)
	if request.method == 'POST' and form.is_valid():
		form.save()
		messages.success(request, 'Product created.')
		return redirect('products:list')

	return render(
		request,
		'shopkeeper/products/form.html',
		{
			'form': form,
			'role_label': 'Shopkeeper',
			'page_title': 'Add a product',
			'has_shops': request.user.shops.exists(),
			'active_nav': 'products',
		},
	)


@role_group_required(SHOPKEEPER_GROUP)
def product_update(request, product_id):
	product = get_object_or_404(Product, pk=product_id, shop__owner=request.user)
	form = ProductForm(
		request.POST or None,
		request.FILES or None,
		user=request.user,
		instance=product,
	)
	if request.method == 'POST' and form.is_valid():
		form.save()
		messages.success(request, 'Product updated.')
		return redirect('products:list')

	return render(
		request,
		'shopkeeper/products/form.html',
		{
			'form': form,
			'role_label': 'Shopkeeper',
			'page_title': 'Edit product',
			'product': product,
			'has_shops': request.user.shops.exists(),
			'active_nav': 'products',
		},
	)
