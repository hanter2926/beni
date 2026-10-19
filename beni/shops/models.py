from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from beni.upload_paths import (
	shop_cover_path,
	shop_gallery_image_path,
	shop_logo_path,
)


class Shop(models.Model):
	owner = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='shops',
	)
	name = models.CharField(max_length=150)
	description = models.TextField(blank=True)
	category = models.CharField(max_length=100)
	phone = models.CharField(max_length=30)
	address = models.CharField(max_length=255)
	city = models.CharField(max_length=100)
	state = models.CharField(max_length=100)
	postal_code = models.CharField(max_length=20)
	latitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		null=True,
		blank=True,
		validators=[
			MinValueValidator(Decimal('-90')),
			MaxValueValidator(Decimal('90')),
		],
	)
	longitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		null=True,
		blank=True,
		validators=[
			MinValueValidator(Decimal('-180')),
			MaxValueValidator(Decimal('180')),
		],
	)
	opening_hours = models.TextField(blank=True)
	logo_image = models.ImageField(upload_to=shop_logo_path, blank=True)
	cover_image = models.ImageField(upload_to=shop_cover_path, blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ('name', 'id')
		constraints = [
			models.CheckConstraint(
				condition=(
					Q(latitude__isnull=True)
					| Q(latitude__gte=Decimal('-90'), latitude__lte=Decimal('90'))
				),
				name='shop_latitude_range',
			),
			models.CheckConstraint(
				condition=(
					Q(longitude__isnull=True)
					| Q(longitude__gte=Decimal('-180'), longitude__lte=Decimal('180'))
				),
				name='shop_longitude_range',
			),
		]

	def __str__(self):
		return self.name


class ShopPhoto(models.Model):
	shop = models.ForeignKey(
		Shop,
		on_delete=models.CASCADE,
		related_name='photos',
	)
	image = models.ImageField(upload_to=shop_gallery_image_path)
	alt_text = models.CharField(max_length=200, blank=True)
	sort_order = models.PositiveSmallIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ('sort_order', 'created_at', 'pk')

	def __str__(self):
		return f'Photo for {self.shop.name}'


class ShopBankDetails(models.Model):
	shop = models.OneToOneField(
		Shop,
		on_delete=models.CASCADE,
		related_name='bank_details',
	)
	account_holder_name = models.CharField(max_length=150)
	account_number = models.CharField(max_length=34)
	ifsc_code = models.CharField(max_length=11)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f'Bank details for shop #{self.shop_id}'
