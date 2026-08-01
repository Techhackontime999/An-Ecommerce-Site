from django import forms
from .models import Order

class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'email', 'address', 'postal_code', 'city']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': 'First name',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Last name',
                'autocomplete': 'family-name',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'you@example.com',
                'autocomplete': 'email',
                'inputmode': 'email',
            }),
            'address': forms.TextInput(attrs={
                'placeholder': 'House number, street, area',
                'autocomplete': 'street-address',
            }),
            'postal_code': forms.TextInput(attrs={
                'placeholder': 'e.g. 110001',
                'autocomplete': 'postal-code',
                'inputmode': 'numeric',
            }),
            'city': forms.TextInput(attrs={
                'placeholder': 'City',
                'autocomplete': 'address-level2',
            }),
        }
