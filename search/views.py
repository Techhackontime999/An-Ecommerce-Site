# shop/views.py
from django.db.models import Q
from django.shortcuts import render
from shop.models import Product

def product_search(request):
    query = request.GET.get("q")
    products = []

    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        ).distinct()

    return render(request, "search/search_results.html", {
        "query": query,
        "products": products
    })
