# seller/forms.py
from django import forms
from shop.models import Product
from ckeditor.widgets import CKEditorWidget

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # Use exclude OR fields, not both
        exclude = ['seller', 'created', 'updated']
        widgets = {
            'description': CKEditorWidget(),
        }


       