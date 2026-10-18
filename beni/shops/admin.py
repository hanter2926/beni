from django.contrib import admin

from .models import Shop
from verification.models import VerificationApplication


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
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
