from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from .forms import SellerRegisterForm, CustomerRegisterForm, SellerProfileForm, CustomerProfileForm
from .models import SellerProfile, CustomerProfile


def signup(request):
    if request.method == 'POST':
        form = CustomerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            customers_group, created = Group.objects.get_or_create(name='customers')
            customers_group.user_set.add(user)
            login(request, user)
            return redirect(request.GET.get('next') or 'shop:product_list')
    else:
        form = CustomerRegisterForm()

    return render(request, 'registration/signup.html', {'form': form})


def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)

        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)

        if hasattr(user, 'sellerprofile'):
            return redirect('seller:seller_dashboard')
        elif hasattr(user, 'customerprofile'):
            return redirect('shop:product_list')

        return redirect('shop:product_list')

    return render(request, 'registration/login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })


def logout_view(request):
    logout(request)
    return redirect('shop:product_list')


def seller_register(request):
    if request.method == 'POST':
        form = SellerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
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
        profile = request.user.sellerprofile
        form_class = SellerProfileForm
    except SellerProfile.DoesNotExist:
        try:
            profile = request.user.customerprofile
            form_class = CustomerProfileForm
        except CustomerProfile.DoesNotExist:
            profile = CustomerProfile.objects.create(
                user=request.user, phone='', address=''
            )
            form_class = CustomerProfileForm

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('accounts:profile')
    else:
        form = form_class(instance=profile)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
    })
