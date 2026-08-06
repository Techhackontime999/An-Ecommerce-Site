"""Seed the Logistics Management System with realistic demo data.

Creates courier companies (mock, mock express, delhivery), courier services,
PIN-code serviceability, warehouses (platform + seller), performance scores,
holidays and the shipping engine config. With ``--with-demo-shipments`` it
also builds shipments for the most recent unpaid/new orders so the whole
pipeline can be exercised end to end.

Usage::

    python manage.py seed_logistics
    python manage.py seed_logistics --with-demo-shipments --orders 20
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from logistics.constants import (
    DeliverySpeed,
    OwnerType,
    PaymentMode,
    ShipmentStatus,
    Zone,
)
from logistics.models import (
    CourierCompany,
    CourierPerformanceScore,
    CourierService,
    Holiday,
    PincodeServiceability,
    ShippingEngineConfig,
    Warehouse,
)
from logistics.services.fulfillment import FulfillmentService


# (pincode, city, state, zone, cod available, est days)
PINCODES = [
    ('110001', 'New Delhi', 'Delhi', 'metro', True, 2),
    ('110025', 'New Delhi', 'Delhi', 'metro', True, 2),
    ('201301', 'Noida', 'Uttar Pradesh', 'urban', True, 2),
    ('122001', 'Gurugram', 'Haryana', 'urban', True, 2),
    ('121001', 'Faridabad', 'Haryana', 'urban', True, 3),
    ('400001', 'Mumbai', 'Maharashtra', 'metro', True, 2),
    ('400064', 'Mumbai', 'Maharashtra', 'metro', True, 2),
    ('411001', 'Pune', 'Maharashtra', 'metro', True, 3),
    ('440001', 'Nagpur', 'Maharashtra', 'urban', True, 3),
    ('560001', 'Bengaluru', 'Karnataka', 'metro', True, 2),
    ('560034', 'Bengaluru', 'Karnataka', 'metro', True, 2),
    ('600001', 'Chennai', 'Tamil Nadu', 'metro', True, 2),
    ('500001', 'Hyderabad', 'Telangana', 'metro', True, 2),
    ('700001', 'Kolkata', 'West Bengal', 'metro', True, 2),
    ('302001', 'Jaipur', 'Rajasthan', 'urban', True, 3),
    ('452001', 'Indore', 'Madhya Pradesh', 'urban', True, 3),
    ('380001', 'Ahmedabad', 'Gujarat', 'urban', True, 3),
    ('751001', 'Bhubaneswar', 'Odisha', 'urban', True, 3),
    ('821101', 'Sasaram', 'Bihar', 'rural', True, 6),
    ('431001', 'Aurangabad', 'Maharashtra', 'urban', True, 4),
    ('141001', 'Ludhiana', 'Punjab', 'urban', True, 3),
    ('832401', 'Jamshedpur', 'Jharkhand', 'rural', False, 7),
    ('788001', 'Silchar', 'Assam', 'rural', False, 7),
]


def _courier(kind, **overrides):
    defaults = {
        'name': kind['name'],
        'code': kind['code'],
        'description': kind['description'],
        'supports_cod': kind.get('supports_cod', True),
        'supports_reverse_pickup': kind.get('supports_reverse_pickup', True),
        'base_charge': kind.get('base_charge', 40),
        'per_kg_charge': kind.get('per_kg_charge', 15),
        'cod_charge_percent': kind.get('cod_charge_percent', 2),
        'max_capacity_per_day': kind.get('max_capacity_per_day', 0),
        'max_weight_g': kind.get('max_weight_g', 30000),
        'sandbox_mode': True,
        'is_active': True,
    }
    defaults.update(overrides)
    courier, created = CourierCompany.objects.update_or_create(
        code=kind['code'],
        defaults=defaults,
    )
    return courier, created


def _upsert(model, defaults, unique, attempts=5):
    """get_or_create + apply defaults, with retries for SQLite lock contention
    (the local DB often lives on a WSL-mounted Windows drive where file locks
    are flaky). Never uses select_for_update like update_or_create does."""
    import time
    from django.db import OperationalError
    for attempt in range(attempts):
        try:
            obj, created = model.objects.get_or_create(**unique, defaults=defaults)
            if not created and defaults:
                changed = {
                    k: v for k, v in defaults.items()
                    if getattr(obj, k) != v
                }
                if changed:
                    model.objects.filter(pk=obj.pk).update(**changed)
            return obj, created
        except OperationalError:
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f'Could not seed {model.__name__} due to repeated lock errors.')


class Command(BaseCommand):
    help = 'Seed the LMS with couriers, warehouses, serviceability and demo shipments.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-demo-shipments', action='store_true',
            help='Also create shipments for recent orders through the fulfilment pipeline.',
        )
        parser.add_argument('--orders', type=int, default=20, help='Max demo orders to fulfil.')

    def handle(self, *args, **options):
        self.stdout.write('Seeding logistics...')

        couriers = [
            {
                'name': 'Mock Courier (Simulation)',
                'code': 'mock',
                'description': 'Simulated courier for development and demos.',
                'base_charge': 40,
                'per_kg_charge': 15,
                'cod_charge_percent': 2,
                'max_capacity_per_day': 0,
            },
            {
                'name': 'Mock Express (Simulation)',
                'code': 'mockexpress',
                'description': 'Fast simulated courier — pricier but quicker SLA.',
                'base_charge': 70,
                'per_kg_charge': 25,
                'cod_charge_percent': 3,
                'max_capacity_per_day': 0,
            },
            {
                'name': 'Delhivery',
                'code': 'delhivery',
                'description': 'Delhivery network courier (real API). Keep sandbox mode on until '
                               'api_base_url/api_key are set.',
                'base_charge': 55,
                'per_kg_charge': 20,
                'cod_charge_percent': 2,
                'max_capacity_per_day': 0,
            },
        ]
        for kind in couriers:
            courier, created = _courier(kind)
            self.stdout.write(f"  {'created' if created else 'updated'} courier {courier.code}")

            # Services
            services = {
                DeliverySpeed.STANDARD: (5, 0, True),
                DeliverySpeed.EXPRESS: (3, 10, False),
                DeliverySpeed.PRIORITY: (2, 25, False),
            }
            if not courier.services.exists():
                for speed, (sla, premium, is_default) in services.items():
                    CourierService.objects.create(
                        courier=courier,
                        name=speed.title(),
                        code=speed,
                        delivery_sla_days=sla,
                        delivery_speed=speed,
                        price_premium_percent=premium,
                        is_default=is_default,
                    )

            # Serviceability
            created_svc = 0
            for pincode, city, state, zone, cod, days in PINCODES:
                _, was_created = _upsert(
                    PincodeServiceability,
                    defaults={
                        'city': city, 'state': state, 'zone': zone,
                        'is_cod_available': cod, 'estimated_delivery_days': days,
                        'max_cod_amount': 20000 if cod else 0,
                    },
                    unique={'courier': courier, 'pincode': pincode},
                )
                created_svc += int(was_created)
            self.stdout.write(f'    {created_svc} serviceability rows for {courier.code}')

        # Warehouses
        warehouses = [
            {
                'name': 'Fulfilment Centre Delhi NCR',
                'code': 'DEL-01', 'city': 'New Delhi', 'state': 'Delhi', 'pincode': '110001',
                'owner_type': OwnerType.PLATFORM, 'latitude': '28.6139', 'longitude': '77.2090',
                'extra': {'performance_score': 94},
            },
            {
                'name': 'Fulfilment Centre Mumbai',
                'code': 'MUM-01', 'city': 'Mumbai', 'state': 'Maharashtra', 'pincode': '400001',
                'owner_type': OwnerType.PLATFORM, 'latitude': '19.0760', 'longitude': '72.8777',
                'extra': {'performance_score': 91},
            },
            {
                'name': 'Fulfilment Centre Bengaluru',
                'code': 'BLR-01', 'city': 'Bengaluru', 'state': 'Karnataka', 'pincode': '560001',
                'owner_type': OwnerType.PLATFORM, 'latitude': '12.9716', 'longitude': '77.5946',
                'extra': {'performance_score': 96},
            },
        ]
        for wh in warehouses:
            warehouse, created = _upsert(
                Warehouse,
                defaults={
                    'name': wh['name'],
                    'city': wh['city'], 'state': wh['state'], 'pincode': wh['pincode'],
                    'owner_type': wh['owner_type'],
                    'latitude': wh['latitude'], 'longitude': wh['longitude'],
                    'address_line1': f'{wh["city"]} Fulfilment Centre, Industrial Area',
                    'contact_name': 'Ops Team',
                    'contact_phone': '1800-419-7788',
                    'is_active': True,
                    'extra_config': wh['extra'],
                },
                unique={'code': wh['code']},
            )
            self.stdout.write(f"  {'created' if created else 'updated'} warehouse {warehouse.code}")

        # Attach warehouses to real sellers when available
        from accounts.models import SellerProfile
        sellers = list(SellerProfile.objects.all()[:3])
        for i, seller in enumerate(sellers):
            wh, _ = _upsert(
                Warehouse,
                defaults={
                    'name': f'{seller.shop_name} Warehouse',
                    'owner_type': OwnerType.SELLER,
                    'city': 'New Delhi', 'state': 'Delhi', 'pincode': '110025',
                    'address_line1': seller.address or 'Seller fulfilment centre',
                    'is_active': True,
                    'extra_config': {'performance_score': 88 + i},
                },
                unique={'seller': seller, 'code': f'{seller.shop_name[:8].upper()}-01'},
            )
            self.stdout.write(f'  attached warehouse {wh.code} to seller {seller.shop_name}')

        # Performance scores for the current month
        today = timezone.localdate()
        period = today.strftime('%Y-%m')
        base_scores = {
            'mock': {'total': 5000, 'delivered': 4820, 'success': 96.4, 'avg_days': 4.1, 'on_time': 94.0, 'capacity': 90.0, 'return': 3.5, 'composite': 87.0},
            'mockexpress': {'total': 3800, 'delivered': 3740, 'success': 98.4, 'avg_days': 2.2, 'on_time': 97.0, 'capacity': 80.0, 'return': 1.5, 'composite': 93.0},
            'delhivery': {'total': 12500, 'delivered': 11980, 'success': 95.8, 'avg_days': 3.4, 'on_time': 93.0, 'capacity': 95.0, 'return': 3.1, 'composite': 89.0},
        }
        for courier in CourierCompany.objects.all():
            data = base_scores.get(courier.code, base_scores['mock'])
            for zone in (Zone.METRO, Zone.URBAN, Zone.RURAL):
                _upsert(
                    CourierPerformanceScore,
                    defaults={
                        'total_shipments': data['total'], 'delivered': data['delivered'],
                        'success_rate': data['success'], 'avg_delivery_days': data['avg_days'],
                        'on_time_rate': data['on_time'], 'capacity_score': data['capacity'],
                        'return_rate': data['return'], 'composite_score': data['composite'],
                    },
                    unique={'courier': courier, 'period': period, 'zone': zone},
                )

        # Holidays for the coming quarter
        if not Holiday.objects.exists():
            for delta, name in ((7, 'State Holiday (demo)'), (30, 'Maintenance Window (demo)')):
                _upsert(
                    Holiday,
                    defaults={'name': name},
                    unique={'courier': None, 'date': today + timedelta(days=delta)},
                )

        # Make sure real orders are serviceable so --with-demo-shipments works.
        from order.models import Order
        order_pincodes = sorted({
            str(o.postal_code).strip() for o in Order.objects.exclude(postal_code='')
        })
        added = 0
        for pincode in order_pincodes:
            if len(pincode) != 6 or not pincode.isdigit():
                continue
            zone = 'metro' if pincode[:2] in ('11', '12', '20', '24', '40', '41', '56', '60', '70', '71', '72', '73', '74', '75') else 'urban'
            for courier in CourierCompany.objects.filter(is_active=True):
                _, was_created = _upsert(
                    PincodeServiceability,
                    defaults={
                        'zone': zone, 'is_cod_available': True,
                        'estimated_delivery_days': 3 if zone == 'metro' else 5,
                        'max_cod_amount': 20000,
                    },
                    unique={'courier': courier, 'pincode': pincode},
                )
                added += int(was_created)
        if added:
            self.stdout.write(f'  registered {added} serviceability row(s) for order pincodes.')

        ShippingEngineConfig.get()
        self.stdout.write(self.style.SUCCESS('Logistics seeded successfully.'))

        if options.get('with_demo_shipments'):
            self._seed_demo_shipments(options['orders'])

    def _seed_demo_shipments(self, limit):
        from order.models import Order
        from shop.models import Product

        orders = Order.objects.filter(status__in=(
            Order.Status.PENDING, Order.Status.PROCESSING,
        )).order_by('-created')[:limit]
        if not orders:
            self.stdout.write('No orders to fulfil.')
            return

        if not Product.objects.exists():
            self.stdout.write(self.style.WARNING('No products found — skipping demo shipments.'))
            return

        created = 0
        for order in orders:
            if not order.items.exists():
                continue
            try:
                shipments = FulfillmentService.create_shipments_for_order(order)
                created += len(shipments)
            except Exception as exc:
                self.stderr.write(f'  Failed for order #{order.pk}: {exc}')
        self.stdout.write(self.style.SUCCESS(f'Created {created} demo shipment(s).'))
