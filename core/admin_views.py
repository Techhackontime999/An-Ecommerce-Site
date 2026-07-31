from io import StringIO

from django.contrib import admin
from django.core.management import call_command
from django.shortcuts import redirect
from django.contrib import messages


ADMIN_MODELS_CLEAR_ORDER = [
    'seller.SellerProduct', 'documentation.DocumentationSection',
    'contact.ContactMessage', 'about.TeamMember', 'about.AboutSection',
    'faq.Story', 'faq.FAQ', 'services.Service',
    'payments.Payment', 'order.OrderItem', 'order.Order',
    'reviews.SellerReview', 'reviews.Review', 'deals.Deal',
    'coupons.Coupon', 'shop.Product', 'accounts.SellerProfile',
    'accounts.CustomerProfile', 'shop.Category',
]


def seed_data_view(request):
    buf = StringIO()
    try:
        call_command('seed_all', stdout=buf)
        output = buf.getvalue()
        messages.success(request, f'Database seeded!\n{output}')
    except Exception as e:
        messages.error(request, f'Seeding failed: {e}')
    return redirect('admin:index')


def clear_data_view(request):
    from django.apps import apps
    cleared = []
    for model_label in ADMIN_MODELS_CLEAR_ORDER:
        try:
            model = apps.get_model(model_label)
            count = model.objects.count()
            model.objects.all().delete()
            if count:
                cleared.append(f'{model.__name__} ({count})')
        except LookupError:
            pass
    if cleared:
        messages.success(request, f'Cleared: {", ".join(cleared)}')
    else:
        messages.warning(request, 'No data to clear.')
    return redirect('admin:index')
