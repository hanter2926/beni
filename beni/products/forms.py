from django import forms

from shops.models import Shop

from .models import Product


class ProductForm(forms.ModelForm):
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
        for name, field in self.fields.items():
            attrs = field.widget.attrs
            attrs['class'] = f"{attrs.get('class', '')} form-control".strip()
            if self.is_bound and self.errors.get(name):
                attrs['aria-invalid'] = 'true'
                attrs['aria-describedby'] = f'id_{name}_errors'