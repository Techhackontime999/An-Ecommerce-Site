"""The full Platform Studio settings schema.

Every setting the superuser can edit is declared here once. Each entry carries
its default value (mirroring the current hard-coded site content), so the
platform behaves exactly as before until a superuser changes something.

Each definition is a dict::

    key        unique slug used in templates (``platform_settings.<key>``)
    label      human-readable label shown in the studio
    group      one of the group keys below
    field_type text | textarea | boolean | select | color | number
    default    string value (booleans use ``'0'`` / ``'1'``)
    help_text  short helper shown under the input
    choices    list of (value, label) for ``select`` fields
"""

GROUP_ORDER = [
    'brand',
    'appearance',
    'homepage',
    'navbar',
    'footer',
    'seo',
    'contact',
    'commerce',
    'custom',
]

GROUPS = {
    'brand': {
        'label': 'Brand & Identity',
        'description': 'The name, logo and tagline shown across the whole site.',
        'icon': 'palette',
    },
    'appearance': {
        'label': 'Appearance',
        'description': 'Site-wide look & feel defaults (used when a visitor has no personal preference).',
        'icon': 'droplet',
    },
    'homepage': {
        'label': 'Homepage',
        'description': 'Every text block on the landing page, from hero to footer call-to-action.',
        'icon': 'home',
    },
    'navbar': {
        'label': 'Header & Navigation',
        'description': 'The top navigation bar, logo and search behaviour.',
        'icon': 'layout',
    },
    'footer': {
        'label': 'Footer',
        'description': 'Footer blurb, social links, column visibility and copyright line.',
        'icon': 'columns',
    },
    'seo': {
        'label': 'SEO & Analytics',
        'description': 'Search-engine meta tags and third-party tracking snippets.',
        'icon': 'search',
    },
    'contact': {
        'label': 'Contact Details',
        'description': 'Public contact information used around the storefront.',
        'icon': 'phone',
    },
    'commerce': {
        'label': 'Store Settings',
        'description': 'Default currency and store behaviour.',
        'icon': 'shopping',
    },
    'custom': {
        'label': 'Custom Code',
        'description': 'Add your own CSS / JS / HTML without touching any files.',
        'icon': 'code',
    },
}


def _currency_choices():
    from preferences.currencies import CURRENCIES

    return [(code, info['name']) for code, info in CURRENCIES.items()]


def setting(key, label, group, field_type, default, help_text='', choices=None):
    return {
        'key': key,
        'label': label,
        'group': group,
        'field_type': field_type,
        'default': default,
        'help_text': help_text,
        'choices': choices or [],
    }


# (key, label, group, field_type, default, help_text, choices)
_S = setting

