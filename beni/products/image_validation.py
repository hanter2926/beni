from beni.upload_validation import validate_decoded_image


MAX_PRODUCT_IMAGE_SIZE = 2 * 1024 * 1024
MAX_PRODUCT_IMAGE_DIMENSION = 6000
MAX_PRODUCT_IMAGE_PIXELS = 24_000_000
ALLOWED_PRODUCT_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def validate_product_image(upload):
    return validate_decoded_image(
        upload,
        max_size=MAX_PRODUCT_IMAGE_SIZE,
        max_dimension=MAX_PRODUCT_IMAGE_DIMENSION,
        max_pixels=MAX_PRODUCT_IMAGE_PIXELS,
    )
