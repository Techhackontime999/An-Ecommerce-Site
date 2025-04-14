from django.shortcuts import render
from .models import Deal
from django.utils import timezone

def todays_deals(request):
    now = timezone.now()
    deals = Deal.objects.filter(start_time__lte=now, end_time__gte=now)
    return render(request, 'deals/todays_deals.html', {'deals': deals})
