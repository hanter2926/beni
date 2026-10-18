from django import forms
from django.utils import timezone

from beni.upload_forms import MultipleImageField

from .models import RepairBooking, RepairBookingImage
from .services import WORKER_TRANSITIONS, active_repair_workers


class RepairBookingForm(forms.ModelForm):
    images = MultipleImageField(
        required=False,
        max_files=5,
        max_size=5 * 1024 * 1024,
        label='Photos of the issue',
        help_text='Optional. Up to five JPEG, PNG, or WebP images, 5 MB each.',
    )

    class Meta:
        model = RepairBooking
        fields = (
            'service_category',
            'problem_description',
            'service_address',
            'preferred_at',
        )
        widgets = {
            'problem_description': forms.Textarea(attrs={'rows': 4}),
            'service_address': forms.Textarea(attrs={'rows': 3}),
            'preferred_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['images'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field.help_text:
                field.widget.attrs['aria-describedby'] = f'id_{name}_help'
            if self.is_bound and self.errors.get(name):
                field.widget.attrs['aria-invalid'] = 'true'
                existing = field.widget.attrs.get('aria-describedby')
                field.widget.attrs['aria-describedby'] = ' '.join(
                    part
                    for part in (existing, f'id_{name}_errors')
                    if part
                )

    def clean_preferred_at(self):
        preferred_at = self.cleaned_data['preferred_at']
        if preferred_at <= timezone.now():
            raise forms.ValidationError(
                'Choose a preferred appointment time in the future.'
            )
        return preferred_at


class BookingImageForm(forms.Form):
    images = MultipleImageField(
        required=False,
        max_files=5,
        max_size=5 * 1024 * 1024,
        label='Repair photos',
        help_text='JPEG, PNG, or WebP; up to five images, 5 MB each.',
    )

    def __init__(self, *args, booking, image_types, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.booking = booking
        self.actor = actor
        self.image_types = tuple(image_types)
        self.fields['images'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'
        self.fields['image_type'] = forms.ChoiceField(
            choices=[
                (value, label)
                for value, label in RepairBookingImage.TYPE_CHOICES
                if value in self.image_types
            ],
            required=False,
            label='Photo type',
        )
        self.fields['image_type'].widget.attrs['class'] = 'form-control'
        self.fields['remove_images'] = forms.ModelMultipleChoiceField(
            queryset=RepairBookingImage.objects.filter(
                booking=booking,
                uploaded_by=actor,
                image_type__in=self.image_types,
            ),
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label='Remove photos uploaded by you',
        )

    def clean(self):
        cleaned_data = super().clean()
        images = cleaned_data.get('images', [])
        image_type = cleaned_data.get('image_type')
        removals = cleaned_data.get('remove_images')
        if images:
            if not image_type:
                self.add_error('image_type', 'Choose a photo type.')
        if self.booking.images.count() - (removals.count() if removals else 0) + len(images) > 10:
            self.add_error('images', 'A booking can have no more than ten photos.')
        if not images and not removals:
            raise forms.ValidationError('Choose new photos or select photos to remove.')
        return cleaned_data


class WorkerAssignmentForm(forms.Form):
    worker = forms.ModelChoiceField(
        queryset=active_repair_workers(),
        label='Assign to Repair Worker',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['worker'].queryset = active_repair_workers()
        self.fields['worker'].widget.attrs['class'] = 'form-control'


class WorkerBookingStatusForm(forms.Form):
    status = forms.ChoiceField(label='Update job status', required=False)
    images = MultipleImageField(
        required=False,
        max_files=5,
        max_size=5 * 1024 * 1024,
        label='Add job photos',
        help_text='Optional. JPEG, PNG, or WebP; up to five images, 5 MB each.',
    )

    def __init__(self, *args, current_status, booking=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.booking = booking
        self.actor = actor
        allowed_statuses = sorted(WORKER_TRANSITIONS.get(current_status, set()))
        self.fields['status'].choices = [
            (status, dict(RepairBooking.STATUS_CHOICES)[status])
            for status in allowed_statuses
        ]
        self.fields['status'].widget.attrs['class'] = 'form-control'
        self.fields['images'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'
        self.fields['image_type'] = forms.ChoiceField(
            choices=[
                (RepairBookingImage.TYPE_WORKER_VISIT_PROOF, 'Visit proof'),
                (RepairBookingImage.TYPE_REPAIR_PROGRESS, 'Repair progress'),
                (RepairBookingImage.TYPE_COMPLETED_WORK, 'Completed repair'),
            ],
            required=False,
            label='Photo type',
        )
        self.fields['image_type'].widget.attrs['class'] = 'form-control'
        self.fields['remove_images'] = forms.ModelMultipleChoiceField(
            queryset=(
                RepairBookingImage.objects.filter(
                    booking=booking,
                    uploaded_by=actor,
                    image_type__in=(
                        RepairBookingImage.TYPE_WORKER_VISIT_PROOF,
                        RepairBookingImage.TYPE_REPAIR_PROGRESS,
                        RepairBookingImage.TYPE_COMPLETED_WORK,
                    ),
                )
                if booking and actor
                else RepairBookingImage.objects.none()
            ),
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label='Remove job photos uploaded by you',
        )

    def clean(self):
        cleaned_data = super().clean()
        images = cleaned_data.get('images', [])
        status = cleaned_data.get('status')
        removals = cleaned_data.get('remove_images')
        if not status and not images and not removals:
            raise forms.ValidationError(
                'Choose a job status, add job photos, or select photos to remove.'
            )
        if images:
            if not cleaned_data.get('image_type'):
                self.add_error('image_type', 'Choose a photo type.')
            if (
                self.booking
                and self.booking.images.count()
                - (removals.count() if removals else 0)
                + len(images) > 10
            ):
                self.add_error('images', 'A booking can have no more than ten photos.')
        return cleaned_data
