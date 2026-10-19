import re

from django import forms
from django.core.files.uploadedfile import UploadedFile
from beni.upload_validation import validate_decoded_image
from beni.upload_forms import MultipleImageField

from .models import Shop, ShopBankDetails, ShopPhoto


class ShopForm(forms.ModelForm):
    LOGO_MAX_SIZE = 3 * 1024 * 1024
    COVER_MAX_SIZE = 5 * 1024 * 1024
    PHOTO_MAX_SIZE = 3 * 1024 * 1024
    gallery_images = MultipleImageField(
        required=False,
        max_files=5,
        max_size=PHOTO_MAX_SIZE,
        label='Shop photos',
        help_text='Optional. Up to five JPEG, PNG, or WebP images, 3 MB each.',
    )
    remove_photos = forms.ModelMultipleChoiceField(
        queryset=ShopPhoto.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Remove shop photos',
    )

    class Meta:
        model = Shop
        fields = (
            'name',
            'category',
            'description',
            'phone',
            'address',
            'city',
            'state',
            'postal_code',
            'latitude',
            'longitude',
            'opening_hours',
            'logo_image',
            'cover_image',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'opening_hours': forms.Textarea(attrs={'rows': 3}),
            'latitude': forms.NumberInput(attrs={'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'step': '0.000001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['logo_image'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'
        self.fields['cover_image'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'
        self.fields['gallery_images'].widget.attrs['accept'] = (
            '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
        )
        self.fields['city'].label = 'Locality / city'
        self.fields['city'].help_text = (
            'Enter the locality or neighborhood where customers can find the shop.'
        )
        if self.instance.pk:
            self.fields['remove_photos'].queryset = ShopPhoto.objects.filter(
                shop=self.instance,
            )
        for field_name in ('logo_image', 'cover_image'):
            self.fields[field_name].widget.attrs['data-image-preview-input'] = ''
        self.fields['logo_image'].help_text = (
            'Optional. JPEG, PNG, or WebP; maximum 3 MB and 24 megapixels.'
        )
        self.fields['cover_image'].help_text = (
            'Optional. JPEG, PNG, or WebP; maximum 5 MB and 24 megapixels.'
        )
        self.fields['gallery_images'].widget.attrs['data-image-preview-input'] = ''
        _style_fields(self)

    def clean_logo_image(self):
        image = self.cleaned_data.get('logo_image')
        if isinstance(image, UploadedFile):
            return validate_decoded_image(image, max_size=self.LOGO_MAX_SIZE)
        return image

    def clean_cover_image(self):
        image = self.cleaned_data.get('cover_image')
        if isinstance(image, UploadedFile):
            return validate_decoded_image(image, max_size=self.COVER_MAX_SIZE)
        return image

    def clean(self):
        cleaned_data = super().clean()
        new_images = cleaned_data.get('gallery_images', [])
        removals = cleaned_data.get('remove_photos')
        existing_count = self.instance.photos.count() if self.instance.pk else 0
        removal_count = removals.count() if removals is not None else 0
        if existing_count - removal_count + len(new_images) > 5:
            self.add_error(
                'gallery_images',
                'A shop can have no more than five gallery photos.',
            )
        return cleaned_data

    def save(self, commit=True):
        shop = super().save(commit=commit)
        if commit:
            self.save_photos(shop)
        return shop

    def save_photos(self, shop):
        for photo in self.cleaned_data.get('remove_photos', []):
            photo.delete()
        for image in self.cleaned_data.get('gallery_images', []):
            ShopPhoto.objects.create(
                shop=shop,
                image=image,
                alt_text=shop.name,
            )


class ShopBankDetailsForm(forms.Form):
    ACCOUNT_NUMBER_MAX_LENGTH = 34

    account_holder_name = forms.CharField(
        max_length=150,
        required=False,
        label='Account holder name',
    )
    account_number = forms.CharField(
        max_length=ACCOUNT_NUMBER_MAX_LENGTH,
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={'autocomplete': 'new-password'},
        ),
    )
    ifsc_code = forms.CharField(
        max_length=11,
        required=False,
        label='IFSC code',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        self.has_data = False
        if instance is not None:
            self.fields['account_holder_name'].initial = (
                instance.account_holder_name
            )
            self.fields['ifsc_code'].initial = instance.ifsc_code
        self.fields['account_number'].help_text = (
            'Account number is never displayed after saving. Leave blank to '
            'keep the existing account number.'
        )
        self.fields['account_holder_name'].help_text = (
            'Enter the name registered with the bank.'
        )
        self.fields['ifsc_code'].max_length = 11
        self.fields['ifsc_code'].help_text = '11-character Indian IFSC code.'
        _style_fields(self)

    def clean_account_number(self):
        value = self.cleaned_data.get('account_number', '').strip()
        if value and not value.isdigit():
            raise forms.ValidationError('Enter an account number using digits only.')
        if value and not 6 <= len(value) <= self.ACCOUNT_NUMBER_MAX_LENGTH:
            raise forms.ValidationError(
                'Enter an account number between 6 and 34 digits.'
            )
        return value

    def clean_ifsc_code(self):
        value = self.cleaned_data.get('ifsc_code', '').strip().upper()
        if value and not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', value):
            raise forms.ValidationError('Enter a valid 11-character IFSC code.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        fields = ('account_holder_name', 'account_number', 'ifsc_code')
        supplied = any(cleaned_data.get(name) for name in fields)
        self.has_data = supplied
        if not supplied:
            return cleaned_data

        if self.instance is not None:
            for name in fields:
                if not cleaned_data.get(name):
                    cleaned_data[name] = getattr(self.instance, name)
        elif supplied:
            for name in fields:
                if not cleaned_data.get(name):
                    self.add_error(name, 'Complete all bank details to save them.')
        return cleaned_data

    def save_for_shop(self, shop):
        if not self.has_data:
            return None
        values = {
            name: self.cleaned_data[name]
            for name in ('account_holder_name', 'account_number', 'ifsc_code')
        }
        details = self.instance or ShopBankDetails(shop=shop)
        for name, value in values.items():
            setattr(details, name, value)
        details.save()
        return details


def _style_fields(form):
    for name, field in form.fields.items():
        attrs = field.widget.attrs
        attrs['class'] = f"{attrs.get('class', '')} form-control".strip()
        described_by = []
        if field.help_text:
            described_by.append(f'id_{name}_help')
        if form.is_bound and form.errors.get(name):
            attrs['aria-invalid'] = 'true'
            described_by.append(f'id_{name}_errors')
        if described_by:
            attrs['aria-describedby'] = ' '.join(described_by)