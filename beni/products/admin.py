from django.contrib import admin
from django import forms
from django.core.files.uploadedfile import UploadedFile

from .models import Product, ProductImage
from .image_validation import validate_product_image
from beni.upload_validation import validate_decoded_image


class ProductAdminForm(forms.ModelForm):
	class Meta:
		model = Product
		fields = '__all__'

	def clean_image(self):
		image = self.cleaned_data.get('image')
		if isinstance(image, UploadedFile):
			return validate_product_image(image)
		return image

class ProductImageInlineForm(forms.ModelForm):
	class Meta:
		model = ProductImage
		fields = '__all__'

	def clean_image(self):
		image = self.cleaned_data.get('image')
		if isinstance(image, UploadedFile):
			return validate_decoded_image(image, max_size=2 * 1024 * 1024)
		return image


class ProductImageInline(admin.TabularInline):
	model = ProductImage
	form = ProductImageInlineForm
	extra = 0
	max_num = 5
	validate_max = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
	form = ProductAdminForm
	inlines = [ProductImageInline]
	list_display = ('name', 'shop', 'category', 'sku', 'price', 'stock_quantity', 'is_active')
	list_filter = ('is_active', 'category')
	search_fields = ('name', 'sku', 'shop__name')
	list_select_related = ('shop',)
	readonly_fields = ('created_at', 'updated_at')
