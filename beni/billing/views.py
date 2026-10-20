from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from orders.models import Order
from payments.models import PaymentAttempt


@login_required(login_url='accounts:login')
def order_invoice(request, order_number):
    orders = Order.objects.select_related(
        'customer',
        'shop',
        'checkout_attempt',
    ).prefetch_related('items')
    if not request.user.is_staff and not request.user.is_superuser:
        orders = orders.filter(
            Q(customer=request.user) | Q(shop__owner=request.user)
        )

    order = get_object_or_404(orders, order_number=order_number)
    payment_attempt = (
        PaymentAttempt.objects.filter(
            checkout_attempt=order.checkout_attempt,
            status=PaymentAttempt.STATUS_CAPTURED,
        )
        .exclude(provider_payment_id__isnull=True)
        .exclude(provider_payment_id='')
        .order_by('-updated_at', '-pk')
        .first()
    )
    if request.user.is_staff or request.user.is_superuser:
        role_label = 'Admin'
    elif order.shop.owner_id == request.user.pk:
        role_label = 'Shopkeeper'
    else:
        role_label = 'Customer'

    return render(
        request,
        'billing/order_invoice.html',
        {
            'order': order,
            'payment_attempt': payment_attempt,
            'role_label': role_label,
        },
    )
