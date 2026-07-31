from django import forms
from django.utils.text import slugify

from shop.models import Product

from .models import Comment, Post, PostReport, PostProduct, Tag


class TagInputMixin:
    tag_widget_attrs = {
        'class': 'form-control blog-field-input',
        'placeholder': 'e.g. audio, deals, travel',
    }

    def clean_tags(self):
        raw = self.cleaned_data.get('tags') or []
        names = []
        if isinstance(raw, list):
            for item in raw:
                names.extend(name.strip() for name in str(item).split(','))
        else:
            names.extend(name.strip() for name in str(raw).split(','))
        names = [n for n in names if n]
        tags = []
        for name in list(dict.fromkeys(names))[:8]:
            slug = slugify(name)[:60]
            if not slug:
                continue
            tag, _ = Tag.objects.get_or_create(
                slug=slug,
                defaults={'name': name[:60]},
            )
            tags.append(tag)
        return tags


class PostForm(TagInputMixin, forms.ModelForm):
    tags = forms.CharField(
        required=False,
        label='Tags',
        widget=forms.TextInput(attrs=TagInputMixin.tag_widget_attrs),
    )
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all().order_by('name'),
        required=False,
        label='Linked products',
        widget=forms.SelectMultiple(attrs={'class': 'form-control blog-field-input'}),
    )
    product_role = forms.ChoiceField(
        choices=PostProduct.Role.choices,
        required=False,
        label='Product role',
        help_text='Applies to every linked product.',
        widget=forms.Select(attrs={'class': 'form-control blog-field-input'}),
    )
    publish_at = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control blog-field-input', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
    )

    class Meta:
        model = Post
        fields = (
            'title', 'post_type', 'body', 'excerpt', 'tags', 'products',
            'product_role', 'featured_image', 'video_url', 'status', 'publish_at',
            'allow_comments', 'meta_title', 'meta_description',
        )
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control blog-field-input',
                'placeholder': 'A headline people actually want to read',
            }),
            'post_type': forms.Select(attrs={'class': 'form-control blog-field-input'}),
            'body': forms.Textarea(attrs={
                'class': 'form-control blog-field-input blog-field-body',
                'rows': 14,
            }),
            'excerpt': forms.TextInput(attrs={
                'class': 'form-control blog-field-input',
                'placeholder': 'A one-line summary shown on cards (optional)',
            }),
            'featured_image': forms.ClearableFileInput(attrs={'class': 'form-control blog-field-input'}),
            'video_url': forms.URLInput(attrs={
                'class': 'form-control blog-field-input',
                'placeholder': 'https://www.youtube.com/watch?v=... or https://.../demo.mp4',
            }),
            'status': forms.Select(attrs={'class': 'form-control blog-field-input'}),
            'allow_comments': forms.CheckboxInput(attrs={'class': 'blog-check-input'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control blog-field-input'}),
            'meta_description': forms.Textarea(attrs={
                'class': 'form-control blog-field-input',
                'rows': 2,
            }),
        }

    def clean_publish_at(self):
        value = self.cleaned_data.get('publish_at')
        if value is None:
            from django.utils import timezone
            return timezone.now()
        return value

    def clean_slug(self):
        return self.cleaned_data.get('slug')

    def _auto_slug(self):
        base = self.cleaned_data.get('title')
        if not base:
            return None
        from .models import _unique_slug
        return _unique_slug(self.instance, base)


class CommentForm(forms.ModelForm):
    parent_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'comment-parent-id'}),
    )

    class Meta:
        model = Comment
        fields = ('body',)
        widgets = {
            'body': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'Share your thoughts... use @username to mention someone',
                    'class': 'blog-comment-input',
                }
            ),
        }

    def save(self, commit=True):
        comment = super().save(commit=False)
        parent_id = self.cleaned_data.get('parent_id')
        if parent_id and not comment.parent:
            comment.parent_id = parent_id
        if commit:
            comment.save()
        return comment


class PostReportForm(forms.ModelForm):
    class Meta:
        model = PostReport
        fields = ('reason', 'details')
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-control blog-field-input'}),
            'details': forms.Textarea(attrs={
                'class': 'form-control blog-field-input',
                'rows': 3,
                'placeholder': 'Anything the moderation team should know?',
            }),
        }
