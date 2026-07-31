from django.shortcuts import render, get_object_or_404, redirect
from cart.forms import CartAddProductForm
from .models import Category, Product
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone


def home(request):
    trending = Product.objects.filter(available=True)[:8]
    now = timezone.now()
    deals = Product.objects.filter(
        available=True,
        deals__start_time__lte=now,
        deals__end_time__gte=now
    ).distinct()[:4]
    if not deals:
        deals = Product.objects.filter(available=True)[:4]
    return render(request, 'shop/home.html', {
        'trending_products': trending,
        'deals': deals,
    })


def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=category, available=True)
    else:
        products = Product.objects.filter(available=True)

    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    current_ids = [p.id for p in page_obj.object_list]
    suggested_qs = Product.objects.filter(available=True).prefetch_related('deals')
    if category:
        suggested_qs = suggested_qs.filter(category=category)
    if current_ids:
        suggested_qs = suggested_qs.exclude(id__in=current_ids)
    suggested_products = suggested_qs[:10]

    return render(request, 'shop/product/list.html', {
        'category': category,
        'categories': categories,
        'products': page_obj,
        'suggested_products': suggested_products,
    })


def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    cart_product_form = CartAddProductForm()
    context = {'product': product, 'cart_product_form': cart_product_form}
    return render(request, 'shop/product/detail.html', context)


def product_search(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()

    products = Product.objects.filter(available=True)
    product_categories = Category.objects.all()

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    return render(request, "shop/product/product_search.html", {
        "results": products,
        "query": query,
        "selected_category": category_slug,
        "product_categories": product_categories,
        "search_action": "shop:product_search",
    })
