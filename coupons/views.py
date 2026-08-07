from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from cart.cart import Cart
from .forms import CouponApplyForm
from .models import Coupon
from .services import validate_coupon


@require_POST
@login_required
def coupon_apply(request):
    """Apply a coupon to the current cart.

    Every limit (dates, usage, per-user, scoping, minimum total) is enforced
    here — an invalid or exhausted coupon is never stored in the session.
    """
    cart = Cart(request)
    form = CouponApplyForm(request.POST)
    if form.is_valid():
        code = form.cleaned_data['code']
        try:
            coupon = Coupon.objects.get(code__iexact=code)
        except Coupon.DoesNotExist:
            coupon = None

        if coupon is None:
            request.session['coupon_id'] = None
            messages.error(request, 'Invalid coupon code.')
        else:
            ok, reason = validate_coupon(
                coupon,
                user=request.user,
                cart_total=cart.get_total_price(),
                seller_ids=cart._seller_ids(),
            )
            if ok:
                request.session['coupon_id'] = coupon.id
                messages.success(request, f'Coupon "{coupon.code}" applied.')
            else:
                request.session['coupon_id'] = None
                messages.error(request, reason)
    return redirect('cart:cart_detail')
