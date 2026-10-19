from django.db.models import Q

from verification.models import VerificationApplication

from .models import Product


def eligible_shop_verifications(shop_ids=None, *, lock=False):
    verifications = VerificationApplication.objects.filter(
        application_type=VerificationApplication.TYPE_SHOPKEEPER,
        status=VerificationApplication.STATUS_APPROVED,
        phone_status=VerificationApplication.CHECK_VERIFIED,
        applicant__profile__phone_verified=True,
    ).filter(
        Q(aadhaar_status=VerificationApplication.CHECK_VERIFIED)
        | Q(pan_status=VerificationApplication.CHECK_VERIFIED)
    )
    if shop_ids is not None:
        verifications = verifications.filter(shop_id__in=shop_ids)
    if lock:
        verifications = verifications.select_for_update()
    return verifications


def marketable_products(queryset=None):
    products = queryset if queryset is not None else Product.objects.all()
    return products.filter(
        is_active=True,
        shop__is_active=True,
        shop_id__in=eligible_shop_verifications().values_list('shop_id', flat=True),
    ).distinct()


def is_product_marketable(product, *, shop=None, eligible_shop_ids=None):
    product_shop = shop or product.shop
    if not product.is_active or not product_shop.is_active:
        return False
    if eligible_shop_ids is None:
        eligible_shop_ids = set(
            eligible_shop_verifications(
                shop_ids=(product_shop.pk,),
            ).values_list('shop_id', flat=True)
        )
    return product_shop.pk in eligible_shop_ids
