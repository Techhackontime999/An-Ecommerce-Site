"""Currencies supported by the site with approximate USD rates.

Rates are static defaults so the whole site works offline. You can keep them
updated from a free exchange-rate API or extend the list with more codes.
"""

CURRENCIES = {
    'USD': {'symbol': '$', 'rate': 1.0, 'decimals': 2, 'name': 'US Dollar'},
    'EUR': {'symbol': '€', 'rate': 0.92, 'decimals': 2, 'name': 'Euro'},
    'GBP': {'symbol': '£', 'rate': 0.79, 'decimals': 2, 'name': 'British Pound'},
    'INR': {'symbol': '₹', 'rate': 83.5, 'decimals': 2, 'name': 'Indian Rupee'},
    'JPY': {'symbol': '¥', 'rate': 155.0, 'decimals': 0, 'name': 'Japanese Yen'},
    'AUD': {'symbol': 'A$', 'rate': 1.52, 'decimals': 2, 'name': 'Australian Dollar'},
    'CAD': {'symbol': 'C$', 'rate': 1.36, 'decimals': 2, 'name': 'Canadian Dollar'},
    'CHF': {'symbol': 'CHF ', 'rate': 0.89, 'decimals': 2, 'name': 'Swiss Franc'},
    'CNY': {'symbol': '¥', 'rate': 7.25, 'decimals': 2, 'name': 'Chinese Yuan'},
    'RUB': {'symbol': '₽', 'rate': 88.0, 'decimals': 2, 'name': 'Russian Ruble'},
    'BRL': {'symbol': 'R$', 'rate': 5.05, 'decimals': 2, 'name': 'Brazilian Real'},
    'KRW': {'symbol': '₩', 'rate': 1360.0, 'decimals': 0, 'name': 'South Korean Won'},
    'AED': {'symbol': 'د.إ', 'rate': 3.67, 'decimals': 2, 'name': 'UAE Dirham'},
    'MXN': {'symbol': 'MX$', 'rate': 17.2, 'decimals': 2, 'name': 'Mexican Peso'},
    'SGD': {'symbol': 'S$', 'rate': 1.35, 'decimals': 2, 'name': 'Singapore Dollar'},
    'NZD': {'symbol': 'NZ$', 'rate': 1.66, 'decimals': 2, 'name': 'New Zealand Dollar'},
    'ZAR': {'symbol': 'R', 'rate': 18.9, 'decimals': 2, 'name': 'South African Rand'},
    'TRY': {'symbol': '₺', 'rate': 32.4, 'decimals': 2, 'name': 'Turkish Lira'},
}

DEFAULT_CURRENCY = 'USD'
