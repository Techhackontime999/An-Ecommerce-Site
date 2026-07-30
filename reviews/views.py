from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Review
from shop.models import Product
from order.models import OrderItem


@login_required
def create_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    has_ordered = OrderItem.objects.filter(
        order__user=request.user,
        product=product
    ).exists()

    if not has_ordered:
        messages.error(request, "You can only review products you have purchased.")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)

    if Review.objects.filter(product=product, user=request.user).exists():
        messages.warning(request, "You have already reviewed this product.")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)

    if request.method == "POST":
        try:
            rating = int(request.POST.get('rating', 0))
        except (ValueError, TypeError):
            messages.error(request, "Invalid rating value.")
            return redirect('shop:product_detail', id=product.id, slug=product.slug)

        if rating < 1 or rating > 5:
            messages.error(request, "Rating must be between 1 and 5.")
            return redirect('shop:product_detail', id=product.id, slug=product.slug)

        comment = request.POST.get('comment', '').strip()
        Review.objects.create(product=product, user=request.user, rating=rating, comment=comment)
        messages.success(request, "Thanks for your review!")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)

    return render(request, 'reviews/review_form.html', {'product': product})
