from django import forms

from .models import Shop


class ShopForm(forms.ModelForm):
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
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'opening_hours': forms.Textarea(attrs={'rows': 3}),
            'latitude': forms.NumberInput(attrs={'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'step': '0.000001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


def _style_fields(form):
    for name, field in form.fields.items():
        attrs = field.widget.attrs
        attrs['class'] = f"{attrs.get('class', '')} form-control".strip()
        if form.is_bound and form.errors.get(name):
            attrs['aria-invalid'] = 'true'
            attrs['aria-describedby'] = f'id_{name}_errors'