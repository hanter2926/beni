from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path, reverse_lazy

from .forms import BeniPasswordResetForm, BeniSetPasswordForm, LoginForm
from .views import private_profile_image, profile, register, role_dashboard_url


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
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            form_class=BeniPasswordResetForm,
            template_name='auth/password_reset_form.html',
            email_template_name='auth/password_reset_email.html',
            subject_template_name='auth/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='auth/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password-reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            form_class=BeniSetPasswordForm,
            template_name='auth/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='auth/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('profile/', profile, name='profile'),
    path('profiles/<int:user_id>/image/', private_profile_image, name='profile_image'),
    path(
        'logout/',
        auth_views.LogoutView.as_view(next_page='accounts:login'),
        name='logout',
    ),
    path(
        'password-change/',
        login_required(
            auth_views.PasswordChangeView.as_view(
                template_name='auth/password_change.html',
                success_url=reverse_lazy('accounts:password_change_done'),
            )
        ),
        name='password_change',
    ),
    path(
        'password-change/done/',
        login_required(
            auth_views.PasswordChangeDoneView.as_view(
                template_name='auth/password_change_done.html',
            )
        ),
        name='password_change_done',
    ),
]