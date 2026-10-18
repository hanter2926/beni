from django import forms

from beni.upload_forms import MultipleDocumentField

from .models import VerificationApplication, VerificationDocument


class VerificationSubmissionForm(forms.Form):
    confirmation = forms.BooleanField(
        required=True,
        label='I want to submit this application for staff review.',
    )
    documents = MultipleDocumentField(
        required=False,
        max_files=5,
        label='Supporting documents',
        help_text='Optional. Up to five JPEG, PNG, WebP, or PDF files, 10 MB each.',
    )

    def __init__(self, *args, application=None, application_type, **kwargs):
        super().__init__(*args, **kwargs)
        self.application = application
        self.application_type = application_type
        self.fields['documents'].widget.attrs['accept'] = (
            'image/jpeg,image/png,image/webp,application/pdf,.pdf'
        )
        self.fields['documents'].widget.attrs['aria-describedby'] = 'id_documents_help'
        self.fields['document_type'] = forms.ChoiceField(
            choices=self._document_type_choices(),
            required=False,
            label='Document type',
        )
        self.fields['remove_documents'] = forms.ModelMultipleChoiceField(
            queryset=(
                VerificationDocument.objects.filter(application=application)
                if application
                else VerificationDocument.objects.none()
            ),
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label='Remove previously submitted documents',
        )
        attrs = self.fields['confirmation'].widget.attrs
        if self.is_bound and self.errors.get('confirmation'):
            attrs['aria-invalid'] = 'true'
            attrs['aria-describedby'] = 'id_confirmation_errors'

    def _document_type_choices(self):
        allowed_types = (
            {
                VerificationDocument.TYPE_IDENTITY,
                VerificationDocument.TYPE_ADDRESS,
                VerificationDocument.TYPE_TAX,
                VerificationDocument.TYPE_BANK,
                VerificationDocument.TYPE_BUSINESS,
                VerificationDocument.TYPE_OTHER,
            }
            if self.application_type == VerificationApplication.TYPE_SHOPKEEPER
            else {
                VerificationDocument.TYPE_IDENTITY,
                VerificationDocument.TYPE_ADDRESS,
                VerificationDocument.TYPE_QUALIFICATION,
                VerificationDocument.TYPE_OTHER,
            }
        )
        return [
            ('', 'Choose a document type'),
            *[
                (value, label)
                for value, label in VerificationDocument.TYPE_CHOICES
                if value in allowed_types
            ],
        ]

    def clean(self):
        cleaned_data = super().clean()
        documents = cleaned_data.get('documents', [])
        document_type = cleaned_data.get('document_type')
        removals = cleaned_data.get('remove_documents')
        if documents and not document_type:
            self.add_error('document_type', 'Choose a document type.')
        if (
            self.application
            and self.application.status == VerificationApplication.STATUS_APPROVED
            and (documents or (removals and removals.exists()))
        ):
            raise forms.ValidationError(
                'Documents cannot be changed after verification is approved.'
            )
        existing_count = (
            self.application.documents.count() if self.application else 0
        )
        if existing_count - (removals.count() if removals else 0) + len(documents) > 5:
            self.add_error('documents', 'An application can have no more than five documents.')
        return cleaned_data


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
