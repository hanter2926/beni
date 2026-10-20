from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.forms import inlineformset_factory

from products.models import Product
from products.services import marketable_products

from .models import (
    RepairGuide,
    RepairGuideCategory,
    RepairGuideResource,
    RepairGuideStep,
    RepairGuideSubcategory,
    RepairQuestion,
    RepairAnswer,
)


class RepairGuideSubcategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.category.name} — {obj.name}'


class RepairGuideForm(forms.ModelForm):
    class Meta:
        model = RepairGuide
        fields = (
            'category',
            'subcategory',
            'title',
            'slug',
            'summary',
            'item_type',
            'supported_model',
            'symptoms',
            'possible_causes',
            'diagnosis',
            'difficulty',
            'estimated_minutes',
            'safety_warnings',
            'preparation',
            'expected_result',
            'troubleshooting',
            'related_guides',
        )
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 3}),
            'symptoms': forms.Textarea(attrs={'rows': 3}),
            'possible_causes': forms.Textarea(attrs={'rows': 3}),
            'diagnosis': forms.Textarea(attrs={'rows': 3}),
            'safety_warnings': forms.Textarea(attrs={'rows': 3}),
            'preparation': forms.Textarea(attrs={'rows': 3}),
            'expected_result': forms.Textarea(attrs={'rows': 3}),
            'troubleshooting': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = RepairGuideCategory.objects.filter(
            is_active=True,
        )
        self.fields['subcategory'] = RepairGuideSubcategoryChoiceField(
            queryset=RepairGuideSubcategory.objects.filter(
                category__is_active=True,
                is_active=True,
            ).select_related('category'),
            required=False,
        )
        self.fields['related_guides'].queryset = RepairGuide.objects.filter(
            status=RepairGuide.STATUS_PUBLISHED,
        )
        if self.instance.pk:
            self.fields['related_guides'].queryset = (
                self.fields['related_guides'].queryset.exclude(
                    pk=self.instance.pk,
                )
            )
        self._style_fields()

    def _style_fields(self):
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        subcategory = cleaned_data.get('subcategory')
        if subcategory and category and subcategory.category_id != category.pk:
            self.add_error(
                'subcategory',
                'Choose an item type within the selected category.',
            )
        return cleaned_data


class RepairGuideStepForm(forms.ModelForm):
    class Meta:
        model = RepairGuideStep
        fields = ('position', 'title', 'instructions', 'image')
        widgets = {
            'instructions': forms.Textarea(attrs={'rows': 4}),
        }


class RepairGuideStepFormSetBase(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        positions = set()
        for form in self.forms:
            if not form.has_changed() or (
                self.can_delete and self._should_delete_form(form)
            ):
                continue
            position = form.cleaned_data.get('position')
            if position in positions:
                raise ValidationError('Each repair step needs a unique position.')
            positions.add(position)


RepairGuideStepFormSet = inlineformset_factory(
    RepairGuide,
    RepairGuideStep,
    form=RepairGuideStepForm,
    formset=RepairGuideStepFormSetBase,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    max_num=30,
    validate_max=True,
)


class RepairGuideResourceForm(forms.ModelForm):
    class Meta:
        model = RepairGuideResource
        fields = (
            'resource_type',
            'name',
            'quantity',
            'product',
            'position',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = marketable_products(
            Product.objects.filter(stock_quantity__gt=0)
        ).select_related('shop')
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


RepairGuideResourceFormSet = inlineformset_factory(
    RepairGuide,
    RepairGuideResource,
    form=RepairGuideResourceForm,
    extra=1,
    can_delete=True,
    max_num=50,
    validate_max=True,
)


class RepairQuestionForm(forms.ModelForm):
    class Meta:
        model = RepairQuestion
        fields = (
            'category',
            'subcategory',
            'title',
            'body',
            'image',
            'related_guide',
            'related_product',
        )
        widgets = {'body': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = RepairGuideCategory.objects.filter(
            is_active=True,
        )
        self.fields['subcategory'] = RepairGuideSubcategoryChoiceField(
            queryset=RepairGuideSubcategory.objects.filter(
                category__is_active=True,
                is_active=True,
            ).select_related('category'),
            required=False,
        )
        self.fields['related_guide'].queryset = RepairGuide.objects.filter(
            status=RepairGuide.STATUS_PUBLISHED,
        )
        self.fields['related_product'].queryset = Product.objects.filter(
            pk__in=marketable_products(
                Product.objects.filter(stock_quantity__gt=0)
            ).values('pk')
        ).select_related('shop')
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class RepairAnswerForm(forms.ModelForm):
    class Meta:
        model = RepairAnswer
        fields = ('body',)
        widgets = {'body': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body'].widget.attrs['class'] = 'form-control'


class ContentReportForm(forms.Form):
    reason = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
    )
