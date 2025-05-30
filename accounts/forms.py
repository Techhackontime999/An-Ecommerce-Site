
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import SellerProfile, CustomerProfile


# accounts/forms.py

class SellerRegisterForm(UserCreationForm):
    shop_name = forms.CharField(max_length=100,required=False)
    gst_number = forms.CharField(max_length=15, required=False)  # Optional GST field  
    bank_account = forms.CharField(max_length=15, required=True) 
    phone = forms.CharField(max_length=15,required=True)
    address = forms.CharField(widget=forms.Textarea,required=True)
    email = forms.EmailField(required=True)
    profile_picture=forms.ImageField(required=False)
    

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class CustomerRegisterForm(UserCreationForm):
    phone = forms.CharField(max_length=15)
    address = forms.CharField(widget=forms.Textarea)
    email = forms.EmailField(required=True)
    profile_picture=forms.ImageField(required=False)
    
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class SellerProfileForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = ['shop_name', 'gst_number', 'phone', 'address', 'description' ,'profile_picture']

class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ['phone', 'address']