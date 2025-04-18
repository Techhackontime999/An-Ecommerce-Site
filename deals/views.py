# from django.shortcuts import render
from .models import Deal
from django.utils import timezone
from .models import Deal
from shop.models import Category
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404

from django.db.models import Avg
# def todays_deals(request, category_slug=None):
#     # Get all categories to display in the sidebar
#     categories = Category.objects.all()

#     # If category_slug is passed, filter deals based on category
#     if category_slug:
#         category = Category.objects.get(slug=category_slug)
#         deals = Deal.objects.filter(product__category=category, start_time__lte=timezone.now(), end_time__gte=timezone.now())
#     else:
#         # If no category is selected, display all deals
#         deals = Deal.objects.filter(start_time__lte=timezone.now(), end_time__gte=timezone.now())
    
#     return render(request, 'deals/todays_deals.html', {
#         'deals': deals,
#         'categories': categories,
#         'category': category if category_slug else None,
#     })



# def todays_deals(request, category_slug=None):
#     categories = Category.objects.all()
#     now = timezone.now()

#     if category_slug:
#         category = get_object_or_404(Category, slug=category_slug)
#         deals_list = Deal.objects.filter(
#             product__category=category,
#             start_time__lte=now,
#             end_time__gte=now
#         )
#     else:
#         category = None
#         deals_list = Deal.objects.filter(start_time__lte=now, end_time__gte=now)

#     # Apply pagination
#     paginator = Paginator(deals_list, 2)  # 9 deals per page
#     page_number = request.GET.get('page')
#     deals = paginator.get_page(page_number)

#     return render(request, 'deals/todays_deals.html', {
#         'deals': deals,
#         'categories': categories,
#         'category': category,
#     })


def todays_deals(request, category_slug=None):
    categories = Category.objects.all()
    now = timezone.now()

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        deals_list = Deal.objects.filter(
            product__category=category,
            start_time__lte=now,
            end_time__gte=now
        )
    else:
        category = None
        deals_list = Deal.objects.filter(
            start_time__lte=now,
            end_time__gte=now
        )

    paginator = Paginator(deals_list, 9)  # 9 deals per page
    page_number = request.GET.get('page')
    deals = paginator.get_page(page_number)

    return render(request, 'deals/todays_deals.html', {
        'deals': deals,
        'categories': categories,
        'category': category,
    })