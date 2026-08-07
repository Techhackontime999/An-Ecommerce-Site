from decimal import Decimal
from django.conf import settings
from coupons.models import Coupon
from shop.models import Product, ProductVariant
from .models import CartItem

class Cart():

    def __init__(self, request):
        """
        Initialize the cart. The session cart works for guests; signed-in
        users get their cart persisted to the database too.
        """
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            # save an empty cart in the session
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart
        # store current applied coupon
        self.coupon_id = self.session.get('coupon_id')

        user = getattr(request, 'user', None)
        self.user = user if (user is not None and user.is_authenticated) else None
        if self.user:
            self._hydrate_from_db()

    @staticmethod
    def _key(product_id, variant_id=None):
        if variant_id:
            return f'{product_id}:{variant_id}'
        return str(product_id)

    @staticmethod
    def _parse_key(key):
        if ':' in key:
            pid, vid = key.split(':', 1)
            return int(pid), int(vid)
        return int(key), None

    def _hydrate_from_db(self):
        """Merge the user's saved cart into the session (session wins on conflicts)."""
        if not self.user:
            return
        changed = False
        for item in CartItem.objects.filter(user=self.user).select_related('product'):
            if item.key not in self.cart:
                self.cart[item.key] = {
                    'quantity': item.quantity,
                    'price': str(item.product.price),
                    'variant_id': item.variant_id,
                }
                changed = True
        if changed:
            self.session.modified = True

    def _persist_to_db(self):
        """Full-sync the session cart into the database for signed-in users."""
        if not self.user:
            return
        existing = {item.key: item for item in CartItem.objects.filter(user=self.user)}
        for key, entry in self.cart.items():
            pid, vid = self._parse_key(key)
            item = existing.get(key)
            if item is not None:
                if item.quantity != entry['quantity']:
                    item.quantity = entry['quantity']
                    item.save(update_fields=['quantity', 'updated'])
            else:
                CartItem.objects.create(
                    user=self.user,
                    product_id=pid,
                    variant_id=vid,
                    key=key,
                    quantity=entry['quantity'],
                )
        stale = set(existing) - set(self.cart)
        if stale:
            CartItem.objects.filter(user=self.user, key__in=stale).delete()

    def add(self, product, quantity=1, update_quantity=False, variant_id=None, price=None):
        """
        Add a product to the cart or update its quantity.
        """
        key = self._key(product.id, variant_id)
        if price is None:
            price = product.price
        if key not in self.cart:
            self.cart[key] = {
                'quantity': 0,
                'price': str(price),
                'variant_id': variant_id,
            }
        if update_quantity:
            self.cart[key]['quantity'] = quantity
        else:
            self.cart[key]['quantity'] += quantity
        self.cart[key]['price'] = str(price)
        self.save()

    def save(self):
        """
        mark the session as "modified" to make sure it gets saved
        """
        self.session.modified = True
        self._persist_to_db()

    def remove(self, product, variant_id=None):
        """
        Remove a product from the cart.
        """
        key = self._key(product.id, variant_id)
        if key in self.cart:
            del self.cart[key]
            self.save()

    def __iter__(self):
        """
        Iterate over the items in the cart and get the products
        from the database, applying deal/variant prices if available.
        """
        product_ids = set()
        variant_ids = set()
        for key in self.cart.keys():
            if ':' in key:
                pid, vid = key.split(':', 1)
                product_ids.add(int(pid))
                variant_ids.add(int(vid))
            else:
                product_ids.add(int(key))

        products = Product.objects.filter(id__in=product_ids)
        variants = {v.id: v for v in ProductVariant.objects.filter(id__in=variant_ids)}
        # Deep-copy entries so enriching them (Decimal prices, product objects)
        # never writes unserializable values back into the session cart.
        cart = {k: dict(v) for k, v in self.cart.items()}

        for product in products:
            current_price = product.current_price
            for key, entry in list(cart.items()):
                if key.startswith(f'{product.id}:'):
                    variant = variants.get(entry.get('variant_id'))
                    if variant and not variant.active:
                        continue
                    entry['product'] = product
                    if variant:
                        entry['variant'] = variant
                        entry['price'] = str(variant.effective_price)
                    else:
                        entry['price'] = str(current_price)
                    entry['total_price'] = Decimal(entry['price']) * entry['quantity']
                elif key == str(product.id):
                    entry['product'] = product
                    entry['price'] = str(current_price)
                    entry['total_price'] = current_price * entry['quantity']

        for item in cart.values():
            if 'product' not in item:
                continue
            item['price'] = Decimal(item['price'])
            yield item

    def __len__(self):
        """
        Count all items in the cart.
        """
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        return sum(Decimal(item['price']) * item['quantity'] for item in self)


    def clear(self):
        """
        remove cart from session
        """
        del self.session[settings.CART_SESSION_ID]
        self.save()

    @property
    def coupon(self):
        if self.coupon_id:
            return Coupon.objects.get(id=self.coupon_id)
        return None

    def get_discount(self):
        if self.coupon:
            return (self.coupon.discount / Decimal('100')) \
                * self.get_total_price()
        return Decimal('0')

    def get_total_price_after_discount(self):
        return self.get_total_price() - self.get_discount()
