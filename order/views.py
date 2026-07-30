
from django.shortcuts import render, redirect
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
            return redirect('payments:checkout', order_id=order.id)
    else:
        form = OrderCreateForm()
    return render(request, 'order/create.html', {'cart': cart, 'form': form})
