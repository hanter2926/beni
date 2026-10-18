from django import forms
from django.core.files.uploadedfile import UploadedFile

from shops.models import Shop

from beni.upload_forms import MultipleImageField

from .image_validation import validate_product_image
from .models import Product, ProductImage


class ProductForm(forms.ModelForm):
    gallery_images = MultipleImageField(
        required=False,
        max_files=5,
        max_size=2 * 1024 * 1024,
        label='Additional gallery images',
        help_text='Optional. Up to five JPEG, PNG, or WebP images, 2 MB each.',
    )
    remove_gallery_images = forms.ModelMultipleChoiceField(
        queryset=ProductImage.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Remove gallery images',
    )

    class Meta:
        model = Product
        fields = (
            'shop',
            'name',
            'category',
            'description',
            'sku',
            'price',
            'stock_quantity',
            'image',
            'is_active',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'stock_quantity': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shop'].queryset = Shop.objects.filter(owner=user).order_by('name')
        self.fields['image'].widget.attrs.update({
            'accept': '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp',
            'type': 'file',
            'data-product-image-input': '',
        })
        self.fields['image'].help_text = (
            'Optional. JPEG, PNG, or WebP; maximum 2 MB, 6000 × 6000 pixels, '
            'and 24 megapixels.'
        )
        if self.instance.pk:
            self.fields['remove_gallery_images'].queryset = (
                ProductImage.objects.filter(product=self.instance)
            )
        self.fields['gallery_images'].widget.attrs.update({
            'accept': '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp',
        })
        for name, field in self.fields.items():
            attrs = field.widget.attrs
            attrs['class'] = f"{attrs.get('class', '')} form-control".strip()
            described_by = []
            if field.help_text:
                described_by.append(f'id_{name}_help')
            if name == 'image':
                described_by.append('product-image-preview-message')
            if self.is_bound and self.errors.get(name):
                attrs['aria-invalid'] = 'true'
                described_by.append(f'id_{name}_errors')
            if described_by:
                attrs['aria-describedby'] = ' '.join(described_by)

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if isinstance(image, UploadedFile):
            return validate_product_image(image)
        return image

    def clean(self):
        cleaned_data = super().clean()
        new_images = cleaned_data.get('gallery_images', [])
        removals = cleaned_data.get('remove_gallery_images')
        existing_count = (
            self.instance.gallery_images.count() if self.instance.pk else 0
        )
        removal_count = removals.count() if removals is not None else 0
        if existing_count - removal_count + len(new_images) > 5:
            self.add_error(
                'gallery_images',
                'A product can have no more than five gallery images.',
            )
        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=commit)
        if not commit:
            return product

        selected_removals = list(self.cleaned_data.get('remove_gallery_images', []))
        for gallery_image in selected_removals:
            gallery_image.delete()

        for image in self.cleaned_data.get('gallery_images', []):
            ProductImage.objects.create(
                product=product,
                image=image,
                alt_text=product.name,
            )
        return product