import json
from django.shortcuts import render, get_object_or_404, redirect
from cart.forms import CartAddProductForm
from .models import Category, Product
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator
from platform_studio.utils import get_setting


def home(request):
    trending = Product.objects.with_rating().with_deal_price().filter(available=True)[:8]
    hero_products = list(
        Product.objects.with_deal_price().filter(available=True, image__isnull=False)
        .exclude(image='')[:16]
    )
    now = timezone.now()
    deals = Product.objects.with_rating().with_deal_price().filter(
        available=True,
        deals__start_time__lte=now,
        deals__end_time__gte=now
    ).distinct()[:4]
    if not deals:
        deals = Product.objects.with_rating().with_deal_price().filter(available=True)[:4]
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
        products = Product.objects.with_rating().with_deal_price().filter(category=category, available=True)
    else:
        products = Product.objects.with_rating().with_deal_price().filter(available=True)

    per_page = 12
    try:
        per_page = int(get_setting('products_per_page', '12') or 12)
    except (TypeError, ValueError):
        per_page = 12
    if per_page < 1:
        per_page = 12
    paginator = Paginator(products, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    current_ids = [p.id for p in page_obj.object_list]
    chunk_size = 4

    page_products = list(page_obj.object_list)

    popular_qs = (
        Product.objects.with_rating().with_deal_price().filter(available=True)
        .annotate(review_count=Count('product_reviews'))
        .order_by('-review_count')
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

    suggested_qs = Product.objects.with_rating().with_deal_price().filter(available=True)
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
    product = get_object_or_404(
        Product.objects.with_rating().with_deal_price(),
        id=id, slug=slug, available=True,
    )
    cart_product_form = CartAddProductForm()

    from reviews.models import ProductReview
    from django.db.models import Avg, Count
    approved = ProductReview.objects.filter(
        product=product,
        status=ProductReview.Status.APPROVED,
    ).select_related('reviewer').prefetch_related('helpful_votes', 'images')
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

    from reviews.models import has_paid_order
    user_purchased = has_paid_order(request.user, product) if request.user.is_authenticated else False

    related_qs = Product.objects.with_rating().with_deal_price().filter(available=True)
    same_category = related_qs.filter(category=product.category).exclude(id=product.id)[:6]
    if len(same_category) < 6:
        popular_qs = (
            Product.objects.with_rating().with_deal_price().filter(available=True)
            .annotate(review_count=Count('product_reviews', filter=Q(product_reviews__status='approved')))
            .order_by('-review_count')
            .exclude(id=product.id)
            .exclude(id__in=[p.id for p in same_category])
        )
        others = list(popular_qs[:6])
    else:
        others = []
    suggested_products = list(same_category) + others

    first_variant = product.first_active_variant
    first_available_variant = product.active_variants.filter(stock__gt=0).first() or first_variant
    default_variant = first_available_variant or first_variant
    has_variant_options = product.active_variants.count() > 1
    variant_descriptions = {
        v.id: (v.description or '') for v in product.active_variants.all()
    }
    merged_description = product.description or ''
    if default_variant and default_variant.description:
        extra = default_variant.description.strip()
        if extra and extra != (product.description or '').strip():
            merged_description = (merged_description + '\n' + extra).strip()
    if first_variant:
        display_price = first_variant.effective_price
    else:
        display_price = product.current_price
    mrp = product.price
    try:
        discount_percent = round((1 - float(display_price) / float(mrp)) * 100) if mrp else 0
    except (TypeError, ValueError, ZeroDivisionError):
        discount_percent = 0
    if discount_percent < 0:
        discount_percent = 0

    page_url = f'{request.scheme}://{request.get_host()}{product.get_absolute_url()}'
    product_json_ld = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': product.name,
        'description': str(Truncator(strip_tags(product.description or '')).words(40)),
        'sku': str(product.id),
        'brand': product.brand or None,
        'image': (f'{request.scheme}://{request.get_host()}{product.image.url}'
                  if product.image else None),
        'offers': {
            '@type': 'Offer',
            'url': page_url,
            'priceCurrency': 'USD',
            'price': f'{display_price:.2f}',
            'availability': ('https://schema.org/InStock' if product.available
                             else 'https://schema.org/OutOfStock'),
        },
        'aggregateRating': {
            '@type': 'AggregateRating',
            'ratingValue': f'{widget_average:.1f}',
            'reviewCount': str(widget_total),
        },
    }

    context = {
        'product': product,
        'cart_product_form': cart_product_form,
        'suggested_products': suggested_products[:12],
        'widget_reviews': approved[:3],
        'widget_total': widget_total,
        'widget_average': widget_average,
        'widget_recommend': widget_recommend,
        'user_review': user_review,
        'user_purchased': user_purchased,
        'first_available_variant': first_available_variant,
        'has_variant_options': has_variant_options,
        'variant_descriptions': variant_descriptions,
        'merged_description': merged_description,
        'display_price': display_price,
        'mrp': mrp,
        'discount_percent': discount_percent,
        'product_json_ld': json.dumps(product_json_ld),
    }
    return render(request, 'shop/product/detail.html', context)


def product_search(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', 'relevance').strip()

    products = Product.objects.with_rating().with_deal_price().filter(available=True)
    product_categories = Category.objects.all()

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    sort_map = {
        'price_asc': ('price', 'price'),
        'price_desc': ('-price', 'price_desc'),
        'newest': ('-created', 'newest'),
        'rating': ('-_avg_rating', 'rating'),
        'name': ('name', 'name'),
    }
    order, active_sort = sort_map.get(sort, (None, 'relevance'))
    if order:
        products = products.order_by(order)

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "shop/product/product_search.html", {
        "results": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "selected_category": category_slug,
        "product_categories": product_categories,
        "sort": active_sort,
        "search_action": "shop:product_search",
    })
