"""Public + staff-facing views for the LMS.

- ``tracking_lookup`` / ``tracking_detail``: public order tracking by AWB or
  shipment number.
- ``webhook``: courier push endpoint (HMAC verified, logged, applied).
- ``dashboard`` / ``shipments`` / ``ndr_queue`` / ``returns_queue``: staff
  operational views (tabs over the live data).

Webhook URLs are intentionally *not* under the admin; couriers should not have
to authenticate to the admin site.
"""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

from logistics.models import (
    CourierCompany,
    NDRRecord,
    ReturnShipment,
    Shipment,
    TrackingEvent,
    WebhookEvent,
)
from logistics.services.fulfillment import FulfillmentService

# ------------------------------------------------------------------ tracking


def tracking_lookup(request):
    """Landing page with a tracking lookup form (GET ?q=AWB|shipment number)."""
    query = (request.GET.get('q') or '').strip()
    shipment = None
    error = ''
    if query:
        shipment = (
            Shipment.objects.filter(
                Q(tracking_number__iexact=query) | Q(shipment_number__iexact=query)
            )
            .select_related('order', 'courier', 'warehouse')
            .first()
        )
        if shipment is None:
            error = f'No shipment found for "{query}". Please double-check the tracking number.'
    return render(request, 'logistics/tracking.html', {
        'query': query,
        'shipment': shipment,
        'error': error,
        'show_lookup': True,
    })


def tracking_detail(request, tracking_number):
    shipment = get_object_or_404(
        Shipment.objects.select_related('order', 'courier', 'warehouse', 'service'),
        Q(tracking_number__iexact=tracking_number) | Q(shipment_number__iexact=tracking_number),
    )
    events = list(shipment.tracking_events.order_by('timestamp', 'id'))
    deduped = []
    for ev in events:
        if deduped and deduped[-1].status == ev.status:
            continue
        deduped.append(ev)
    return render(request, 'logistics/tracking.html', {
        'query': shipment.shipment_number,
        'shipment': shipment,
        'events': deduped,
        'show_lookup': False,
    })


# -------------------------------------------------------------------- webhook

def _verify_signature(courier_code, raw_body, header_signature):
    """Verify an HMAC-SHA256 signature over the raw request body.

    Secret is looked up in ``LOGISTICS_WEBHOOK_SECRETS``. Fail-closed: if no
    secret is configured for the courier, or no signature is supplied, the
    webhook is rejected so unauthenticated pushes can never mutate state.
    """
    secret = (settings.LOGISTICS_WEBHOOK_SECRETS or {}).get(courier_code, '')
    if not secret:
        logger.error('Courier webhook "%s" received but no webhook secret is configured — rejecting.', courier_code)
        return False
    if not header_signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = header_signature.split('=', 1)[-1] if '=' in header_signature else header_signature
    return hmac.compare_digest(expected, provided)


def _resolve_shipment(payload):
    """Find the shipment referenced by a courier payload."""
    lookup = None
    for key in ('tracking_number', 'shipment_number', 'external_shipment_id', 'awb'):
        value = payload.get(key)
        if value:
            lookup = (key, str(value))
            break
    if lookup is None:
        return None
    key, value = lookup
    kwargs = {f'{key}__iexact': value}
    return Shipment.objects.filter(**kwargs).select_related('courier').first()


