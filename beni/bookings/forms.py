from django import forms
from django.utils import timezone

from .models import RepairBooking
from .services import WORKER_TRANSITIONS, active_repair_workers


class RepairBookingForm(forms.ModelForm):
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
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if self.is_bound and self.errors.get(name):
                field.widget.attrs['aria-invalid'] = 'true'
                field.widget.attrs['aria-describedby'] = f'id_{name}_errors'

    def clean_preferred_at(self):
        preferred_at = self.cleaned_data['preferred_at']
        if preferred_at <= timezone.now():
            raise forms.ValidationError(
                'Choose a preferred appointment time in the future.'
            )
        return preferred_at


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
    status = forms.ChoiceField(label='Update job status')

    def __init__(self, *args, current_status, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_statuses = sorted(WORKER_TRANSITIONS.get(current_status, set()))
        self.fields['status'].choices = [
            (status, dict(RepairBooking.STATUS_CHOICES)[status])
            for status in allowed_statuses
        ]
        self.fields['status'].widget.attrs['class'] = 'form-control'
