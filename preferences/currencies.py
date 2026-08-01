"""Currencies supported by the site.

Prices are stored in USD. ``rate`` below is only a *static fallback* used
when the live exchange-rate API (see ``preferences.exchange``) is unreachable.
The site always tries to use fresh, real rates fetched from the API and cached
for a few hours, so conversions stay correct instead of going stale.
"""

CURRENCIES = {
    'USD': {'symbol': '$', 'rate': 1.0, 'decimals': 2, 'name': 'US Dollar'},
    'EUR': {'symbol': '€', 'rate': 0.86, 'decimals': 2, 'name': 'Euro'},
    'GBP': {'symbol': '£', 'rate': 0.74, 'decimals': 2, 'name': 'British Pound'},
    'INR': {'symbol': '₹', 'rate': 88.0, 'decimals': 2, 'name': 'Indian Rupee'},
    'JPY': {'symbol': '¥', 'rate': 148.0, 'decimals': 0, 'name': 'Japanese Yen'},
    'AUD': {'symbol': 'A$', 'rate': 1.53, 'decimals': 2, 'name': 'Australian Dollar'},
    'CAD': {'symbol': 'C$', 'rate': 1.42, 'decimals': 2, 'name': 'Canadian Dollar'},
    'CHF': {'symbol': 'CHF ', 'rate': 0.83, 'decimals': 2, 'name': 'Swiss Franc'},
    'CNY': {'symbol': '¥', 'rate': 7.1, 'decimals': 2, 'name': 'Chinese Yuan'},
    'RUB': {'symbol': '₽', 'rate': 92.0, 'decimals': 2, 'name': 'Russian Ruble'},
    'BRL': {'symbol': 'R$', 'rate': 5.6, 'decimals': 2, 'name': 'Brazilian Real'},
    'KRW': {'symbol': '₩', 'rate': 1390.0, 'decimals': 0, 'name': 'South Korean Won'},
    'AED': {'symbol': 'د.إ', 'rate': 3.67, 'decimals': 2, 'name': 'UAE Dirham'},
    'MXN': {'symbol': 'MX$', 'rate': 18.4, 'decimals': 2, 'name': 'Mexican Peso'},
    'SGD': {'symbol': 'S$', 'rate': 1.31, 'decimals': 2, 'name': 'Singapore Dollar'},
    'NZD': {'symbol': 'NZ$', 'rate': 1.68, 'decimals': 2, 'name': 'New Zealand Dollar'},
    'ZAR': {'symbol': 'R', 'rate': 18.1, 'decimals': 2, 'name': 'South African Rand'},
    'TRY': {'symbol': '₺', 'rate': 38.0, 'decimals': 2, 'name': 'Turkish Lira'},
    'PHP': {'symbol': '₱', 'rate': 56.5, 'decimals': 2, 'name': 'Philippine Peso'},
    'IDR': {'symbol': 'Rp', 'rate': 16200.0, 'decimals': 0, 'name': 'Indonesian Rupiah'},
    'THB': {'symbol': '฿', 'rate': 34.0, 'decimals': 2, 'name': 'Thai Baht'},
    'VND': {'symbol': '₫', 'rate': 25500.0, 'decimals': 0, 'name': 'Vietnamese Dong'},
    'MYR': {'symbol': 'RM', 'rate': 4.35, 'decimals': 2, 'name': 'Malaysian Ringgit'},
    'PLN': {'symbol': 'zł', 'rate': 3.95, 'decimals': 2, 'name': 'Polish Złoty'},
    'CZK': {'symbol': 'Kč', 'rate': 23.2, 'decimals': 2, 'name': 'Czech Koruna'},
    'HUF': {'symbol': 'Ft', 'rate': 365.0, 'decimals': 0, 'name': 'Hungarian Forint'},
    'SEK': {'symbol': 'kr', 'rate': 10.4, 'decimals': 2, 'name': 'Swedish Krona'},
    'NOK': {'symbol': 'kr', 'rate': 10.7, 'decimals': 2, 'name': 'Norwegian Krone'},
    'DKK': {'symbol': 'kr', 'rate': 6.4, 'decimals': 2, 'name': 'Danish Krone'},
    'ILS': {'symbol': '₪', 'rate': 3.65, 'decimals': 2, 'name': 'Israeli New Shekel'},
    'SAR': {'symbol': 'ر.س', 'rate': 3.75, 'decimals': 2, 'name': 'Saudi Riyal'},
    'QAR': {'symbol': 'ر.ق', 'rate': 3.64, 'decimals': 2, 'name': 'Qatari Riyal'},
    'KWD': {'symbol': 'د.ك', 'rate': 0.31, 'decimals': 3, 'name': 'Kuwaiti Dinar'},
    'BHD': {'symbol': 'د.ب', 'rate': 0.38, 'decimals': 3, 'name': 'Bahraini Dinar'},
    'OMR': {'symbol': 'ر.ع', 'rate': 0.385, 'decimals': 3, 'name': 'Omani Rial'},
    'HKD': {'symbol': 'HK$', 'rate': 7.8, 'decimals': 2, 'name': 'Hong Kong Dollar'},
    'TWD': {'symbol': 'NT$', 'rate': 32.2, 'decimals': 2, 'name': 'Taiwan Dollar'},
    'ARS': {'symbol': 'ARS ', 'rate': 1400.0, 'decimals': 2, 'name': 'Argentine Peso'},
    'CLP': {'symbol': 'CLP ', 'rate': 940.0, 'decimals': 0, 'name': 'Chilean Peso'},
    'COP': {'symbol': 'COP ', 'rate': 4100.0, 'decimals': 0, 'name': 'Colombian Peso'},
    'PEN': {'symbol': 'S/ ', 'rate': 3.72, 'decimals': 2, 'name': 'Peruvian Sol'},
    'NGN': {'symbol': '₦', 'rate': 1520.0, 'decimals': 2, 'name': 'Nigerian Naira'},
    'KES': {'symbol': 'KSh', 'rate': 129.0, 'decimals': 2, 'name': 'Kenyan Shilling'},
    'EGP': {'symbol': 'E£', 'rate': 49.0, 'decimals': 2, 'name': 'Egyptian Pound'},
    'PKR': {'symbol': '₨', 'rate': 279.0, 'decimals': 2, 'name': 'Pakistani Rupee'},
    'BDT': {'symbol': '৳', 'rate': 118.0, 'decimals': 2, 'name': 'Bangladeshi Taka'},
    'LKR': {'symbol': 'රු', 'rate': 298.0, 'decimals': 2, 'name': 'Sri Lankan Rupee'},
    'MMK': {'symbol': 'K', 'rate': 2100.0, 'decimals': 0, 'name': 'Myanmar Kyat'},
    'UAH': {'symbol': '₴', 'rate': 41.5, 'decimals': 2, 'name': 'Ukrainian Hryvnia'},
    'GHS': {'symbol': 'GH₵', 'rate': 15.2, 'decimals': 2, 'name': 'Ghanaian Cedi'},
}

DEFAULT_CURRENCY = 'USD'
