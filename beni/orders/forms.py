from django import forms
from django.core.validators import RegexValidator


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    phone = forms.CharField(
        max_length=30,
        validators=[RegexValidator(
            regex=r'^[0-9+() .-]{7,30}$',
            message='Enter a valid phone number.',
        )],
    )
    address_line1 = forms.CharField(max_length=255)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    postal_code = forms.CharField(max_length=20)
    delivery_notes = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            attrs = field.widget.attrs
            attrs['class'] = f"{attrs.get('class', '')} form-control".strip()
            if self.is_bound and self.errors.get(name):
                attrs['aria-invalid'] = 'true'
                attrs['aria-describedby'] = f'id_{name}_errors'

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digit_count = sum(character.isdigit() for character in phone)
        if not 7 <= digit_count <= 15:
            raise forms.ValidationError('Enter a phone number with 7 to 15 digits.')
        return phone


class OrderStatusForm(forms.Form):
    status = forms.ChoiceField(label='Update order status')

    def __init__(self, *args, allowed_statuses, current_status, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            'confirmed': 'Accept order',
            'cancelled': (
                'Reject order'
                if current_status == 'pending'
                else 'Cancel order'
            ),
        }
        self.fields['status'].choices = [
            (status, labels.get(status, status.replace('_', ' ').title()))
            for status in allowed_statuses
        ]
        self.fields['status'].widget.attrs['class'] = 'form-control'
