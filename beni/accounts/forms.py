from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django import forms
from django.forms import ModelForm

from beni.upload_validation import validate_decoded_image

from .models import Profile


def style_fields(form):
    autocomplete = {
        'username': 'username',
        'email': 'email',
        'password': 'current-password',
        'password1': 'new-password',
        'password2': 'new-password',
    }
    for name, field in form.fields.items():
        attrs = field.widget.attrs
        attrs['class'] = f"{attrs.get('class', '')} form-control".strip()
        if name in autocomplete:
            attrs['autocomplete'] = autocomplete[name]

        described_by = []
        if field.help_text:
            described_by.append(f'id_{name}_help')
        if form.is_bound and form.errors.get(name):
            attrs['aria-invalid'] = 'true'
            described_by.append(f'id_{name}_errors')
        if described_by:
            attrs['aria-describedby'] = ' '.join(described_by)
    return form


def _validate_unique_email(email, *, exclude_user_id=None):
    users = get_user_model().objects.filter(email__iexact=email)
    if exclude_user_id is not None:
        users = users.exclude(pk=exclude_user_id)
    if users.exists():
        raise forms.ValidationError(
            'An account with this email address already exists.'
        )
    return email


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class BeniPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class BeniSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class RegistrationForm(UserCreationForm):
    ROLE_CUSTOMER = 'customer'
    ROLE_SHOPKEEPER = 'shopkeeper'
    ROLE_REPAIR_WORKER = 'repair_worker'

    email = forms.EmailField(
        required=True,
        help_text='Used for password recovery.',
    )
    role = forms.ChoiceField(
        choices=(
            (ROLE_CUSTOMER, 'Customer'),
            (ROLE_SHOPKEEPER, 'Shopkeeper'),
            (ROLE_REPAIR_WORKER, 'Repair Worker'),
        ),
        help_text=(
            'Shopkeeper and Repair Worker features remain restricted until '
            'required verification is approved.'
        ),
        label='Account type',
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(('username', 'email', 'role', 'password1', 'password2'))
        style_fields(self)

    def clean_email(self):
        return _validate_unique_email(self.cleaned_data['email'].strip())


class ProfileForm(ModelForm):
    email = forms.EmailField(
        required=True,
        help_text='Used for password recovery.',
    )
    profile_image = forms.ImageField(
        required=False,
        label='Profile photo',
        help_text='Optional. JPEG, PNG, or WebP; maximum 3 MB and 24 megapixels.',
        widget=forms.ClearableFileInput(
            attrs={'accept': 'image/jpeg,image/png,image/webp'}
        ),
    )

    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name', 'email')

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.fields['profile_image'].widget.attrs['data-image-preview-input'] = ''
        if profile and profile.image:
            self.fields['profile_image'].initial = profile.image
        style_fields(self)

    def clean_email(self):
        return _validate_unique_email(
            self.cleaned_data['email'].strip(),
            exclude_user_id=self.instance.pk,
        )

    def clean_profile_image(self):
        image = self.cleaned_data.get('profile_image')
        if isinstance(image, UploadedFile):
            return validate_decoded_image(image, max_size=3 * 1024 * 1024)
        return image

    def save(self, commit=True):
        user = super().save(commit=commit)
        if not commit:
            return user

        profile = self.profile or Profile(user=user)
        new_image = self.cleaned_data.get('profile_image')
        if isinstance(new_image, UploadedFile):
            profile.image = new_image
            profile.save()
        elif new_image is False and profile.image:
            profile.image = ''
            profile.save()
        self.profile = profile
        return user