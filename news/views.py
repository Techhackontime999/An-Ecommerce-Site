from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from .context_processors import active_news_items
from .models import NewsItem


def news_list(request):
    items = active_news_items()
    paginator = Paginator(items, 10)
    page = request.GET.get('page')
    items_page = paginator.get_page(page)
    return render(request, 'news/list.html', {
        'page_obj': items_page,
    })


def news_detail(request, pk, slug):
    item = NewsItem.objects.filter(pk=pk, slug=slug).first()
    if item is None or not item.is_active:
        raise Http404('News item not found or not published yet.')
    other_items = active_news_items().exclude(pk=item.pk)[:4]
    return render(request, 'news/detail.html', {
        'item': item,
        'other_items': other_items,
    })
