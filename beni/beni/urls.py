"""
URL configuration for beni project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='accounts:login', permanent=False), name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('customer/', include('customers.urls')),
    path('notifications/', include('notifications.urls')),
    path('repairs/', include('bookings.urls')),
    path('wallets/', include('wallets.urls')),
    path('verification/', include('verification.urls')),
    path('catalog/', include('products.public_urls')),
    path('workspace/', include('dashboard.urls')),
    path('workspace/shopkeeper/shops/', include('shops.urls')),
    path('workspace/shopkeeper/products/', include('products.urls')),
    path('workspace/shopkeeper/orders/', include('customers.shopkeeper_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
