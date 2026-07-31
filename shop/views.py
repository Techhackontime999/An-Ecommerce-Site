from django.shortcuts import render, get_object_or_404, redirect
from cart.forms import CartAddProductForm
from .models import Category, Product
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone


def home(request):
    trending = Product.objects.filter(available=True)[:8]
    hero_products = list(
        Product.objects.filter(available=True, image__isnull=False)
        .exclude(image='')[:16]
    )
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
        'hero_products': hero_products,
        'hero_layer_images': [p.image.url for p in hero_products],
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

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    current_ids = [p.id for p in page_obj.object_list]
    chunk_size = 4

    page_products = list(page_obj.object_list)

    popular_qs = (
        Product.objects.filter(available=True)
        .annotate(review_count=Count('reviews'))
        .order_by('-review_count')
        .prefetch_related('deals')
        .exclude(id__in=current_ids)
    )
    if category:
        fill_pool = list(popular_qs.filter(category=category)[:6]) + \
                    list(popular_qs.exclude(category=category)[:6])
    else:
        fill_pool = list(popular_qs[:12])

    product_rows = []
    current = []
    for p in page_products:
        current.append(p)
        if len(current) == chunk_size:
            product_rows.append(current)
            current = []
    if current:
        product_rows.append(current)

    for row in product_rows:
        need = chunk_size - len(row)
        if need > 0 and fill_pool:
            row.extend(fill_pool[:need])
            fill_pool = fill_pool[need:]

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
        'product_rows': product_rows,
        'suggested_products': suggested_products,
    })


def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    cart_product_form = CartAddProductForm()

    from reviews.models import ProductReview
    from django.db.models import Avg, Count
    approved = ProductReview.objects.filter(
        product=product,
        status=ProductReview.Status.APPROVED,
    ).select_related('reviewer').prefetch_related('helpful_votes')
    aggregate = approved.aggregate(average=Avg('overall_rating'))
    widget_total = approved.count()
    widget_average = round(aggregate['average'], 1) if aggregate['average'] else 0
    widget_recommend = (
        round(approved.filter(recommendation_rating__gte=70).count() / widget_total * 100)
        if widget_total else 0
    )
    user_review = (
        ProductReview.objects.filter(product=product, reviewer=request.user).first()
        if request.user.is_authenticated else None
    )

    related_qs = Product.objects.filter(available=True).prefetch_related('deals')
    same_category = related_qs.filter(category=product.category).exclude(id=product.id)[:6]
    if len(same_category) < 6:
        popular_qs = (
            Product.objects.filter(available=True)
            .annotate(review_count=Count('reviews'))
            .order_by('-review_count')
            .prefetch_related('deals')
            .exclude(id=product.id)
            .exclude(id__in=[p.id for p in same_category])
        )
        others = list(popular_qs[:6])
    else:
        others = []
    suggested_products = list(same_category) + others

    context = {
        'product': product,
        'cart_product_form': cart_product_form,
        'suggested_products': suggested_products[:12],
        'widget_reviews': approved[:3],
        'widget_total': widget_total,
        'widget_average': widget_average,
        'widget_recommend': widget_recommend,
        'user_review': user_review,
    }
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