ALL_SETTINGS = [
    # ---- Brand & Identity ----
    _S('site_name', 'Site name', 'brand', 'text', 'Shop-Seed',
       'Shown in the logo, page titles and metadata.'),
    _S('site_tagline', 'Tagline', 'brand', 'text', 'Premium E-Commerce',
       'Short tagline appended to page titles.'),
    _S('logo_mark', 'Logo letter', 'brand', 'text', 'S',
       'The letter displayed inside the logo box in the header and footer.'),
    _S('brand_description', 'Brand description', 'brand', 'textarea',
       "India's most trusted e-commerce platform. Discover premium products at unbeatable prices with fast delivery.",
       'Used in the footer and the about section.'),
    _S('support_email', 'Support email', 'brand', 'text', 'support@shop-seed.com',
       'Public support address.'),
    _S('copyright_holder', 'Copyright holder', 'brand', 'text', 'Shop-Seed',
       'Name used in the footer copyright line.'),

    # ---- Appearance ----
    _S('default_theme', 'Default theme', 'appearance', 'select', 'light',
       'Theme shown to visitors who have not chosen one personally.',
       [('light', 'Light'), ('dark', 'Dark')]),
    _S('default_accent', 'Default accent colour', 'appearance', 'select', 'orange',
       'Primary accent used across the storefront.',
       [
           ('orange', 'Orange'), ('teal', 'Teal'), ('blue', 'Blue'),
           ('purple', 'Purple'), ('green', 'Green'), ('rose', 'Rose'),
           ('indigo', 'Indigo'), ('cyan', 'Cyan'), ('amber', 'Amber'),
           ('pink', 'Pink'), ('lime', 'Lime'), ('gold', 'Gold'),
       ]),
    _S('default_font', 'Default font style', 'appearance', 'select', 'default',
       'Typography style for the storefront.',
       [
           ('default', 'Default'), ('serif', 'Serif'), ('mono', 'Monospace'),
           ('rounded', 'Rounded'), ('elegant', 'Elegant'), ('playful', 'Playful'),
           ('hand', 'Handwritten'),
       ]),
    _S('default_text_size', 'Default text size', 'appearance', 'select', 'regular',
       'Base text size for the storefront.',
       [('small', 'Small'), ('regular', 'Regular'), ('large', 'Large'), ('xl', 'Extra Large')]),
    _S('allow_theme_toggle', 'Show theme toggle button', 'appearance', 'boolean', '1',
       'Lets visitors switch between light and dark mode from the navbar.'),
    _S('allow_language_selector', 'Show language selector', 'appearance', 'boolean', '1',
       'Lets visitors change the site language.'),
    _S('allow_currency_selector', 'Show currency selector', 'appearance', 'boolean', '1',
       'Lets visitors change the display currency.'),

    # ---- Homepage ----
    _S('hero_badge_text', 'Hero badge text', 'homepage', 'text', 'Big Sale — Up to 60% Off',
       'Small badge above the hero heading.'),
    _S('hero_title_1', 'Hero heading line 1', 'homepage', 'text', 'Shop'),
    _S('hero_title_2', 'Hero heading line 2', 'homepage', 'text', 'Smarter,'),
    _S('hero_title_3', 'Hero heading line 3', 'homepage', 'text', 'Live'),
    _S('hero_title_4', 'Hero heading line 4', 'homepage', 'text', 'Better'),
    _S('hero_subtitle', 'Hero subtitle', 'homepage', 'textarea',
       "India's most trusted online marketplace. From fashion to electronics, find everything you need with fast delivery, easy returns, and best prices.",
       'Paragraph under the hero heading.'),
    _S('hero_cta_text', 'Hero primary button', 'homepage', 'text', 'Shop Now'),
    _S('hero_cta_url', 'Hero primary button link', 'homepage', 'text', '/shop/',
       'Relative or absolute URL.'),
    _S('hero_ghost_text', 'Hero secondary button', 'homepage', 'text', 'View Deals'),
    _S('hero_ghost_url', 'Hero secondary button link', 'homepage', 'text', '/todays-deals/',
       'Relative or absolute URL.'),

    _S('features_badge', 'Features badge', 'homepage', 'text', 'Why Shop-Seed'),
    _S('features_heading', 'Features heading', 'homepage', 'text', 'Why Millions Trust Us'),

    _S('feature_1_icon', 'Feature 1 icon', 'homepage', 'text', 'fa-truck',
       'Any Font Awesome icon class, e.g. fa-truck.'),
    _S('feature_1_title', 'Feature 1 title', 'homepage', 'text', 'Free & Fast Delivery'),
    _S('feature_1_text', 'Feature 1 text', 'homepage', 'textarea',
       'Free delivery on orders above $49. Express shipping available in select cities with real-time tracking.'),
    _S('feature_2_icon', 'Feature 2 icon', 'homepage', 'text', 'fa-rotate-left'),
    _S('feature_2_title', 'Feature 2 title', 'homepage', 'text', 'Easy Returns'),
    _S('feature_2_text', 'Feature 2 text', 'homepage', 'textarea',
       '30-day return policy with free pickup. No questions asked — we believe in hassle-free shopping.'),
    _S('feature_3_icon', 'Feature 3 icon', 'homepage', 'text', 'fa-headset'),
    _S('feature_3_title', 'Feature 3 title', 'homepage', 'text', '24/7 Customer Care'),
    _S('feature_3_text', 'Feature 3 text', 'homepage', 'textarea',
       "Dedicated support team available round the clock. Call, chat, or email — we're here for you anytime."),
    _S('feature_4_icon', 'Feature 4 icon', 'homepage', 'text', 'fa-shield'),
    _S('feature_4_title', 'Feature 4 title', 'homepage', 'text', 'Secure Payments'),
    _S('feature_4_text', 'Feature 4 text', 'homepage', 'textarea',
       '100% secure transactions with encrypted checkout. Your privacy and data security are our top priority.'),

    _S('collections_badge', 'Collections badge', 'homepage', 'text', 'Categories'),
    _S('collections_heading', 'Collections heading', 'homepage', 'text', 'Shop by Category'),
    _S('collection_1_label', 'Collection 1 eyebrow', 'homepage', 'text', 'Featured'),
    _S('collection_1_title', 'Collection 1 title', 'homepage', 'text', "Women's Collection"),
    _S('collection_2_label', 'Collection 2 eyebrow', 'homepage', 'text', 'New'),
    _S('collection_2_title', 'Collection 2 title', 'homepage', 'text', "Men's Collection"),
    _S('collection_3_label', 'Collection 3 eyebrow', 'homepage', 'text', 'Trending'),
    _S('collection_3_title', 'Collection 3 title', 'homepage', 'text', 'Accessories'),
    _S('collection_4_label', 'Collection 4 eyebrow', 'homepage', 'text', 'Essentials'),
    _S('collection_4_title', 'Collection 4 title', 'homepage', 'text', 'Footwear'),

    _S('featured_badge', 'Featured badge', 'homepage', 'text', 'Featured'),
    _S('featured_heading', 'Featured heading', 'homepage', 'text', 'Best Sellers'),
    _S('featured_subtitle', 'Featured subtitle', 'homepage', 'textarea',
       'Most-loved products at unbeatable prices. Updated daily with new deals.'),

    _S('deals_badge', 'Deals badge', 'homepage', 'text', 'Limited Time'),
    _S('deals_heading', 'Deals heading', 'homepage', 'text', "Today's Hot Deals"),
    _S('deals_subtitle', 'Deals subtitle', 'homepage', 'textarea',
       "Unbeatable discounts on top products. Grab them before they're gone."),
    _S('deals_link_text', 'Deals "view all" text', 'homepage', 'text', 'View All Deals'),

    _S('testimonial_quote', 'Testimonial quote', 'homepage', 'textarea',
       "Shop-Seed transformed the way I shop online. The quality is unmatched, delivery is lightning-fast, and their support team genuinely cares. I haven't had a single disappointment in over a year of shopping here."),
    _S('testimonial_name', 'Testimonial name', 'homepage', 'text', 'Priya Sharma'),
    _S('testimonial_role', 'Testimonial role', 'homepage', 'text', 'Verified Buyer, 24 orders'),

    _S('cta_heading', 'Call-to-action heading', 'homepage', 'text', 'Start Shopping Today'),
    _S('cta_text', 'Call-to-action text', 'homepage', 'textarea',
       'Join millions of satisfied customers who trust Shop-Seed for premium products at the best prices with fast delivery.'),
    _S('cta_button_text', 'Call-to-action button', 'homepage', 'text', 'Get Started Free'),
    _S('cta_button_url', 'Call-to-action button link', 'homepage', 'text', '/accounts/signup/',
       'Relative or absolute URL.'),

    # ---- Header & Navigation ----
    _S('show_nav_deals', 'Show "Deals" link', 'navbar', 'boolean', '1'),
    _S('show_nav_about', 'Show "About" link', 'navbar', 'boolean', '1'),
    _S('show_nav_best_sellers', 'Show "Best Sellers" link', 'navbar', 'boolean', '1'),
    _S('show_nav_services', 'Show "Services" link', 'navbar', 'boolean', '1'),
    _S('show_nav_blog', 'Show "Blog" link', 'navbar', 'boolean', '1'),
    _S('search_placeholder', 'Search box placeholder', 'navbar', 'text', 'Search products...'),

    # ---- Footer ----
    _S('show_footer_shop', 'Show "Shop" column', 'footer', 'boolean', '1'),
    _S('show_footer_support', 'Show "Support" column', 'footer', 'boolean', '1'),
    _S('show_footer_company', 'Show "Company" column', 'footer', 'boolean', '1'),
    _S('show_footer_social', 'Show social icons', 'footer', 'boolean', '1'),
    _S('footer_copyright', 'Copyright line', 'footer', 'text', '© 2026 Shop-Seed. All rights reserved.'),
    _S('social_twitter', 'Twitter / X URL', 'footer', 'text', '#'),
    _S('social_instagram', 'Instagram URL', 'footer', 'text', '#'),
    _S('social_facebook', 'Facebook URL', 'footer', 'text', '#'),
    _S('social_linkedin', 'LinkedIn URL', 'footer', 'text', '#'),
    _S('social_youtube', 'YouTube URL', 'footer', 'text', '#'),

    # ---- SEO & Analytics ----
    _S('meta_description', 'Meta description', 'seo', 'textarea',
       'Shop-Seed — Premium e-commerce platform',
       'Shown under the page title in search results.'),
    _S('meta_keywords', 'Meta keywords', 'seo', 'text',
       'shop, ecommerce, online shopping, deals, products'),
    _S('meta_robots', 'Robots directive', 'seo', 'select', 'index, follow',
       'Controls how search engines index the site.',
       [('index, follow', 'Index + follow (recommended)'),
        ('noindex, follow', 'No index, follow links'),
        ('noindex, nofollow', 'No index, no follow')]),
    _S('google_analytics_id', 'Google Analytics ID', 'seo', 'text', '',
       'e.g. G-XXXXXXXXXX — the tracking snippet is injected automatically.'),
    _S('pixel_html', 'Extra tracking / pixel code', 'seo', 'textarea', '',
       'Raw HTML injected into the <head> on every page (Analytics, Meta Pixel, etc.).'),

    # ---- Contact Details ----
    _S('contact_email', 'Contact email', 'contact', 'text', 'support@shop-seed.com'),
    _S('contact_phone', 'Contact phone', 'contact', 'text', '+1 (800) 123-4567'),
    _S('contact_address', 'Contact address', 'contact', 'textarea',
       'Shop-Seed HQ, 100 Market Street, New York, NY'),
    _S('support_hours', 'Support hours', 'contact', 'text', '24/7'),

    # ---- Store Settings ----
    _S('default_currency', 'Default currency', 'commerce', 'select', 'INR',
       'Currency shown to visitors who have not chosen one.',
       _currency_choices()),
    _S('free_shipping_threshold', 'Free shipping threshold', 'commerce', 'number', '999',
       'Order amount (in default currency) that unlocks free shipping.'),
    _S('products_per_page', 'Products per page', 'commerce', 'number', '12',
       'How many products are shown per page in the shop.'),
    _S('show_news_ticker', 'Show news ticker bar', 'commerce', 'boolean', '1'),

    # ---- Custom Code ----
    _S('custom_css', 'Custom CSS', 'custom', 'textarea', '',
       'Plain CSS injected into every page. No <style> tags needed.'),
    _S('custom_js', 'Custom JavaScript', 'custom', 'textarea', '',
       'Plain JS injected before the closing </body> tag. No <script> tags needed.'),
    _S('custom_header_html', 'Custom <head> HTML', 'custom', 'textarea', '',
       'Raw HTML added inside the <head> (fonts, meta, scripts).'),
    _S('custom_body_top', 'Custom top-of-body HTML', 'custom', 'textarea', '',
       'Raw HTML inserted at the very top of every page body.'),
    _S('custom_body_bottom', 'Custom bottom-of-body HTML', 'custom', 'textarea', '',
       'Raw HTML inserted right before the closing </body> tag.'),
]


def get_group_definition(group_key):
    return GROUPS.get(group_key)


def settings_in_group(group_key):
    return [s for s in ALL_SETTINGS if s['group'] == group_key]


def iter_groups():
    return [(key, GROUPS[key]) for key in GROUP_ORDER if key in GROUPS]


def setting_by_key(key):
    for s in ALL_SETTINGS:
        if s['key'] == key:
            return s
    return None
