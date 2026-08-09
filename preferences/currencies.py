"""Currencies supported by the site.

Prices are stored in INR. ``rate`` below is only a *static fallback* used
when the live exchange-rate API (see ``preferences.exchange``) is unreachable.
The site always tries to use fresh, real rates fetched from the API and cached
for a few hours, so conversions stay correct instead of going stale.
"""

CURRENCIES = {
    'USD': {'symbol': '$', 'rate': 0.011364, 'decimals': 2, 'name': 'US Dollar'},
    'EUR': {'symbol': '€', 'rate': 0.009773, 'decimals': 2, 'name': 'Euro'},
    'GBP': {'symbol': '£', 'rate': 0.008409, 'decimals': 2, 'name': 'British Pound'},
    'INR': {'symbol': '₹', 'rate': 1.0, 'decimals': 2, 'name': 'Indian Rupee'},
    'JPY': {'symbol': '¥', 'rate': 1.681818, 'decimals': 0, 'name': 'Japanese Yen'},
    'AUD': {'symbol': 'A$', 'rate': 0.017386, 'decimals': 2, 'name': 'Australian Dollar'},
    'CAD': {'symbol': 'C$', 'rate': 0.016136, 'decimals': 2, 'name': 'Canadian Dollar'},
    'CHF': {'symbol': 'CHF ', 'rate': 0.009432, 'decimals': 2, 'name': 'Swiss Franc'},
    'CNY': {'symbol': '¥', 'rate': 0.080682, 'decimals': 2, 'name': 'Chinese Yuan'},
    'RUB': {'symbol': '₽', 'rate': 1.045455, 'decimals': 2, 'name': 'Russian Ruble'},
    'BRL': {'symbol': 'R$', 'rate': 0.063636, 'decimals': 2, 'name': 'Brazilian Real'},
    'KRW': {'symbol': '₩', 'rate': 15.795455, 'decimals': 0, 'name': 'South Korean Won'},
    'AED': {'symbol': 'د.إ', 'rate': 0.041705, 'decimals': 2, 'name': 'UAE Dirham'},
    'MXN': {'symbol': 'MX$', 'rate': 0.209091, 'decimals': 2, 'name': 'Mexican Peso'},
    'SGD': {'symbol': 'S$', 'rate': 0.014886, 'decimals': 2, 'name': 'Singapore Dollar'},
    'NZD': {'symbol': 'NZ$', 'rate': 0.019091, 'decimals': 2, 'name': 'New Zealand Dollar'},
    'ZAR': {'symbol': 'R', 'rate': 0.205682, 'decimals': 2, 'name': 'South African Rand'},
    'TRY': {'symbol': '₺', 'rate': 0.431818, 'decimals': 2, 'name': 'Turkish Lira'},
    'PHP': {'symbol': '₱', 'rate': 0.642045, 'decimals': 2, 'name': 'Philippine Peso'},
    'IDR': {'symbol': 'Rp', 'rate': 184.090909, 'decimals': 0, 'name': 'Indonesian Rupiah'},
    'THB': {'symbol': '฿', 'rate': 0.386364, 'decimals': 2, 'name': 'Thai Baht'},
    'VND': {'symbol': '₫', 'rate': 289.772727, 'decimals': 0, 'name': 'Vietnamese Dong'},
    'MYR': {'symbol': 'RM', 'rate': 0.049432, 'decimals': 2, 'name': 'Malaysian Ringgit'},
    'PLN': {'symbol': 'zł', 'rate': 0.044886, 'decimals': 2, 'name': 'Polish Złoty'},
    'CZK': {'symbol': 'Kč', 'rate': 0.263636, 'decimals': 2, 'name': 'Czech Koruna'},
    'HUF': {'symbol': 'Ft', 'rate': 4.147727, 'decimals': 0, 'name': 'Hungarian Forint'},
    'SEK': {'symbol': 'kr', 'rate': 0.118182, 'decimals': 2, 'name': 'Swedish Krona'},
    'NOK': {'symbol': 'kr', 'rate': 0.121591, 'decimals': 2, 'name': 'Norwegian Krone'},
    'DKK': {'symbol': 'kr', 'rate': 0.072727, 'decimals': 2, 'name': 'Danish Krone'},
    'ILS': {'symbol': '₪', 'rate': 0.041477, 'decimals': 2, 'name': 'Israeli New Shekel'},
    'SAR': {'symbol': 'ر.س', 'rate': 0.042614, 'decimals': 2, 'name': 'Saudi Riyal'},
    'QAR': {'symbol': 'ر.ق', 'rate': 0.041364, 'decimals': 2, 'name': 'Qatari Riyal'},
    'KWD': {'symbol': 'د.ك', 'rate': 0.003523, 'decimals': 3, 'name': 'Kuwaiti Dinar'},
    'BHD': {'symbol': 'د.ب', 'rate': 0.004318, 'decimals': 3, 'name': 'Bahraini Dinar'},
    'OMR': {'symbol': 'ر.ع', 'rate': 0.004375, 'decimals': 3, 'name': 'Omani Rial'},
    'HKD': {'symbol': 'HK$', 'rate': 0.088636, 'decimals': 2, 'name': 'Hong Kong Dollar'},
    'TWD': {'symbol': 'NT$', 'rate': 0.365909, 'decimals': 2, 'name': 'Taiwan Dollar'},
    'ARS': {'symbol': 'ARS ', 'rate': 15.909091, 'decimals': 2, 'name': 'Argentine Peso'},
    'CLP': {'symbol': 'CLP ', 'rate': 10.681818, 'decimals': 0, 'name': 'Chilean Peso'},
    'COP': {'symbol': 'COP ', 'rate': 46.590909, 'decimals': 0, 'name': 'Colombian Peso'},
    'PEN': {'symbol': 'S/ ', 'rate': 0.042273, 'decimals': 2, 'name': 'Peruvian Sol'},
    'NGN': {'symbol': '₦', 'rate': 17.272727, 'decimals': 2, 'name': 'Nigerian Naira'},
    'KES': {'symbol': 'KSh', 'rate': 1.465909, 'decimals': 2, 'name': 'Kenyan Shilling'},
    'EGP': {'symbol': 'E£', 'rate': 0.556818, 'decimals': 2, 'name': 'Egyptian Pound'},
    'PKR': {'symbol': '₨', 'rate': 3.170455, 'decimals': 2, 'name': 'Pakistani Rupee'},
    'BDT': {'symbol': '৳', 'rate': 1.340909, 'decimals': 2, 'name': 'Bangladeshi Taka'},
    'LKR': {'symbol': 'රු', 'rate': 3.386364, 'decimals': 2, 'name': 'Sri Lankan Rupee'},
    'MMK': {'symbol': 'K', 'rate': 23.863636, 'decimals': 0, 'name': 'Myanmar Kyat'},
    'UAH': {'symbol': '₴', 'rate': 0.471591, 'decimals': 2, 'name': 'Ukrainian Hryvnia'},
    'GHS': {'symbol': 'GH₵', 'rate': 0.172727, 'decimals': 2, 'name': 'Ghanaian Cedi'},
}

DEFAULT_CURRENCY = 'INR'
