from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from accounts.models import Profile
from bookings.models import RepairBookingImage
from products.models import Product, ProductImage
from shops.models import Shop
from verification.models import VerificationDocument

from .file_lifecycle import schedule_delete_if_unreferenced


def _remember_old_uploads(instance, using, field_names):
    if not instance.pk:
        instance._previous_uploads = {}
        return
    old_values = (
        type(instance)._base_manager.using(using)
        .filter(pk=instance.pk)
        .values(*field_names)
        .first()
    )
    instance._previous_uploads = old_values or {}


def _schedule_replaced_uploads(instance, field_references):
    previous_uploads = getattr(instance, '_previous_uploads', {})
    for field_name, references in field_references.items():
        old_name = previous_uploads.get(field_name)
        current_name = getattr(instance, field_name).name
        if old_name and old_name != current_name:
            schedule_delete_if_unreferenced(
                old_name,
                *references,
                storage=instance._meta.get_field(field_name).storage,
            )


def _schedule_deleted_upload(instance, field_name, *references):
    file_field = getattr(instance, field_name)
    schedule_delete_if_unreferenced(
        file_field,
        *references,
    )


@receiver(pre_save, sender=Product)
def remember_product_image(sender, instance, using, **kwargs):
    _remember_old_uploads(instance, using, ('image',))


@receiver(post_save, sender=Product)
def remove_replaced_product_image(sender, instance, **kwargs):
    _schedule_replaced_uploads(
        instance,
        {
            'image': (
                (Product, 'image'),
                (ProductImage, 'image'),
            ),
        },
    )


@receiver(pre_save, sender=Shop)
def remember_shop_images(sender, instance, using, **kwargs):
    _remember_old_uploads(instance, using, ('logo_image', 'cover_image'))


@receiver(post_save, sender=Shop)
def remove_replaced_shop_images(sender, instance, **kwargs):
    _schedule_replaced_uploads(
        instance,
        {
            'logo_image': ((Shop, 'logo_image'),),
            'cover_image': ((Shop, 'cover_image'),),
        },
    )


@receiver(pre_save, sender=Profile)
def remember_profile_image(sender, instance, using, **kwargs):
    _remember_old_uploads(instance, using, ('image',))


@receiver(post_save, sender=Profile)
def remove_replaced_profile_image(sender, instance, **kwargs):
    _schedule_replaced_uploads(
        instance,
        {'image': ((Profile, 'image'),)},
    )


@receiver(post_delete, sender=Product)
def remove_deleted_product_image(sender, instance, **kwargs):
    _schedule_deleted_upload(
        instance,
        'image',
        (Product, 'image'),
        (ProductImage, 'image'),
    )


@receiver(post_delete, sender=ProductImage)
def remove_deleted_gallery_image(sender, instance, **kwargs):
    _schedule_deleted_upload(
        instance,
        'image',
        (Product, 'image'),
        (ProductImage, 'image'),
    )


@receiver(post_delete, sender=Shop)
def remove_deleted_shop_images(sender, instance, **kwargs):
    _schedule_deleted_upload(instance, 'logo_image', (Shop, 'logo_image'))
    _schedule_deleted_upload(instance, 'cover_image', (Shop, 'cover_image'))


@receiver(post_delete, sender=Profile)
def remove_deleted_profile_image(sender, instance, **kwargs):
    _schedule_deleted_upload(instance, 'image', (Profile, 'image'))


@receiver(post_delete, sender=RepairBookingImage)
def remove_deleted_booking_image(sender, instance, **kwargs):
    _schedule_deleted_upload(
        instance,
        'image',
        (RepairBookingImage, 'image'),
    )


@receiver(post_delete, sender=VerificationDocument)
def remove_deleted_verification_document(sender, instance, **kwargs):
    _schedule_deleted_upload(
        instance,
        'file',
        (VerificationDocument, 'file'),
    )
