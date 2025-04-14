from django.shortcuts import render
from .models import Deal
from django.utils import timezone
from .models import Deal
from shop.models import Category


def todays_deals(request, category_slug=None):
    # Get all categories to display in the sidebar
    categories = Category.objects.all()

    # If category_slug is passed, filter deals based on category
    if category_slug:
        category = Category.objects.get(slug=category_slug)
        deals = Deal.objects.filter(product__category=category, start_time__lte=timezone.now(), end_time__gte=timezone.now())
    else:
        # If no category is selected, display all deals
        deals = Deal.objects.filter(start_time__lte=timezone.now(), end_time__gte=timezone.now())

    return render(request, 'deals/todays_deals.html', {
        'deals': deals,
        'categories': categories,
        'category': category if category_slug else None,
    })