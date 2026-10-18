from django.conf import settings
from django.db import models

from beni.upload_paths import profile_image_path
from verification.storage import private_storage


class Profile(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='profile',
	)
	image = models.ImageField(
		upload_to=profile_image_path,
		storage=private_storage,
		blank=True,
	)

	def __str__(self):
		return f'Profile for {self.user.get_username()}'
