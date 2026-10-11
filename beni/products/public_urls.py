from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
	path('', views.public_catalog, name='list'),
	path('<int:product_id>/', views.public_product_detail, name='detail'),
]