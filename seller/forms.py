# seller/forms.py
from django import forms
from accounts.models import SellerDocument
from shop.models import Product, ProductVariant
from ckeditor.widgets import CKEditorWidget
from django.forms.models import inlineformset_factory


class SellerDocumentForm(forms.ModelForm):
    class Meta:
        model = SellerDocument
        fields = ['document_type', 'file', 'description']
        widgets = {
            'description': forms.TextInput(attrs={'placeholder': 'Optional note about this document'}),
        }


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        if data is None:
            return []
        single_file_clean = forms.FileField.clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(self, d) for d in data]
        return [single_file_clean(self, data)]

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        if not data:
            return False
        return super().has_changed(initial, data)


class ProductForm(forms.ModelForm):
    gallery_images = MultiFileField(
        required=False,
        label='Additional photos',
        help_text='Upload one or more extra photos for this product.',
    )

    class Meta:
        model = Product
        exclude = ['seller', 'created', 'updated']
        widgets = {
            'description': CKEditorWidget(),
        }


class ProductVariantForm(forms.ModelForm):
    gallery_images = MultiFileField(
        required=False,
        label='Variant gallery',
        help_text='Multiple photos for this variant only.',
    )

    class Meta:
        model = ProductVariant
        fields = ['name', 'sku', 'price', 'stock', 'description', 'image', 'active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Size 3-6'}),
            'sku': forms.TextInput(attrs={'placeholder': 'Optional SKU'}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Optional'}),
            'stock': forms.NumberInput(attrs={'min': 0}),
            'description': CKEditorWidget(),
        }


VariantsFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=1,
    can_delete=True,
)
