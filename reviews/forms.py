from django import forms

from .models import ProductReview, ReviewReport


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        if data is None:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned = []
        for single_file in data:
            cleaned.append(super().clean(single_file))
        return cleaned


class ProductReviewForm(forms.ModelForm):
    overall_rating = forms.ChoiceField(
        choices=[(i, f'{i} star' + ('' if i == 1 else 's')) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'review-star-input'}),
    )

    image = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'form-control blog-field-input',
            'accept': 'image/*',
        }),
    )

    class Meta:
        model = ProductReview
        fields = (
            'overall_rating',
            'performance',
            'value',
            'quality',
            'recommendation_rating',
            'pros',
            'cons',
            'review_text',
            'video_url',
        )
        widgets = {
            'performance': forms.Select(attrs={'class': 'form-control blog-field-input'}),
            'value': forms.Select(attrs={'class': 'form-control blog-field-input'}),
            'quality': forms.Select(attrs={'class': 'form-control blog-field-input'}),
            'recommendation_rating': forms.NumberInput(attrs={
                'class': 'form-control blog-field-input',
                'min': 0,
                'max': 100,
            }),
            'pros': forms.Textarea(attrs={
                'class': 'form-control blog-field-input',
                'rows': 2,
                'placeholder': 'What did you like?',
            }),
            'cons': forms.Textarea(attrs={
                'class': 'form-control blog-field-input',
                'rows': 2,
                'placeholder': 'What could be better?',
            }),
            'review_text': forms.Textarea(attrs={
                'class': 'form-control blog-field-input',
                'rows': 5,
                'placeholder': 'Share your honest experience with this product...',
            }),
            'video_url': forms.URLInput(attrs={
                'class': 'form-control blog-field-input',
                'placeholder': 'https://youtube.com/watch?v=...',
            }),
        }

    def clean_image(self):
        images = self.files.getlist('image') if self.files else []
        if len(images) > ProductReview.MAX_IMAGES:
            raise forms.ValidationError(f'You can upload a maximum of {ProductReview.MAX_IMAGES} photos.')
        return images

    def clean_recommendation_rating(self):
        value = self.cleaned_data.get('recommendation_rating') or 0
        if value < 0 or value > 100:
            raise forms.ValidationError('Recommendation must be between 0 and 100.')
        return value


class ReviewReportForm(forms.ModelForm):
    class Meta:
        model = ReviewReport
        fields = ('reason', 'details')
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-control blog-field-input'}),
            'details': forms.Textarea(attrs={
                'class': 'form-control blog-field-input',
                'rows': 3,
            }),
        }
