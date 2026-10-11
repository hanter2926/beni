from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


def style_fields(form):
    autocomplete = {
        'username': 'username',
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


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class RegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)