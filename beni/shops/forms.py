from django import forms
from django.core.files.uploadedfile import UploadedFile
from beni.upload_validation import validate_decoded_image

from .models import Shop


class ShopForm(forms.ModelForm):
    LOGO_MAX_SIZE = 3 * 1024 * 1024
    COVER_MAX_SIZE = 5 * 1024 * 1024

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
        for field_name in ('logo_image', 'cover_image'):
            self.fields[field_name].widget.attrs['data-image-preview-input'] = ''
        self.fields['logo_image'].help_text = (
            'Optional. JPEG, PNG, or WebP; maximum 3 MB and 24 megapixels.'
        )
        self.fields['cover_image'].help_text = (
            'Optional. JPEG, PNG, or WebP; maximum 5 MB and 24 megapixels.'
        )
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