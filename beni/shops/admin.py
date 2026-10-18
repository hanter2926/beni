from django.contrib import admin
from django import forms
from django.core.files.uploadedfile import UploadedFile

from .models import Shop
from beni.upload_validation import validate_decoded_image
from verification.models import VerificationApplication


class ShopAdminForm(forms.ModelForm):
	class Meta:
		model = Shop
		fields = '__all__'

	def clean_logo_image(self):
		image = self.cleaned_data.get('logo_image')
		if isinstance(image, UploadedFile):
			return validate_decoded_image(image, max_size=3 * 1024 * 1024)
		return image

	def clean_cover_image(self):
		image = self.cleaned_data.get('cover_image')
		if isinstance(image, UploadedFile):
			return validate_decoded_image(image, max_size=5 * 1024 * 1024)
		return image


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
	form = ShopAdminForm
	list_display = (
		'name',
		'owner',
		'category',
		'city',
		'state',
		'is_active',
		'verification_status',
	)
	list_filter = (
		'is_active',
		'category',
		'state',
		'verification_applications__status',
	)
	search_fields = ('name', 'owner__username', 'city', 'state', 'postal_code')
	readonly_fields = ('is_active', 'created_at', 'updated_at')

	@admin.display(description='Verification', ordering='verification_applications__status')
	def verification_status(self, obj):
		try:
			application = obj.verification_applications
		except VerificationApplication.DoesNotExist:
			return 'No application'
		return application.get_status_display()
