from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


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
