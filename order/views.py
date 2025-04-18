# from django.shortcuts import render
# from cart.cart import Cart
# from .models import OrderItem
# from .forms import OrderCreateForm

# def order_create(request):
#     cart = Cart(request)
#     if request.method == 'POST':
#         form = OrderCreateForm(request.POST)
#         if form.is_valid():
            
#             order = form.save()
#             for item in cart:
#                 is_deal = item['product'].price != item['price']
#                 OrderItem.objects.create(
#                    order=order,
#                    product=item['product'],
#                    price=item['price'],
#                    quantity=item['quantity'],
#                    deal_applied=is_deal  # ✅ Track it
#                 )
#             # clear the cart
#             cart.clear()
#             return render(request, 'order/created.html', {'order': order})
#     else:
#         form = OrderCreateForm()
#     return render(request, 'order/create.html', {'cart': cart, 'form': form})



from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from cart.cart import Cart
from .models import OrderItem
from .forms import OrderCreateForm

@login_required
def order_create(request):
    cart = Cart(request)
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)   # ✅ Create order instance without saving
            order.user = request.user         # ✅ Now assign the user
            order.save()                      # ✅ Then save the order
            for item in cart:
                is_deal = item['product'].price != item['price']
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    price=item['price'],
                    quantity=item['quantity'],
                    deal_applied=is_deal
                )
            cart.clear()
            return render(request, 'order/created.html', {'order': order})
    else:
        form = OrderCreateForm()
    return render(request, 'order/create.html', {'cart': cart, 'form': form})
