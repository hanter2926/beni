from django import forms

from .models import VerificationApplication


class VerificationSubmissionForm(forms.Form):
    confirmation = forms.BooleanField(
        required=True,
        label='I want to submit this application for staff review.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attrs = self.fields['confirmation'].widget.attrs
        if self.is_bound and self.errors.get('confirmation'):
            attrs['aria-invalid'] = 'true'
            attrs['aria-describedby'] = 'id_confirmation_errors'


class VerificationReviewForm(forms.Form):
    status = forms.ChoiceField(choices=VerificationApplication.STATUS_CHOICES)
    phone_status = forms.ChoiceField(choices=VerificationApplication.CHECK_CHOICES)
    aadhaar_status = forms.ChoiceField(choices=VerificationApplication.CHECK_CHOICES)
    pan_status = forms.ChoiceField(choices=VerificationApplication.CHECK_CHOICES)
    bank_status = forms.ChoiceField(choices=VerificationApplication.CHECK_CHOICES)
    face_status = forms.ChoiceField(choices=VerificationApplication.CHECK_CHOICES)
    reason = forms.CharField(
        required=True,
        min_length=1,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, application_type, **kwargs):
        super().__init__(*args, **kwargs)
        if application_type == VerificationApplication.TYPE_REPAIR_WORKER:
            for name in ('aadhaar_status', 'pan_status', 'bank_status'):
                self.fields.pop(name)
        else:
            self.fields.pop('face_status')
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('reason') and not cleaned_data['reason'].strip():
            self.add_error('reason', 'Provide a non-blank review reason.')
        return cleaned_data
