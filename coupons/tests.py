from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import SellerProfile
from cart.models import CartItem
from coupons.models import Coupon, CouponRedemption
from coupons.services import discount_for, validate_coupon
from shop.models import Category, Product
from order.models import Order


def make_coupon(code='TEST10', **overrides):
    defaults = {
        'code': code,
        'discount': 10,
        'valid_from': timezone.now() - timezone.timedelta(days=1),
        'valid_to': timezone.now() + timezone.timedelta(days=10),
        'active': True,
    }
    defaults.update(overrides)
    return Coupon.objects.create(**defaults)


class CouponValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='couponuser', password='pass1234')

    def test_expired_coupon_is_rejected(self):
        coupon = make_coupon(
            valid_from=timezone.now() - timezone.timedelta(days=10),
            valid_to=timezone.now() - timezone.timedelta(days=1),
        )
        ok, reason = validate_coupon(coupon, user=self.user, cart_total=Decimal('500'))
        self.assertFalse(ok)
        self.assertIn('expired', reason.lower())

    def test_inactive_coupon_is_rejected(self):
        coupon = make_coupon(active=False)
        ok, _ = validate_coupon(coupon, user=self.user, cart_total=Decimal('500'))
        self.assertFalse(ok)

    def test_global_usage_limit_enforced(self):
        coupon = make_coupon(max_uses=2)
        other = get_user_model().objects.create_user(username='other1', password='pass1234')
        CouponRedemption.objects.create(coupon=coupon, user=self.user)
        CouponRedemption.objects.create(coupon=coupon, user=other)
        ok, reason = validate_coupon(coupon, user=self.user, cart_total=Decimal('500'))
        self.assertFalse(ok)
        self.assertIn('usage limit', reason.lower())

    def test_global_usage_limit_counts_all_users(self):
        coupon = make_coupon(max_uses=1)
        self.assertTrue(validate_coupon(coupon, user=self.user, cart_total=Decimal('500'))[0])
        CouponRedemption.objects.create(coupon=coupon, user=self.user)
        self.assertFalse(validate_coupon(coupon, user=self.user, cart_total=Decimal('500'))[0])

    def test_per_user_limit_enforced(self):
        coupon = make_coupon(per_user_limit=1, max_uses=10)
        CouponRedemption.objects.create(coupon=coupon, user=self.user)
        ok, reason = validate_coupon(coupon, user=self.user, cart_total=Decimal('500'))
        self.assertFalse(ok)
        self.assertIn('already used', reason.lower())
        other = get_user_model().objects.create_user(username='other2', password='pass1234')
        self.assertTrue(validate_coupon(coupon, user=other, cart_total=Decimal('500'))[0])

    def test_minimum_cart_total_enforced(self):
        coupon = make_coupon(min_amount=Decimal('100.00'))
        ok, _ = validate_coupon(coupon, user=self.user, cart_total=Decimal('50'))
        self.assertFalse(ok)
        self.assertTrue(validate_coupon(coupon, user=self.user, cart_total=Decimal('150'))[0])

    def test_seller_scoping(self):
        seller_a = SellerProfile.objects.create(
            user=get_user_model().objects.create_user(username='seller_a', password='pass1234'),
            shop_name='Shop A', bank_account='1', account_holder_name='A',
            ifsc_code='HDFC0001234', phone='9999999999', address='x',
        )
        seller_b = SellerProfile.objects.create(
            user=get_user_model().objects.create_user(username='seller_b', password='pass1234'),
            shop_name='Shop B', bank_account='1', account_holder_name='B',
            ifsc_code='HDFC0001234', phone='9999999999', address='x',
        )
        coupon = make_coupon(seller=seller_a)
        ok, _ = validate_coupon(coupon, user=self.user, cart_total=Decimal('500'), seller_ids={seller_a.id})
        self.assertTrue(ok)
        ok, reason = validate_coupon(coupon, user=self.user, cart_total=Decimal('500'), seller_ids={seller_b.id})
        self.assertFalse(ok)
        self.assertIn('not valid for the items', reason.lower())

    def test_allowed_users_whitelist(self):
        coupon = make_coupon()
        coupon.allowed_users.add(self.user)
        ok, _ = validate_coupon(coupon, user=self.user, cart_total=Decimal('500'))
        self.assertTrue(ok)
        stranger = get_user_model().objects.create_user(username='stranger', password='pass1234')
        ok, reason = validate_coupon(coupon, user=stranger, cart_total=Decimal('500'))
        self.assertFalse(ok)
        self.assertIn('not available to you', reason.lower())

    def test_max_discount_cap(self):
        coupon = make_coupon(code='CAP50', discount=50, max_discount_amount=Decimal('100.00'))
        self.assertEqual(discount_for(coupon, Decimal('500')), Decimal('100.00'))
        self.assertEqual(discount_for(coupon, Decimal('100')), Decimal('50.00'))
        uncapped = make_coupon(code='UNCAPPED', discount=10)
        self.assertEqual(discount_for(uncapped, Decimal('500')), Decimal('50.00'))


class CouponCheckoutIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='couponbuyer', password='pass1234', email='buyer@example.com'
        )
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category, name='Earbuds', slug='earbuds',
            price=Decimal('100.00'), stock=10,
        )
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(self.user)

    def _seed_cart(self, quantity=2, coupon_id=None):
        CartItem.objects.create(
            user=self.user, product=self.product, key=str(self.product.id), quantity=quantity,
        )
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {
                'quantity': quantity, 'price': '100.00', 'variant_id': None,
            },
        }
        if coupon_id is not None:
            session['coupon_id'] = coupon_id
        session.save()

    def _order_post(self, token='coupon-token'):
        return self.client.post(reverse('order:order_create'), {
            'checkout_token': token,
            'first_name': 'Ada', 'last_name': 'Lovelace', 'email': 'ada@example.com',
            'address': '5 Way', 'postal_code': '560001', 'city': 'Bangalore',
            'phone': '9999999999', 'state': 'Karnataka', 'country': 'India',
        })

    def _apply(self, code):
        return self.client.post(reverse('coupons:apply'), {'code': code})

    def test_apply_view_sets_session_for_valid_coupon(self):
        coupon = make_coupon(code='VALID10')
        self._seed_cart()
        self._apply('valid10')
        self.assertEqual(self.client.session['coupon_id'], coupon.id)

    def test_apply_view_rejects_exhausted_coupon(self):
        coupon = make_coupon(code='USEDUP', max_uses=1)
        CouponRedemption.objects.create(coupon=coupon, user=self.user)
        self._seed_cart()
        self._apply('usedup')
        self.assertIsNone(self.client.session['coupon_id'])

    def test_apply_view_rejects_seller_coupon_not_in_cart(self):
        other = SellerProfile.objects.create(
            user=get_user_model().objects.create_user(username='other_seller', password='pass1234'),
            shop_name='Other', bank_account='1', account_holder_name='O',
            ifsc_code='HDFC0001234', phone='9999999999', address='x',
        )
        coupon = make_coupon(code='SHOPA', seller=other)
        self._seed_cart()
        self._apply('shop a'.replace(' ', ''))
        self.assertIsNone(self.client.session['coupon_id'])

    def test_order_create_records_redemption_once(self):
        coupon = make_coupon(code='ONCE', max_uses=2, per_user_limit=1)
        self._seed_cart(coupon_id=coupon.id)
        first = self._order_post()
        second = self._order_post()  # same token → idempotent, must not double-redeem
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(order.discount, Decimal('20.00'))
        self.assertEqual(CouponRedemption.objects.filter(coupon=coupon).count(), 1)
        self.assertEqual(CouponRedemption.objects.get(coupon=coupon).order, order)

    def test_exhausted_coupon_not_usable_at_checkout(self):
        coupon = make_coupon(code='EXHAUSTED', max_uses=1, per_user_limit=5)
        self._seed_cart(coupon_id=coupon.id)
        CouponRedemption.objects.create(coupon=coupon, user=self.user)
        response = self._order_post()
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertIsNone(order.coupon)
        self.assertEqual(order.discount, Decimal('0.00'))
        # No new redemption row for this order.
        self.assertEqual(CouponRedemption.objects.filter(coupon=coupon).count(), 1)

    def test_per_user_limit_stops_repeat_use_across_orders(self):
        coupon = make_coupon(code='LIMIT1', max_uses=10, per_user_limit=1)
        self._seed_cart(coupon_id=coupon.id)
        self._order_post()
        self.assertEqual(CouponRedemption.objects.filter(coupon=coupon).count(), 1)

        # Clear cart, re-add, try the coupon again for a second order.
        CartItem.objects.all().delete()
        self._seed_cart(coupon_id=coupon.id)
        response = self._order_post(token='second-order')
        self.assertEqual(response.status_code, 302)
        second = Order.objects.get(user=self.user, checkout_token='second-order')
        self.assertIsNone(second.coupon)
        self.assertEqual(second.discount, Decimal('0.00'))
        self.assertEqual(CouponRedemption.objects.filter(coupon=coupon).count(), 1)
