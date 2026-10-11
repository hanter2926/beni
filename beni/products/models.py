from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

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
	image = models.ImageField(upload_to='products/', blank=True)
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

	def save(self, *args, **kwargs):
		if self.sku is not None:
			self.sku = self.sku.strip() or None
		return super().save(*args, **kwargs)

	def __str__(self):
		return self.name
