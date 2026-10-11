from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import LoginForm
from .views import register, role_dashboard_url


class BeniLoginView(auth_views.LoginView):
    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        return role_dashboard_url(self.request.user)

app_name = 'accounts'

urlpatterns = [
    path(
        'login/',
        BeniLoginView.as_view(
            authentication_form=LoginForm,
            template_name='auth/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('register/', register, name='register'),
    path(
        'logout/',
        auth_views.LogoutView.as_view(next_page='accounts:login'),
        name='logout',
    ),
]