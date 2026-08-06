"""Tests for the shipping decision engine."""

from decimal import Decimal

from logistics.models import CourierRule
from logistics.services.shipping_engine import (
    ShippingContext,
    ShippingEngine,
    NoEligibleCourier,
)
from logistics.constants import PaymentMode

from .base import LogisticsTestCase


class EligibleCouriersTests(LogisticsTestCase):

    def test_served_pincode_returns_both_couriers(self):
        ctx = ShippingContext(destination_pincode=self.PINCODE, weight_g=Decimal('500'))
        candidates = ShippingEngine.eligible_couriers(ctx)
        codes = {c.courier.code for c, _svc in candidates}
        self.assertEqual(codes, {'mock', 'mockexpress'})

    def test_unserved_pincode_returns_nothing(self):
        ctx = ShippingContext(destination_pincode='999999', weight_g=Decimal('500'))
        self.assertEqual(ShippingEngine.eligible_couriers(ctx), [])

    def test_weight_over_max_keeps_courier_out(self):
        self.mock.max_weight_g = 1000
        self.mock.save()
        ctx = ShippingContext(destination_pincode=self.PINCODE, weight_g=Decimal('5000'))
        codes = {c.courier.code for c, _svc in ShippingEngine.eligible_couriers(ctx)}
        self.assertNotIn('mock', codes)
        self.assertIn('mockexpress', codes)

    def test_cod_requires_support(self):
        self.mex.supports_cod = False
        self.mex.save()
        ctx = ShippingContext(
            destination_pincode=self.PINCODE,
            weight_g=Decimal('500'),
            payment_mode=PaymentMode.COD,
            cod_amount=Decimal('3000'),
        )
        codes = {c.courier.code for c, _svc in ShippingEngine.eligible_couriers(ctx)}
        self.assertNotIn('mockexpress', codes)
        self.assertIn('mock', codes)

    def test_cod_amount_cap(self):
        svc = self.mock.serviceability.get()
        svc.max_cod_amount = Decimal('1000')
        svc.save()
        ctx = ShippingContext(
            destination_pincode=self.PINCODE,
            weight_g=Decimal('500'),
            payment_mode=PaymentMode.COD,
            cod_amount=Decimal('3000'),
        )
        codes = {c.courier.code for c, _svc in ShippingEngine.eligible_couriers(ctx)}
        self.assertNotIn('mock', codes)


class SelectionTests(LogisticsTestCase):

    def test_select_courier_returns_a_serving_courier(self):
        ctx = ShippingContext(destination_pincode=self.PINCODE, weight_g=Decimal('500'))
        best, decision = ShippingEngine.select_courier(ctx)
        self.assertIn(best.courier.code, {'mock', 'mockexpress'})
        self.assertIn('ranking', decision)

    def test_no_eligible_raises(self):
        ctx = ShippingContext(destination_pincode='999999', weight_g=Decimal('500'))
        with self.assertRaises(NoEligibleCourier):
            ShippingEngine.select_courier(ctx)

    def test_force_courier_honoured(self):
        ctx = ShippingContext(
            destination_pincode=self.PINCODE,
            weight_g=Decimal('500'),
            force_courier_id=self.mex.pk,
        )
        best, _decision = ShippingEngine.select_courier(ctx)
        self.assertEqual(best.courier.pk, self.mex.pk)

    def test_rule_override_forces_courier(self):
        CourierRule.objects.create(
            name='All COD to mock',
            priority=1,
            payment_mode=PaymentMode.COD,
            courier=self.mock,
            is_active=True,
        )
        ctx = ShippingContext(
            destination_pincode=self.PINCODE,
            weight_g=Decimal('500'),
            payment_mode=PaymentMode.COD,
            cod_amount=Decimal('3000'),
        )
        best, _decision = ShippingEngine.select_courier(ctx)
        self.assertEqual(best.courier.pk, self.mock.pk)

    def test_cost_estimation_math(self):
        ctx = ShippingContext(destination_pincode=self.PINCODE, weight_g=Decimal('1000'))
        cost = ShippingEngine.estimate_cost(self.mock, ctx)
        # 40 + 15 * 1.0 kg = 55.00
        self.assertEqual(cost, Decimal('55.00'))
