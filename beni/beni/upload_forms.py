from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from .upload_validation import validate_decoded_image, validate_verification_document


class MultipleUploadInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleUploadInput

    def __init__(self, *args, max_files=5, max_size, **kwargs):
        self.max_files = max_files
        self.max_size = max_size
        super().__init__(*args, **kwargs)
        self.widget.attrs['data-image-preview-input'] = ''

    def clean(self, data, initial=None):
        uploads = [data] if isinstance(data, UploadedFile) else list(data or [])
        if len(uploads) > self.max_files:
            raise ValidationError(f'Choose no more than {self.max_files} images.')

        cleaned = []
        errors = []
        for upload in uploads:
            try:
                image = super().clean(upload, initial=None)
                cleaned.append(validate_decoded_image(image, max_size=self.max_size))
            except ValidationError as exc:
                errors.extend(exc.error_list)
        if errors:
            raise ValidationError(errors)
        return cleaned


class MultipleDocumentField(forms.FileField):
    widget = MultipleUploadInput

    def __init__(self, *args, max_files=5, **kwargs):
        self.max_files = max_files
        super().__init__(*args, **kwargs)
        self.widget.attrs['data-image-preview-input'] = ''

    def clean(self, data, initial=None):
        uploads = [data] if isinstance(data, UploadedFile) else list(data or [])
        if len(uploads) > self.max_files:
            raise ValidationError(f'Choose no more than {self.max_files} documents.')

        cleaned = []
        errors = []
        for upload in uploads:
            try:
                document = super().clean(upload, initial=None)
                cleaned.append(validate_verification_document(document))
            except ValidationError as exc:
                errors.extend(exc.error_list)
        if errors:
            raise ValidationError(errors)
        return cleaned
