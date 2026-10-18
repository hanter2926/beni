from django import forms


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=30)
    address_line1 = forms.CharField(max_length=255)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    postal_code = forms.CharField(max_length=20)
    delivery_notes = forms.CharField(max_length=255, required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            attrs = field.widget.attrs
            attrs['class'] = f"{attrs.get('class', '')} form-control".strip()
            if self.is_bound and self.errors.get(name):
                attrs['aria-invalid'] = 'true'
                attrs['aria-describedby'] = f'id_{name}_errors'
