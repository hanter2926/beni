from uuid import uuid4

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from .upload_validation import IMAGE_EXTENSIONS


def _image_extension(file_field):
    file_object = file_field.file
    original_position = file_object.tell()
    try:
        file_object.seek(0)
        with Image.open(file_object) as image:
            extension = IMAGE_EXTENSIONS.get(image.format)
        if extension is None:
            raise ValidationError('Use a valid JPEG, PNG, or WebP image.')
        return extension
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise ValidationError('Use a valid JPEG, PNG, or WebP image.') from exc
    finally:
        file_object.seek(original_position)


def _image_path(folder, instance, filename, field_name):
    image_file = getattr(instance, field_name)
    extension = _image_extension(image_file)
    return f'{folder}/{uuid4().hex}{extension}'


def product_image_path(instance, filename):
    return _image_path('products', instance, filename, 'image')


def product_gallery_image_path(instance, filename):
    return _image_path('products/gallery', instance, filename, 'image')


def shop_logo_path(instance, filename):
    return _image_path('shops/logos', instance, filename, 'logo_image')


def shop_cover_path(instance, filename):
    return _image_path('shops/covers', instance, filename, 'cover_image')


def profile_image_path(instance, filename):
    return _image_path('profiles', instance, filename, 'image')


def booking_image_path(instance, filename):
    return _image_path('bookings', instance, filename, 'image')


def verification_document_path(instance, filename):
    file_object = instance.file.file
    original_position = file_object.tell()
    try:
        file_object.seek(0)
        header = file_object.read(1024)
        if b'%PDF-' in header:
            extension = '.pdf'
        else:
            file_object.seek(0)
            with Image.open(file_object) as image:
                extension = IMAGE_EXTENSIONS.get(image.format)
            if extension is None:
                raise ValidationError(
                    'Use a valid JPEG, PNG, WebP, or PDF document.'
                )
    finally:
        file_object.seek(original_position)
    return f'verification/{uuid4().hex}{extension}'