@csrf_exempt
@require_http_methods(['POST'])
def webhook(request, courier_code):
    """Receive a courier webhook, verify it, log it and apply it."""
    raw_body = request.body
    signature = request.META.get('HTTP_X_LMS_SIGNATURE', '')
    if not _verify_signature(courier_code, raw_body, signature):
        return JsonResponse({'status': 'error', 'detail': 'invalid signature'}, status=401)

    try:
        payload = json.loads(raw_body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'detail': 'invalid JSON'}, status=400)

    courier = CourierCompany.objects.filter(code__iexact=courier_code).first()
    dedupe_key = hashlib.sha256(raw_body).hexdigest()
    if courier is not None:
        event, created = WebhookEvent.objects.get_or_create(
            courier=courier,
            dedupe_key=dedupe_key,
            defaults={
                'event_type': payload.get('event_type') or payload.get('event') or '',
                'payload': payload,
                'signature': signature or '',
            },
        )
        if not created:
            # Replay of an already-received raw body — idempotent success.
            return JsonResponse({'status': 'ok', 'detail': 'duplicate'})
    else:
        event = WebhookEvent.objects.create(
            courier=None,
            event_type=payload.get('event_type') or payload.get('event') or '',
            payload=payload,
            signature=signature or '',
        )

    shipment = _resolve_shipment(payload)
    if shipment is None or shipment.courier is None:
        event.error = 'unknown shipment reference'
        event.save(update_fields=['error'])
        return JsonResponse({'status': 'error', 'detail': 'unknown shipment'}, status=404)

    try:
        events = shipment.courier.adapter.handle_webhook(payload)
    except Exception as exc:
        event.error = str(exc)
        event.save(update_fields=['error'])
        return JsonResponse({'status': 'error', 'detail': str(exc)}, status=500)

    if not events:
        event.error = 'unhandled event type'
        event.save(update_fields=['error'])
        return JsonResponse({'status': 'ok', 'detail': 'unhandled'})

    added = FulfillmentService.apply_events(shipment, events, source='webhook')
    event.processed = True
    event.processed_at = timezone.now()
    event.save(update_fields=['processed', 'processed_at'])

    return JsonResponse({
        'status': 'ok',
        'shipment': shipment.shipment_number,
        'tracking_number': shipment.tracking_number,
        'added': added,
        'current_status': shipment.status,
    })


# ---------------------------------------------------------------- dashboards


@staff_member_required
def dashboard(request):
    today = timezone.localdate()
    shipments = Shipment.objects.all()
    today_qs = shipments.filter(created_at__date=today)

    context = {
        'page': 'dashboard',
        'kpi': {
            'total_shipments': shipments.count(),
            'today_shipments': today_qs.count(),
            'in_transit': shipments.filter(status__in=(
                'picked_up', 'at_origin_hub', 'in_transit', 'at_destination_hub',
            )).count(),
            'out_for_delivery': shipments.filter(status='out_for_delivery').count(),
            'delivered': shipments.filter(status='delivered').count(),
            'pending_pickup': shipments.filter(status__in=('order_confirmed', 'packed', 'ready_for_pickup')).count(),
            'ndr_open': NDRRecord.objects.filter(status='open').count(),
            'returns_requested': ReturnShipment.objects.filter(status__in=(
                'requested', 'approved', 'pickup_scheduled', 'picked_up',
            )).count(),
        },
        'by_courier': CourierCompany.objects.annotate(
            shipment_count=Count('shipments'),
        ).order_by('-shipment_count')[:8],
        'recent_events': TrackingEvent.objects.select_related('shipment').order_by('-timestamp', '-id')[:15],
        'recent_shipments': shipments.select_related('order', 'courier', 'warehouse')[:12],
        'open_ndrs': NDRRecord.objects.select_related('shipment').filter(status='open')[:8],
    }
    return render(request, 'logistics/dashboard.html', context)


@staff_member_required
def shipments_list(request):
    qs = Shipment.objects.select_related('order', 'courier', 'warehouse').all()
    status = request.GET.get('status', '')
    courier_id = request.GET.get('courier', '')
    search = (request.GET.get('q') or '').strip()
    if status:
        qs = qs.filter(status=status)
    if courier_id:
        qs = qs.filter(courier_id=courier_id)
    if search:
        qs = qs.filter(
            Q(shipment_number__icontains=search)
            | Q(tracking_number__icontains=search)
            | Q(order__id__icontains=search)
        )
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'logistics/shipments.html', {
        'page': 'shipments',
        'page_obj': page,
        'status': status,
        'courier': courier_id,
        'search': search,
        'couriers': CourierCompany.objects.filter(is_active=True),
        'status_choices': Shipment._meta.get_field('status').choices,
    })


@staff_member_required
def ndr_queue(request):
    qs = NDRRecord.objects.select_related('shipment', 'shipment__order').all()
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs.order_by('status', '-created_at'), 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'logistics/ndr_queue.html', {
        'page': 'ndr',
        'page_obj': page,
        'status': status,
        'status_choices': NDRRecord._meta.get_field('status').choices,
    })


@staff_member_required
def returns_queue(request):
    qs = ReturnShipment.objects.select_related('order', 'original_shipment', 'restock_warehouse').all()
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs.order_by('status', '-created_at'), 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'logistics/returns_queue.html', {
        'page': 'returns',
        'page_obj': page,
        'status': status,
        'status_choices': ReturnShipment._meta.get_field('status').choices,
    })
