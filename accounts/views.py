# from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group



from .forms import CustomUserCreationForm
def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # signal to add group customers
            customers_group, created = Group.objects.get_or_create(name='customers')
            customers_group.user_set.add(user)
            login(request, user)  # Automatically log the user in after signing up
            return redirect(request.GET.get('next') or 'shop:product_list')  # Redirect to home or another page
    else:
        form = CustomUserCreationForm()

    return render(request, 'registration/signup.html', {'form': form})

# from django.contrib.auth.forms import AuthenticationForm
# from django.contrib.auth import login
# from django.shortcuts import render, redirect

def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)
    
    if request.method == 'POST':
        if form.is_valid():
            login(request, form.get_user())
            # Redirect to next if exists, otherwise home or cart
            return redirect(request.POST.get('next') or 'shop:product_list')

    return render(request, 'registration/login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })


def logout_view(request):
    logout(request)
    return redirect('login')
