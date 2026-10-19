from django import forms


class PaidOrderCancellationForm(forms.Form):
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={'rows': 4}),
    )


class CancellationReviewForm(forms.Form):
    notes = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
