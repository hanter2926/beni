from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from beni.upload_paths import profile_image_path
from verification.storage import private_storage


def valid_phone_number(phone):
	return (
		bool(phone)
		and all(character in '+0123456789() .-' for character in phone)
		and 7 <= sum(character.isdigit() for character in phone) <= 15
	)


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
	phone = models.CharField(max_length=30, blank=True)
	alternate_phone = models.CharField(max_length=30, blank=True)
	phone_verified = models.BooleanField(default=False)
	service_details = models.TextField(blank=True)

	def clean(self):
		super().clean()
		for field_name in ('phone', 'alternate_phone'):
			value = getattr(self, field_name)
			if value and not valid_phone_number(value):
				raise ValidationError({
					field_name: 'Enter a valid phone number with 7 to 15 digits.',
				})

	def save(self, *args, **kwargs):
		if self.pk:
			previous_phone = type(self).objects.filter(pk=self.pk).values_list(
				'phone', flat=True,
			).first()
			if previous_phone is not None and previous_phone != self.phone:
				self.phone_verified = False
				update_fields = kwargs.get('update_fields')
				if update_fields is not None:
					kwargs['update_fields'] = set(update_fields) | {'phone_verified'}
		return super().save(*args, **kwargs)

	def __str__(self):
		return f'Profile for {self.user.get_username()}'
