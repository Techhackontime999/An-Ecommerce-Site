from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import Notification, NotificationPreference
from .services import CATEGORY_FIELD, get_user_role, unread_count

PER_PAGE = 25

CATEGORY_ICONS = {
    'order': 'box',
    'payment': 'credit-card',
    'shipping': 'truck-fast',
    'deal': 'tags',
    'review': 'star',
    'account': 'user-shield',
    'system': 'gear',
    'promo': 'gift',
}


@login_required
def notification_list(request):
    category = request.GET.get('category', '').strip()
    qs = Notification.objects.filter(recipient=request.user)
    valid_categories = dict(Notification.Category.choices)
    if category in valid_categories:
        qs = qs.filter(category=category)
    else:
        category = ''

    page = request.GET.get('page', 1)
    try:
        page = max(int(page), 1)
    except (TypeError, ValueError):
        page = 1

    total = qs.count()
    notifications = qs[((page - 1) * PER_PAGE):(page * PER_PAGE)]
    unread = unread_count(request.user)

    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'unread': unread,
        'category': category,
        'categories': valid_categories,
        'page': page,
        'total': total,
        'has_prev': page > 1,
        'has_next': page * PER_PAGE < total,
    })


@login_required
def notification_settings(request):
    prefs, created_prefs = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        for category, field in CATEGORY_FIELD.items():
            setattr(prefs, field, request.POST.get(field) == 'on')
        prefs.email_enabled = request.POST.get('email_enabled') == 'on'
        prefs.save()
        messages.success(request, _('Your notification settings have been saved.'))
        return redirect('notifications:settings')

    fields = [
        {
            'category': category,
            'label': dict(Notification.Category.choices)[category],
            'field': field,
            'icon': CATEGORY_ICONS.get(category, 'bell'),
            'checked': bool(getattr(prefs, field)),
        }
        for category, field in CATEGORY_FIELD.items()
    ]
    return render(request, 'notifications/settings.html', {
        'prefs': prefs,
        'fields': fields,
        'role': get_user_role(request.user),
    })


@require_POST
@login_required
def mark_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return JsonResponse({'ok': True, 'unread': unread_count(request.user)})


@require_POST
@login_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'ok': True, 'unread': 0})


@require_POST
@login_required
def delete_notification(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notif.delete()
    return JsonResponse({'ok': True, 'unread': unread_count(request.user)})


@require_POST
@login_required
def clear_notifications(request):
    Notification.objects.filter(recipient=request.user, is_read=True).delete()
    return JsonResponse({'ok': True, 'unread': unread_count(request.user)})
