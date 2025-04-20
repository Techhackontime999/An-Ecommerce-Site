from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Review
from shop.models import Product
from order.models import OrderItem  # Adjust based on your actual order app

def create_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    # Create a review for a seller
    # Check if user has purchased the product
    has_ordered = OrderItem.objects.filter(
        order__user=request.user,
        product=product
    ).exists()

    if not has_ordered:
        messages.error(request, "You can only review products you have purchased.")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)

    # Check if already reviewed
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.warning(request, "You have already reviewed this product.")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)


    if request.method == "POST":
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment')
        Review.objects.create(product=product, user=request.user, rating=rating, comment=comment)
        messages.success(request, "Thanks for your review!")
        return redirect('shop:product_detail', id=product.id, slug=product.slug)


    return render(request, 'reviews/review_form.html', {'product': product})


   

