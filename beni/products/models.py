from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import connection, models
from django.db.models import Q

from beni.upload_paths import product_gallery_image_path, product_image_path
from shops.models import Shop


class Product(models.Model):
	shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
	name = models.CharField(max_length=150)
	description = models.TextField(blank=True)
	category = models.CharField(max_length=100)
	sku = models.CharField(max_length=64, null=True, blank=True)
	price = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		validators=[MinValueValidator(Decimal('0.00'))],
	)
	stock_quantity = models.PositiveIntegerField(default=0)
	image = models.ImageField(upload_to=product_image_path, blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ('name', 'id')
		constraints = [
			models.CheckConstraint(
				condition=Q(price__gte=Decimal('0.00')),
				name='product_price_nonnegative',
			),
			models.CheckConstraint(
				condition=Q(stock_quantity__gte=0),
				name='product_stock_nonnegative',
			),
			models.UniqueConstraint(
				fields=('shop', 'sku'),
				name='product_shop_sku_unique',
			),
		]

	def clean(self):
		super().clean()
		if self.sku is not None:
			self.sku = self.sku.strip() or None
		self._validate_shop_assignment()

	def save(self, *args, **kwargs):
		if self.sku is not None:
			self.sku = self.sku.strip() or None
		update_fields = kwargs.get('update_fields')
		if update_fields is None or 'shop' in update_fields or 'shop_id' in update_fields:
			self._validate_shop_assignment()
		return super().save(*args, **kwargs)

	def _validate_shop_assignment(self):
		if not self.pk:
			return
		previous_shop_id = type(self).objects.filter(pk=self.pk).values_list('shop_id', flat=True).first()
		if previous_shop_id is None or previous_shop_id == self.shop_id:
			return

		from orders.models import OrderItem

		if OrderItem._meta.db_table not in connection.introspection.table_names():
			return
		if OrderItem.objects.filter(product_id=self.pk).exists():
			raise ValidationError({
				'shop': 'A product with order history cannot be moved to another shop.',
			})

	def __str__(self):
		return self.name


class ProductImage(models.Model):
	product = models.ForeignKey(
		Product,
		on_delete=models.CASCADE,
		related_name='gallery_images',
	)
	image = models.ImageField(upload_to=product_gallery_image_path)
	alt_text = models.CharField(max_length=200, blank=True)
	sort_order = models.PositiveSmallIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ('sort_order', 'created_at', 'pk')

	def __str__(self):
		return f'Gallery image for {self.product.name}'
