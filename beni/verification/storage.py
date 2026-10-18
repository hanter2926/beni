from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateFileSystemStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=settings.PRIVATE_MEDIA_ROOT,
            base_url='/private-media-not-served/',
        )

    def url(self, name):
        raise ValueError('Private files must be served by an authorized view.')


private_storage = PrivateFileSystemStorage()
