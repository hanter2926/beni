from django.urls import path

from . import views

app_name = 'wallets'

urlpatterns = [
    path('shopkeeper/', views.shopkeeper_wallet, name='shopkeeper'),
    path('repair-worker/', views.repair_worker_wallet, name='repair_worker'),
]
