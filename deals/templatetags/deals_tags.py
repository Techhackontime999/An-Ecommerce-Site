from django import template

register = template.Library()


@register.filter
def discount_percent(price, deal_price):
    try:
        price = float(price)
        deal_price = float(deal_price)
        if price <= 0:
            return 0
        return round((price - deal_price) / price * 100)
    except (TypeError, ValueError):
        return 0
