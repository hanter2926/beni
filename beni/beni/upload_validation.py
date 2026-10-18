from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}
IMAGE_EXTENSIONS = {
    'JPEG': '.jpg',
    'PNG': '.png',
    'WEBP': '.webp',
}
MAX_IMAGE_DIMENSION = 6000
MAX_IMAGE_PIXELS = 24_000_000
MAX_VERIFICATION_DOCUMENT_SIZE = 10 * 1024 * 1024


def validate_decoded_image(
    upload,
    *,
    max_size,
    max_dimension=MAX_IMAGE_DIMENSION,
    max_pixels=MAX_IMAGE_PIXELS,
):
    if upload.size > max_size:
        raise ValidationError(
            f'Image files must be {max_size // (1024 * 1024)} MB or smaller.'
        )

    image = getattr(upload, 'image', None)
    if image is None or image.format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError('Use a valid JPEG, PNG, or WebP image.')

    width, height = image.size
    if (
        width > max_dimension
        or height > max_dimension
        or width * height > max_pixels
    ):
        raise ValidationError(
            f'Images must be no larger than {max_dimension} × '
            f'{max_dimension} pixels and {max_pixels // 1_000_000} megapixels.'
        )
    if getattr(image, 'n_frames', 1) > 1:
        raise ValidationError('Animated images are not supported.')

    return upload


def validate_verification_document(upload):
    if upload.size > MAX_VERIFICATION_DOCUMENT_SIZE:
        raise ValidationError('Verification documents must be 10 MB or smaller.')

    file_object = upload.file
    file_object.seek(0)
    header = file_object.read(1024)
    if b'%PDF-' in header:
        try:
            file_object.seek(max(0, upload.size - 1024))
            footer = file_object.read(1024)
            if b'%%EOF' not in footer:
                raise ValidationError('The selected PDF is incomplete or invalid.')
            return upload
        finally:
            file_object.seek(0)

    try:
        file_object.seek(0)
        with Image.open(file_object) as image:
            image.verify()
        file_object.seek(0)
        with Image.open(file_object) as image:
            if image.format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError('Use a JPEG, PNG, WebP, or PDF document.')
            width, height = image.size
            if (
                width > MAX_IMAGE_DIMENSION
                or height > MAX_IMAGE_DIMENSION
                or width * height > MAX_IMAGE_PIXELS
            ):
                raise ValidationError(
                    'Scanned images must be no larger than 6000 × 6000 pixels '
                    'and 24 megapixels.'
                )
            if getattr(image, 'n_frames', 1) > 1:
                raise ValidationError('Animated document images are not supported.')
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise ValidationError(
            'Use a valid JPEG, PNG, WebP, or PDF document.'
        ) from exc
    finally:
        file_object.seek(0)
    return upload
