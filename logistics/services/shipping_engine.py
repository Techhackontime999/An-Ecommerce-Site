"""The shipping decision engine.

Responsibilities:
1. Compute the set of eligible couriers for a shipment context (serviceability,
   weight, COD, hazardous, capacity).
2. Score each candidate from configurable weighted factors.
3. Apply CourierRule overrides (ops-mandated decisions) in priority order.
4. Return the best courier, or honour an explicit manual override.

Adding a new decision input means adding a field to ShippingContext and a
corresponding weight in ShippingEngineConfig.score_weights — no core logic
changes.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from logistics.models import (
    CourierCompany,
    CourierService,
    CourierRule,
    ShippingEngineConfig,
    CourierPerformanceScore,
    PincodeServiceability,
)
from logistics.constants import DeliverySpeed

from . import round_money


@dataclass
class ShippingContext:
    destination_pincode: str
    weight_g: Decimal = Decimal('0')
    payment_mode: str = 'prepaid'
    cod_amount: Decimal = Decimal('0')
    declared_value: Decimal = Decimal('0')
    is_hazardous: bool = False
    delivery_speed: str = DeliverySpeed.STANDARD
    category_id: Optional[int] = None
    source_pincode: str = ''
    force_courier_id: Optional[int] = None

    @property
    def zone(self):
        return 'urban'


@dataclass
class Candidate:
    courier: CourierCompany
    service: Optional[CourierService]
    eta_days: int
    estimated_cost: Decimal
    score: float = 0.0
    breakdown: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)


class ShippingEngine:
    @staticmethod
    def estimate_cost(courier, context, service=None):
        """Estimate the courier charge from CourierCompany pricing config.
        Mirrors BaseCourierAdapter.rate() so admin-visible quotes match."""
        weight_kg = max(float(context.weight_g) / 1000.0, 0.001)
        base = Decimal(str(courier.base_charge))
        per_kg = Decimal(str(courier.per_kg_charge))
        total = base + per_kg * Decimal(str(weight_kg))
        if context.payment_mode == 'cod' and courier.supports_cod:
            total += Decimal(str(courier.cod_charge_percent)) / Decimal(100) * context.cod_amount
        if service and service.price_premium_percent:
            total += total * (Decimal(str(service.price_premium_percent)) / Decimal(100))
        return round_money(total)

    # ------------------------------------------------------------------ 1
    @classmethod
    def eligible_couriers(cls, context):
        """Return (Candidate, PincodeServiceability) tuples for every courier
        able to fulfil this context."""
        from logistics.couriers.registry import get_adapter

        pincode = context.destination_pincode
        eligible = []

        couriers = CourierCompany.objects.filter(is_active=True)
        for courier in couriers:
            adapter_cls = get_adapter(courier.code)
            if adapter_cls is None and not courier.adapter_path:
                continue
            if courier.max_weight_g and context.weight_g > courier.max_weight_g:
                continue
            if courier.min_weight_g and context.weight_g < courier.min_weight_g:
                continue
            if context.payment_mode == 'cod' and not courier.supports_cod:
                continue
            if context.is_hazardous and not courier.extra_config.get('accepts_hazardous', True):
                continue

            svc = PincodeServiceability.objects.filter(
                courier=courier, pincode=pincode, is_active=True,
            ).first()
            if svc is None:
                continue
            if context.payment_mode == 'cod' and not svc.is_cod_available:
                continue
            if context.payment_mode == 'cod' and svc.max_cod_amount and context.cod_amount > svc.max_cod_amount:
                continue

            service = cls._pick_service(courier, context.delivery_speed)
            eta = svc.estimated_delivery_days or (service.delivery_sla_days if service else 5)
            candidate = Candidate(
                courier=courier,
                service=service,
                eta_days=eta,
                estimated_cost=cls.estimate_cost(courier, context, service),
            )
            eligible.append((candidate, svc))

        return eligible

    @staticmethod
    def _pick_service(courier, delivery_speed):
        services = list(courier.services.filter(is_active=True))
        if not services:
            return None
        for service in services:
            if service.delivery_speed == delivery_speed:
                return service
        for service in services:
            if service.is_default:
                return service
        return services[0]

    # ------------------------------------------------------------------ 2
    @classmethod
    def score(cls, candidate, context, config=None, peer_candidates=None):
        """Score one candidate relative to its peers; higher is better."""
        config = config or ShippingEngineConfig.get()
        weights = dict(config.score_weights) or dict(ShippingEngineConfig.DEFAULT_WEIGHTS)
        peers = peer_candidates or [candidate]

        perf = CourierPerformanceScore.objects.filter(
            courier=candidate.courier,
        ).order_by('-period').first()

        breakdown = {}

        def _add(key, raw, good):
            weight = float(weights.get(key, 0.0))
            breakdown[key] = {'raw': raw, 'goodness': round(good, 4), 'weight': weight}
            return weight * good

        total = 0.0

        # Cost — cheaper is better, normalised across peers.
        min_cost = min((c.estimated_cost for c in peers), default=candidate.estimated_cost)
        max_cost = max((c.estimated_cost for c in peers), default=candidate.estimated_cost)
        cost_good = 1.0
        if max_cost > min_cost:
            cost_good = 1.0 - (float(candidate.estimated_cost) - float(min_cost)) / (float(max_cost) - float(min_cost))
        total += _add('cost', candidate.estimated_cost, cost_good)

        # SLA — lower eta is better.
        min_eta = min((c.eta_days for c in peers), default=candidate.eta_days)
        max_eta = max((c.eta_days for c in peers), default=candidate.eta_days)
        sla_good = 1.0
        if max_eta > min_eta:
            sla_good = 1.0 - (candidate.eta_days - min_eta) / (max_eta - min_eta)
        total += _add('sla', candidate.eta_days, sla_good)

        if perf:
            total += _add('performance', perf.composite_score, min(float(perf.composite_score) / 100.0, 1.0))
            total += _add('success_rate', perf.success_rate, min(float(perf.success_rate) / 100.0, 1.0))
            total += _add('return_rate', perf.return_rate, max(1.0 - float(perf.return_rate) / 100.0, 0.0))
            total += _add('capacity', perf.capacity_score, min(float(perf.capacity_score) / 100.0, 1.0))
        else:
            total += _add('performance', None, 0.5)
            total += _add('success_rate', None, 0.5)
            total += _add('return_rate', None, 0.5)
            total += _add('capacity', None, 1.0 if candidate.courier.has_capacity else 0.0)

        candidate.score = round(total, 4)
        candidate.breakdown = breakdown
        return candidate.score, breakdown

    # ------------------------------------------------------------------ 3
    @staticmethod
    def apply_rules(context, candidates, config):
        """Force a courier when a rule matches. Returns (forced_candidate, rule)
        or (None, None)."""
        rules = CourierRule.objects.filter(is_active=True).select_related('courier', 'service')
        for rule in rules:
            if rule.matches({
                'zone': context.zone,
                'delivery_speed': context.delivery_speed,
                'payment_mode': context.payment_mode,
                'category_id': context.category_id,
                'is_hazardous': context.is_hazardous,
                'weight_g': float(context.weight_g),
                'cod_amount': float(context.cod_amount),
            }):
                for candidate, svc in candidates:
                    if candidate.courier.pk == rule.courier_id:
                        if rule.service_id and (candidate.service is None or candidate.service.pk != rule.service_id):
                            service = CourierService.objects.filter(pk=rule.service_id).first()
                            if service:
                                candidate.service = service
                        return candidate, rule
        return None, None

    # ------------------------------------------------------------------ 4
    @classmethod
    def select_courier(cls, context):
        """Main entry point. Returns (candidate, decision_details)."""
        config = ShippingEngineConfig.get()

        if context.force_courier_id:
            courier = CourierCompany.objects.filter(pk=context.force_courier_id, is_active=True).first()
            if courier is None:
                raise ShippingEngineError(f'Courier #{context.force_courier_id} is not active.')
            svc = PincodeServiceability.objects.filter(
                courier=courier, pincode=context.destination_pincode, is_active=True,
            ).first()
            if svc is None:
                raise NoEligibleCourier(
                    f'Courier "{courier.name}" does not serve pincode {context.destination_pincode}.'
                )
            service = cls._pick_service(courier, context.delivery_speed)
            eta = svc.estimated_delivery_days or (service.delivery_sla_days if service else 5)
            candidate = Candidate(
                courier=courier, service=service, eta_days=eta,
                estimated_cost=cls.estimate_cost(courier, context, service),
            )
            return candidate, {
                'method': 'manual', 'force_courier_id': context.force_courier_id,
                'reasons': ['Courier manually overridden by operator.'],
            }

        candidates = cls.eligible_couriers(context)
        if not candidates:
            raise NoEligibleCourier(
                f'No courier can serve pincode {context.destination_pincode} for the given shipment.',
            )

        peers = [c for c, _ in candidates]

        if config.enable_rule_overrides:
            forced, rule = cls.apply_rules(context, candidates, config)
            if forced:
                cls.score(forced, context, config, peers)
                return forced, {
                    'method': 'rule',
                    'rule_id': rule.pk,
                    'rule_name': rule.name,
                    'reasons': [f'Matched rule "{rule.name}" (priority {rule.priority}).'],
                }

        scored = []
        for candidate, svc in candidates:
            score, breakdown = cls.score(candidate, context, config, peers)
            scored.append((candidate, score, breakdown))
        scored.sort(key=lambda row: (row[1], row[0].estimated_cost), reverse=True)

        best, score, breakdown = scored[0]
        best.score = score
        best.breakdown = breakdown
        reasons = [
            f'Best weighted score {score:.2f} across cost, SLA and courier performance.',
            f'Estimated cost {best.estimated_cost} via {best.courier.name}, ETA {best.eta_days} days.',
        ]
        return best, {
            'method': 'engine',
            'total_candidates': len(scored),
            'reasons': reasons,
            'ranking': [
                {'courier': c.courier.code, 'score': s, 'cost': float(c.estimated_cost), 'eta': c.eta_days}
                for c, s, _ in scored
            ],
        }

    @classmethod
    def quote_couriers(cls, context):
        """Return every eligible courier with rates, ETA and score (seller UI)."""
        rows = []
        for candidate, svc in cls.eligible_couriers(context):
            cls.score(candidate, context)
            rows.append({
                'courier': candidate.courier,
                'service': candidate.service,
                'estimated_cost': candidate.estimated_cost,
                'eta_days': candidate.eta_days,
                'score': candidate.score,
                'zone': svc.zone,
                'is_cod_available': svc.is_cod_available,
            })
        rows.sort(key=lambda r: r['estimated_cost'])
        return rows


class ShippingEngineError(Exception):
    pass


class NoEligibleCourier(ShippingEngineError):
    pass
