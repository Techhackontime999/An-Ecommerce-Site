# from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from .forms import SellerRegisterForm
from .models import SellerProfile
from .forms import CustomerRegisterForm
from .models import CustomerProfile
from .forms import SellerProfileForm, CustomerProfileForm

def signup(request):
    if request.method == 'POST':
        form = CustomerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # signal to add group customers
            customers_group, created = Group.objects.get_or_create(name='customers')
            customers_group.user_set.add(user)
            login(request, user)  # Automatically log the user in after signing up
            return redirect(request.GET.get('next') or 'shop:product_list')  # Redirect to home or another page
    else:
        form = CustomerRegisterForm()

    return render(request, 'registration/signup.html', {'form': form})

# from django.contrib.auth.forms import AuthenticationForm
# from django.contrib.auth import login
# from django.shortcuts import render, redirect

# def login_view(request):
#     form = AuthenticationForm(request, data=request.POST or None)
    
#     if request.method == 'POST':
#         if form.is_valid():
#             login(request, form.get_user())
#             # Redirect to next if exists, otherwise home or cart
#             return redirect(request.POST.get('next') or 'shop:product_list')

#     return render(request, 'registration/login.html', {
#         'form': form,
#         'next': request.GET.get('next', '')
#     })
# def login_view(request):
#     form = AuthenticationForm(request, data=request.POST or None)

#     if request.method == 'POST':
#         if form.is_valid():
#             user = form.get_user()
#             login(request, user)

#             # Priority: next URL (if redirected from protected page)
#             next_url = request.POST.get('next')
#             if next_url:
#                 return redirect(next_url)

#             # Check user type
#             if hasattr(user, 'sellerprofile'):
#                 return redirect('seller:seller_dashboard')  # make sure this name is correct
#             elif hasattr(user, 'customerprofile'):
#                 return redirect('shop:product_list')

#             return redirect('shop:product_list')  # default fallback

#     return render(request, 'registration/login.html', {
#         'form': form,
#         'next': request.GET.get('next', '')
#     })

def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)

        print("Logged in user:", user.username)

        if hasattr(user, 'sellerprofile'):
            print("Redirecting to seller dashboard")
            return redirect('seller:seller_dashboard')
        elif hasattr(user, 'customerprofile'):
            print("Redirecting to customer product list")
            return redirect('shop:product_list')

        print("Redirecting to default")
        return redirect('shop:product_list')

    return render(request, 'registration/login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })



def logout_view(request):
    logout(request)
    return redirect('accounts:login')
# accounts/views.py



def seller_register(request):
    if request.method == 'POST':
        form = SellerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # signal to add group customers
            seller_group, created = Group.objects.get_or_create(name='sellers')
            seller_group.user_set.add(user)
            SellerProfile.objects.create(
                user=user,
                shop_name=form.cleaned_data['shop_name'],
                gst_number=form.cleaned_data['gst_number'],
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
            )
            login(request, user)
            return redirect('seller:seller_dashboard')
    else:
        form = SellerRegisterForm()
    return render(request, 'registration/seller_register.html', {'form': form})

@login_required
def profile_view(request):
    try:
        if hasattr(request.user, 'accounts:sellerprofile'):
            profile = request.user.sellerprofile
            form_class = SellerProfileForm
        else:
            profile = request.user.customerprofile
            form_class = CustomerProfileForm
    except (SellerProfile.DoesNotExist, CustomerProfile.DoesNotExist):
        return redirect('shop:product_list ')  # or wherever you want to handle this

    if request.method == 'POST':
        form = form_class(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('accounts:profile')  # reload profile page after saving
    else:
        form = form_class(instance=profile)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile
    })