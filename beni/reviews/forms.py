from django import forms

from .models import Review


class ReviewSubmissionForm(forms.Form):
    rating = forms.TypedChoiceField(
        choices=tuple((value, f'{value} out of 5') for value in range(1, 6)),
        coerce=int,
        label='Rating',
    )
    body = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={'rows': 4}),
        label='Your review',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class ReviewModerationForm(forms.Form):
    status = forms.ChoiceField(
        choices=(
            (Review.STATUS_PUBLISHED, 'Publish'),
            (Review.STATUS_REJECTED, 'Do not publish'),
        ),
        label='Moderation decision',
    )
    moderation_note = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Note to customer',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get('status') == Review.STATUS_REJECTED
            and not cleaned_data.get('moderation_note', '').strip()
        ):
            self.add_error(
                'moderation_note',
                'Add a brief reason when declining a review.',
            )
        return cleaned_data
