from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.roles import SHOPKEEPER_GROUP, role_group_required

from .forms import ProductForm
from .models import Product
from .services import marketable_products


def public_products():
	return marketable_products().select_related('shop')


def public_catalog(request):
	products = public_products()
	query = request.GET.get('q', '').strip()
	category = request.GET.get('category', '').strip()

	if query:
		products = products.filter(
			Q(name__icontains=query)
			| Q(description__icontains=query)
			| Q(category__icontains=query)
			| Q(shop__name__icontains=query)
		)
	if category:
		products = products.filter(category__iexact=category)

	categories = (
		public_products()
		.order_by('category')
		.values_list('category', flat=True)
		.distinct()
	)
	page_obj = Paginator(products, 12).get_page(request.GET.get('page'))
	return render(
		request,
		'customer/catalog/list.html',
		{
			'page_obj': page_obj,
			'products': page_obj.object_list,
			'categories': categories,
			'query': query,
			'selected_category': category,
		},
	)


def public_product_detail(request, product_id):
	product = get_object_or_404(
		public_products().prefetch_related('shop__photos'),
		pk=product_id,
	)
	return render(request, 'customer/catalog/detail.html', {'product': product})


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
