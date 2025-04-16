# seller/forms.py

from django import forms
from shop.models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ['seller', 'created', 'updated']
