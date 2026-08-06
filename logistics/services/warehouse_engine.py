"""Warehouse selection engine.

Chooses the best fulfilment warehouse for an order (or order line) using a
weighted scoring model:

- Inventory availability (required — a warehouse that cannot fulfil a line is
  removed from the candidate set)
- Distance to the customer (from pincode)
- Current processing load (open shipments)
- Warehouse performance score (on-time %, stored in extra_config by the
  scoring job)
- Estimated SLA / shipping cost

The engine is deliberately simple and data-driven: the same scoring weights
drive every decision, and admins can add more warehouses without any code
change. Extend ``WarehouseContext`` with new inputs and add the matching
weight in ``DEFAULT_WEIGHTS`` to grow the model.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from logistics.models import Warehouse


# Indian pincode → rough lat/lon grid used to estimate distance when the
# warehouse has no explicit coordinates. Values are in a lightweight
# "pincode space" (first two digits) so distances are only *relative*.
_PINCODE_GRID = {
    '11': (28.6, 77.2), '12': (28.9, 76.6), '13': (29.4, 76.9),
    '14': (30.7, 76.8), '15': (30.9, 75.8), '16': (30.3, 76.4),
    '17': (31.0, 77.1), '18': (31.1, 75.3), '19': (33.9, 74.3),
    '20': (27.2, 78.0), '22': (25.4, 81.8), '24': (28.6, 77.8),
    '25': (29.4, 77.7), '26': (29.2, 79.5), '27': (26.8, 83.4),
    '28': (27.1, 77.7), '30': (26.9, 75.8), '31': (24.6, 73.7),
    '32': (27.0, 75.2), '34': (26.3, 73.0), '36': (22.3, 70.8),
    '38': (23.0, 72.6), '39': (21.2, 72.8), '40': (19.1, 72.9),
    '41': (18.5, 73.8), '42': (19.1, 73.0), '44': (21.1, 79.1),
    '45': (22.7, 75.8), '46': (23.1, 76.0), '47': (23.2, 77.4),
    '48': (22.6, 77.0), '49': (22.7, 81.1), '50': (17.4, 78.5),
    '52': (16.5, 80.6), '53': (17.7, 83.3), '56': (12.9, 77.6),
    '57': (13.1, 74.7), '58': (15.3, 74.9), '59': (12.3, 75.4),
    '60': (13.0, 80.2), '62': (10.8, 78.7), '63': (11.0, 77.3),
    '64': (11.0, 77.0), '67': (10.5, 76.2), '68': (9.9, 76.3),
    '70': (22.5, 88.4), '71': (22.5, 88.4), '72': (23.0, 87.3),
    '73': (23.0, 88.5), '74': (22.6, 88.4), '75': (20.3, 85.8),
    '76': (19.2, 84.8), '77': (21.2, 81.6), '78': (26.1, 91.7),
    '79': (27.5, 94.7), '80': (25.6, 85.1), '82': (23.3, 85.3),
    '83': (23.3, 85.3), '84': (25.8, 85.5), '85': (26.5, 85.0),
    '86': (20.4, 85.8), '90': (12.9, 77.6), '93': (27.2, 73.5),
}

_DEFAULT_COORDS = (23.0, 79.0)


def _coords_for(pincode):
    p = ''.join(ch for ch in str(pincode or '') if ch.isdigit())
    if p and p[:2] in _PINCODE_GRID:
        return _PINCODE_GRID[p[:2]]
    return _DEFAULT_COORDS


def _distance_km(a_pincode, warehouse):
    if warehouse.latitude and warehouse.longitude:
        a = _coords_for(a_pincode)
        b = (float(warehouse.latitude), float(warehouse.longitude))
    else:
        a = _coords_for(a_pincode)
        b = _coords_for(warehouse.pincode)
    # Rough haversine over the grid (units are degrees; ×111 for km).
    lat1, lon1 = a
    lat2, lon2 = b
    return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5 * 111


@dataclass
class WarehouseContext:
    """Inputs for a warehouse selection decision.

    ``inventory_fn`` is a callable(warehouse) -> bool that tells whether the
    warehouse can fulfil the current order line(s). It is injected so the
    engine stays free of any inventory implementation detail.
    """
    destination_pincode: str
    inventory_fn: callable = lambda warehouse: True
    weight_g: Decimal = Decimal('0')
    declared_value: Decimal = Decimal('0')
    force_warehouse_id: Optional[int] = None

    # Scoring weights — higher = more important.
    DEFAULT_WEIGHTS = {
        'distance': 1.0,
        'load': 0.6,
        'performance': 0.5,
        'cost': 0.4,
    }


@dataclass
class WarehouseCandidate:
    warehouse: Warehouse
    distance_km: float
    open_shipments: int
    performance: float
    score: float = 0.0
    reasons: list = None

    def __post_init__(self):
        self.reasons = self.reasons or []


def performance_of(warehouse):
    """0-100 warehouse performance derived from its config (kept simple)."""
    cfg = warehouse.extra_config if hasattr(warehouse, 'extra_config') else None
    try:
        return float((warehouse.extra_config or {}).get('performance_score', 90.0))
    except (AttributeError, TypeError, ValueError):
        return 90.0


def open_shipment_count(warehouse):
    from logistics.constants import ShipmentStatus
    return warehouse.shipments.filter(
        status__in=ShipmentStatus.TIMELINE,
    ).count()


class WarehouseEngine:
    @classmethod
    def select_warehouse(cls, context):
        """Return a WarehouseCandidate with the best warehouse, or None when no
        warehouse can fulfil the order."""
        if context.force_warehouse_id:
            wh = Warehouse.objects.filter(pk=context.force_warehouse_id, is_active=True).first()
            if wh is None:
                raise WarehouseSelectionError(f'Warehouse #{context.force_warehouse_id} is not active.')
            if not context.inventory_fn(wh):
                raise WarehouseSelectionError(f'Warehouse "{wh.name}" has no stock for this order.')
            candidate = WarehouseCandidate(
                warehouse=wh,
                distance_km=_distance_km(context.destination_pincode, wh),
                open_shipments=open_shipment_count(wh),
                performance=performance_of(wh),
            )
            candidate.reasons.append('Warehouse manually overridden.')
            return candidate

        weights = WarehouseContext.DEFAULT_WEIGHTS
        best = None
        for warehouse in Warehouse.objects.filter(is_active=True):
            if not context.inventory_fn(warehouse):
                continue

            distance = _distance_km(context.destination_pincode, warehouse)
            load = open_shipment_count(warehouse)
            perf = performance_of(warehouse)

            # Distance — closer is better.
            score = 0.0
            reasons = []

            d_score = max(0.0, 1.0 - distance / 2000.0)
            score += weights['distance'] * d_score

            l_score = max(0.0, 1.0 - load / 500.0)
            score += weights['load'] * l_score

            p_score = min(perf / 100.0, 1.0)
            score += weights['performance'] * p_score

            candidate = WarehouseCandidate(
                warehouse=warehouse,
                distance_km=round(distance, 1),
                open_shipments=load,
                performance=perf,
                score=round(score, 3),
            )
            candidate.reasons = [
                f'Distance ~{distance:.0f} km (score {d_score:.2f})',
                f'Load {load} open shipments (score {l_score:.2f})',
                f'Performance {perf:.0f}/100 (score {p_score:.2f})',
            ]
            if best is None or candidate.score > best.score:
                best = candidate

        if best is None:
            raise WarehouseSelectionError(
                f'No warehouse can fulfil delivery to pincode {context.destination_pincode}.'
            )
        best.reasons.append('Selected by weighted warehouse engine.')
        return best


class WarehouseSelectionError(Exception):
    pass
