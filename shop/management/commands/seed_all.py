import io
import random
from datetime import timedelta
from decimal import Decimal

import requests
from PIL import Image, ImageDraw

from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from shop.models import Category, Product, ProductImage, ProductVariant, VariantImage
from accounts.models import CustomerProfile, SellerProfile
from seller.models import SellerProduct
from deals.models import Deal
from coupons.models import Coupon
from reviews.models import ProductReview, ProductReviewImage, ReviewReport
from order.models import Order, OrderItem
from payments.models import Payment
from services.models import Service
from faq.models import FAQ, Story
from about.models import AboutSection, TeamMember
from contact.models import ContactMessage
from documentation.models import DocumentationSection
from shipping.models import ShippingAddress, ShippingMethod, Shipment
from newsletter.models import Subscriber
from preferences.models import UserPreference
from notifications.models import Notification as AppNotification, NotificationPreference
from news.models import NewsItem
from blogs.models import (
    Tag as BlogTag,
    Post,
    PostImage as BlogPostImage,
    PostProduct,
    Comment as BlogComment,
    Badge,
    UserProfile as BlogUserProfile,
    Like as BlogLike,
    Bookmark as BlogBookmark,
    Follow as BlogFollow,
    Notification as BlogNotification,
    UserReaction as BlogUserReaction,
    ActivityFeedItem as BlogActivityFeedItem,
    PostView as BlogPostView,
    PostReport as BlogPostReport,
    ensure_profile as ensure_blog_profile,
)

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - older Pillow
    RESAMPLE = Image.LANCZOS


# ---------------------------------------------------------------------------
# Category themes: remote keywords + procedural gradient palettes + icons
# ---------------------------------------------------------------------------

CATEGORY_THEMES = {
    'electronics': {
        'keyword': 'electronics,smartphone,headphones,gadget',
        'palettes': [('#0f2027', '#2c5364'), ('#232526', '#414345'), ('#1a2980', '#26d0ce')],
        'icon': 'chip',
    },
    'fashion': {
        'keyword': 'fashion,clothes,t-shirt,shoes',
        'palettes': [('#ff7e5f', '#feb47b'), ('#ee9ca7', '#ffdde1'), ('#41295a', '#2F0743')],
        'icon': 'tshirt',
    },
    'home-kitchen': {
        'keyword': 'kitchen,furniture,lamp,home',
        'palettes': [('#1f4037', '#99f2c8'), ('#355c7d', '#6c5b7b'), ('#c94b4b', '#4b134f')],
        'icon': 'lamp',
    },
    'books': {
        'keyword': 'books,library,reading,book',
        'palettes': [('#603813', '#b29f94'), ('#3e5151', '#decba4'), ('#0f0c29', '#302b63')],
        'icon': 'book',
    },
    'beauty': {
        'keyword': 'beauty,cosmetics,makeup,perfume',
        'palettes': [('#f953c6', '#b91d73'), ('#ff758c', '#ff7eb3'), ('#642b73', '#c6426e')],
        'icon': 'sparkle',
    },
    'sports': {
        'keyword': 'sports,fitness,gym,yoga',
        'palettes': [('#134e5e', '#71b280'), ('#232526', '#414345'), ('#1a2a6c', '#b21f1f')],
        'icon': 'dumbbell',
    },
    'toys-games': {
        'keyword': 'toys,games,lego,boardgame',
        'palettes': [('#fc4a1a', '#f7b733'), ('#43cea2', '#185a9d'), ('#ee0979', '#ff6a00')],
        'icon': 'rocket',
    },
    'automotive': {
        'keyword': 'car,automotive,vehicle,garage',
        'palettes': [('#3a1c71', '#d76d77'), ('#141e30', '#243b55'), ('#1f1c18', '#8e0e00')],
        'icon': 'car',
    },
    'abstract': {
        'keyword': 'abstract,design,pattern,colorful',
        'palettes': [('#00c6ff', '#0072ff'), ('#f5af19', '#f12711'), ('#56ab2f', '#a8e063')],
        'icon': 'star',
    },
}

FONT_CANDIDATES = [
    r'C:\Windows\Fonts\arialbd.ttf',
    r'C:\Windows\Fonts\arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
]


def _hex(color):
    color = color.lstrip('#')
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _gradient(size, c1, c2):
    c1, c2 = _hex(c1), _hex(c2)
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        color = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color)
    return img


def _load_font(size):
    from PIL import ImageFont
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _map(box, x, y):
    x0, y0, x1, y1 = box
    return (x0 + (x1 - x0) * x / 100.0, y0 + (y1 - y0) * y / 100.0)


def _icon_chip(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    for px in (22, 36, 50, 64, 78):
        d.rectangle([m(px - 2, 0), m(px + 2, 11)], fill=color)
        d.rectangle([m(px - 2, 89), m(px + 2, 100)], fill=color)
    for py in (25, 42, 58, 75):
        d.rectangle([m(0, py - 2), m(11, py + 2)], fill=color)
        d.rectangle([m(89, py - 2), m(100, py + 2)], fill=color)
    d.rectangle([m(20, 20), m(80, 80)], outline=color, width=5)
    d.rectangle([m(37, 37), m(63, 63)], fill=shade)
    for (x1, y1, x2, y2) in [(50, 11, 50, 20), (78, 20, 78, 28), (22, 25, 22, 33), (50, 80, 50, 89)]:
        d.line([m(x1, y1), m(x2, y2)], fill=shade, width=3)


def _icon_tshirt(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.polygon([
        m(28, 28), m(38, 35), m(62, 35), m(72, 28), m(76, 42),
        m(63, 50), m(63, 74), m(37, 74), m(37, 50), m(24, 42),
    ], fill=color)
    d.ellipse([m(43, 24), m(57, 36)], fill=shade)


def _icon_lamp(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.polygon([m(38, 8), m(62, 8), m(74, 34), m(26, 34)], fill=color)
    d.line([m(50, 34), m(50, 82)], fill=shade, width=5)
    d.ellipse([m(38, 58), m(62, 70)], fill=shade)
    d.rectangle([m(24, 84), m(76, 92)], fill=color)


def _icon_book(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.polygon([m(14, 74), m(46, 74), m(46, 22), m(14, 30)], fill=color)
    d.polygon([m(54, 74), m(86, 74), m(86, 30), m(54, 22)], fill=shade)
    d.line([m(50, 74), m(50, 24)], fill=shade, width=3)
    d.line([m(20, 40), m(40, 34)], fill=shade, width=2)
    d.line([m(60, 34), m(80, 40)], fill=shade, width=2)


def _icon_sparkle(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.polygon([
        m(50, 3), m(58, 42), m(97, 50), m(58, 58),
        m(50, 97), m(42, 58), m(3, 50), m(42, 42),
    ], fill=color)
    d.ellipse([m(66, 22), m(76, 32)], fill=shade)
    d.ellipse([m(22, 66), m(32, 76)], fill=shade)


def _icon_dumbbell(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.rectangle([m(8, 36), m(30, 64)], fill=color)
    d.rectangle([m(70, 36), m(92, 64)], fill=color)
    d.rectangle([m(24, 42), m(76, 58)], fill=color)
    d.rectangle([m(32, 30), m(42, 70)], fill=shade)
    d.rectangle([m(58, 30), m(68, 70)], fill=shade)


def _icon_rocket(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.polygon([m(50, 4), m(66, 54), m(55, 82), m(45, 82), m(34, 54)], fill=color)
    d.ellipse([m(43, 34), m(57, 48)], fill=shade)
    d.polygon([m(34, 54), m(16, 82), m(30, 82)], fill=shade)
    d.polygon([m(66, 54), m(84, 82), m(70, 82)], fill=shade)
    d.polygon([m(45, 82), m(55, 82), m(50, 96)], fill=shade)


def _icon_car(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.polygon([
        m(8, 56), m(13, 42), m(30, 34), m(58, 34), m(74, 42),
        m(88, 48), m(92, 58), m(78, 62), m(20, 62),
    ], fill=color)
    d.polygon([m(30, 34), m(50, 22), m(66, 34)], fill=shade)
    for cx in (28, 72):
        d.ellipse([m(cx - 9, 54), m(cx + 9, 72)], fill=color)
        d.ellipse([m(cx - 4, 59), m(cx + 4, 67)], fill=shade)


def _icon_star(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.polygon([
        m(50, 5), m(60, 38), m(95, 50), m(60, 62),
        m(50, 95), m(40, 62), m(5, 50), m(40, 38),
    ], fill=color)
    d.ellipse([m(28, 22), m(36, 30)], fill=shade)


def _icon_gift(d, box, color, shade):
    m = lambda x, y: _map(box, x, y)
    d.rectangle([m(20, 38), m(80, 88)], fill=color)
    d.rectangle([m(20, 30), m(80, 42)], fill=color)
    d.rectangle([m(44, 30), m(56, 88)], fill=shade)
    d.polygon([m(20, 32), m(50, 8), m(80, 32)], fill=shade)


ICON_DRAWERS = {
    'chip': _icon_chip,
    'tshirt': _icon_tshirt,
    'lamp': _icon_lamp,
    'book': _icon_book,
    'sparkle': _icon_sparkle,
    'dumbbell': _icon_dumbbell,
    'rocket': _icon_rocket,
    'car': _icon_car,
    'star': _icon_star,
    'gift': _icon_gift,
}


def _generate_category_image(slug):
    """Procedurally draw a gradient background with a category icon."""
    theme = CATEGORY_THEMES[slug]
    size = 640
    c1, c2 = random.choice(theme['palettes'])
    img = _gradient(size, c1, c2).convert('RGBA')
    overlay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for _ in range(12):
        x = random.randint(0, size)
        y = random.randint(0, size)
        r = random.randint(8, 42)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, 42), width=3)
    drawer = ICON_DRAWERS.get(theme['icon'])
    if drawer:
        box = (size * 0.18, size * 0.16, size * 0.82, size * 0.88)
        drawer(d, box, (255, 255, 255, 215), (255, 255, 255, 95))
    img = Image.alpha_composite(img, overlay).convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=80)
    return ContentFile(buf.getvalue())


def _generate_avatar(name):
    """Solid background + initials, used for profile/team photos."""
    size = 300
    bg = random.choice([
        (249, 115, 22), (16, 185, 129), (59, 130, 246),
        (168, 85, 247), (236, 72, 153), (20, 184, 166), (234, 88, 12),
    ])
    img = Image.new('RGB', (size, size), bg)
    d = ImageDraw.Draw(img)
    initials = ''.join(w[0] for w in name.split()[:2]).upper() or 'U'
    font = _load_font(110)
    bbox = d.textbbox((0, 0), initials, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
        initials, fill=(255, 255, 255), font=font,
    )
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=80)
    return ContentFile(buf.getvalue())


def _fetch_remote_image(keyword):
    try:
        resp = requests.get(
            f'https://loremflickr.com/640/640/{keyword}',
            timeout=8, headers={'User-Agent': 'Mozilla/5.0'},
        )
        if resp.status_code == 200 and len(resp.content) > 5000:
            img = Image.open(io.BytesIO(resp.content)).convert('RGB')
            img = img.resize((640, 640), RESAMPLE)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            return ContentFile(buf.getvalue())
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Static catalog / marketing data
# ---------------------------------------------------------------------------

PRODUCTS = [
    ('Wireless Bluetooth Headphones', 'Over-ear noise-cancelling headphones with 30-hour battery life and deep bass.', 2999, 'electronics', 'SoundPulse', None),
    ('Smart Watch Pro', 'Fitness smartwatch with heart-rate monitor, GPS and AMOLED display.', 4999, 'electronics', 'FitPro', ['38 mm', '42 mm']),
    ('USB-C Hub 7-in-1', 'Multi-port adapter for laptops with HDMI, USB 3.0 and SD card reader.', 1499, 'electronics', 'PortHub', None),
    ('Wireless Mouse', 'Ergonomic silent-click wireless mouse with adjustable DPI.', 899, 'electronics', 'ClickMate', None),
    ('Bluetooth Speaker', 'Portable waterproof speaker with 12-hour playtime and 360° sound.', 1799, 'electronics', 'BoomBeat', None),
    ('Mechanical Keyboard', 'RGB backlit mechanical keyboard with hot-swappable switches.', 2499, 'electronics', 'TypeTitan', ['Red', 'Blue']),
    ('Noise-Cancelling Earbuds', 'True wireless earbuds with active noise cancellation.', 2499, 'electronics', 'SoundPulse', None),
    ('Cotton T-Shirt', 'Premium combed cotton regular-fit tee.', 799, 'fashion', 'Urban Wear', ['S', 'M', 'L', 'XL']),
    ('Denim Jacket', 'Classic blue denim jacket with a vintage wash.', 2499, 'fashion', 'DenimCo', ['M', 'L', 'XL']),
    ('Running Shoes', 'Lightweight cushioned running shoes with breathable mesh.', 3999, 'fashion', 'StrideX', ['UK 8', 'UK 9', 'UK 10', 'UK 11']),
    ('Leather Wallet', 'Genuine leather bifold wallet with RFID protection.', 1299, 'fashion', 'HideCraft', None),
    ('Sunglasses', 'UV-protection polarized sunglasses with a stylish frame.', 1999, 'fashion', 'PolarEdge', ['Black', 'Brown']),
    ('Backpack', 'Waterproof 40L travel backpack with laptop sleeve.', 1999, 'fashion', 'TrailPro', ['Black', 'Navy', 'Olive']),
    ('Silk Saree', 'Handwoven silk saree with a traditional zari border.', 3499, 'fashion', 'Vastra', None),
    ('Non-Stick Cookware Set', '5-piece non-stick cookware set with stay-cool handles.', 3499, 'home-kitchen', 'ChefMate', None),
    ('Bed Sheet Set', 'Cotton king-size bedsheet set with 4 pillow covers.', 1599, 'home-kitchen', 'CozyHome', ['King', 'Queen']),
    ('Table Lamp', 'LED desk lamp with adjustable brightness and warm light.', 999, 'home-kitchen', 'Lumen', ['Warm White', 'RGB']),
    ('LED Strip Lights', 'Smart RGB music-sync LED strips, 5 m, with app control.', 1299, 'home-kitchen', 'GlowMax', ['5 m', '10 m']),
    ('Air Fryer', '5.5L digital air fryer with 8 preset cooking modes.', 4999, 'home-kitchen', 'CrispAir', None),
    ('Mixer Grinder', '750W mixer grinder with 3 stainless steel jars.', 2999, 'home-kitchen', 'ChefMate', None),
    ('The Great Gatsby', 'F. Scott Fitzgerald classic novel, hardcover edition.', 399, 'books', 'Penguin', None),
    ('Python Programming', 'Complete guide to Python 3 for beginners and intermediates.', 599, 'books', 'TechPress', None),
    ('Atomic Habits', 'The power of tiny changes by James Clear.', 499, 'books', 'Random House', None),
    ('Rich Dad Poor Dad', 'Robert Kiyosaki personal finance classic.', 450, 'books', 'Plata', None),
    ('Face Moisturizer', 'Vitamin C face cream, 50 ml, for radiant skin.', 899, 'beauty', 'GlowUp', None),
    ('Perfume Gift Set', 'Designer fragrance collection in an elegant gift box.', 2499, 'beauty', 'Aroma', ['50 ml', '100 ml']),
    ('Lipstick Set', 'Matte lipstick collection of 6 vibrant shades.', 699, 'beauty', 'Rouge', None),
    ('Hair Dryer', 'Ionic hair dryer with 3 heat settings and cool shot.', 1599, 'beauty', 'StylePro', None),
    ('Yoga Mat', 'Premium non-slip exercise mat with carry strap.', 1199, 'sports', 'ZenFit', ['6 mm', '10 mm']),
    ('Dumbbell Set', 'Adjustable 10 kg pair of hex dumbbells.', 2999, 'sports', 'IronFlex', None),
    ('Cricket Bat', 'Grade-1 willow cricket bat with full cover.', 2499, 'sports', 'Slugger', None),
    ('Football', 'Size-5 FIFA-quality football with stitched panels.', 899, 'sports', 'Kicker', None),
    ('Board Game', 'Family strategy board game for 2-6 players.', 999, 'toys-games', 'PlayLab', None),
    ('Remote Control Car', 'High-speed RC off-road monster truck.', 1999, 'toys-games', 'TurboToys', None),
    ('Building Blocks Set', '500-piece creative building blocks kit.', 1499, 'toys-games', 'BuildBrick', None),
    ('Action Figure', 'Collectible articulated action figure.', 799, 'toys-games', 'HeroZone', None),
    ('Car Phone Mount', 'Universal dashboard phone holder with 360° rotation.', 499, 'automotive', 'DriveSmart', None),
    ('Air Freshener', 'Premium car air freshener, pack of 3.', 349, 'automotive', 'FreshDrive', None),
    ('Car Vacuum Cleaner', '12V handheld car vacuum with crevice nozzle.', 1999, 'automotive', 'CleanRide', None),
    ('Tyre Inflator', 'Digital tyre inflator with LED light and pressure gauge.', 1499, 'automotive', 'PumpPro', None),
]

DEAL_PRODUCTS = [
    'wireless-bluetooth-headphones', 'smart-watch-pro', 'denim-jacket', 'running-shoes',
    'backpack', 'air-fryer', 'led-strip-lights', 'perfume-gift-set',
    'dumbbell-set', 'remote-control-car', 'bluetooth-speaker', 'tyre-inflator',
]

CITIES = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Pune', 'Hyderabad', 'Kolkata', 'Jaipur']
ADDRESSES = [
    '12 MG Road, Andheri West', '45 Park Street', '88 Indiranagar 1st Stage',
    '22 Anna Salai', '310 FC Road, Shivajinagar', '5 Banjara Hills Road No 3',
    '77 Salt Lake Sector V', '19 Malviya Nagar Market',
]

BLOG_POST_SPECS = [
    ('Best budget headphones under ₹5,000 in 2026', Post.PostType.BUYING_GUIDE, 'Buying Guides', 'wireless-bluetooth-headphones', PostProduct.Role.FEATURED, 12, True),
    ('Smart Watch Pro: three months later', Post.PostType.REVIEW, 'Reviews', 'smart-watch-pro', PostProduct.Role.FEATURED, 9, False),
    ('Setting up a smart home office in 5 minutes', Post.PostType.TUTORIAL, 'Setup Tips', 'usb-c-hub-7-in-1', PostProduct.Role.RELATED, 7, False),
    ('Denim jacket vs. denim shirt: what to buy', Post.PostType.COMPARISON, 'Fashion', 'denim-jacket', PostProduct.Role.COMPARED, 5, False),
    ('Why everyone is obsessed with the air fryer', Post.PostType.ARTICLE, 'Kitchen', 'air-fryer', PostProduct.Role.RELATED, 4, False),
    ('Top 5 gadgets for fitness beginners', Post.PostType.GUIDE, 'Fitness', 'dumbbell-set', PostProduct.Role.RELATED, 3, False),
    ("This week's biggest deals — don't miss out", Post.PostType.DEAL, 'Deals', 'bluetooth-speaker', PostProduct.Role.FEATURED, 2, False),
    ('How to pick a running shoe that fits', Post.PostType.GUIDE, 'Fitness', 'running-shoes', PostProduct.Role.FEATURED, 1, False),
]

BLOG_TAGS = [
    'Buying Guides', 'Reviews', 'Setup Tips', 'Fashion', 'Kitchen',
    'Fitness', 'Deals', 'Gadgets', 'Smart Home', 'Office',
]

NEWS_ITEMS = [
    ('Big Billion Days is coming — save up to 60%', 'announcement',
     '<p>Get ready for our biggest sale of the year. Enjoy up to 60% off on electronics, '
     'fashion, and home essentials. Exclusive early access for registered members.</p>', True),
    ('New seller support center now live', 'news',
     '<p>We have opened a dedicated support center for our sellers. Get help with '
     'onboarding, listings, payments, and more — 24/7.</p>', False),
    ('Free shipping weekend: Aug 8 – Aug 10', 'event',
     '<p>Every order ships free this weekend, no minimum order value. Delivery within '
     '24 hours in select cities.</p>', False),
    ('We now ship to 750+ cities across India', 'news',
     '<p>Our logistics network has expanded. Track every order in real time from your '
     'profile page.</p>', False),
]

# Quick-generation presets. Individual --options always override the preset value.
QUICK_PRESETS = {
    'tiny': {
        'users': 2, 'products': 6, 'orders': 1, 'reviews': 1,
        'posts': 1, 'news': 1, 'subscribers': 3, 'seller_products': 3,
    },
    'small': {
        'users': 4, 'products': 12, 'orders': 3, 'reviews': 2,
        'posts': 3, 'news': 2, 'subscribers': 6, 'seller_products': 8,
    },
    'medium': {
        'users': 8, 'products': 24, 'orders': 6, 'reviews': 3,
        'posts': 5, 'news': 3, 'subscribers': 10, 'seller_products': 15,
    },
    'large': {
        'users': 12, 'products': 40, 'orders': 10, 'reviews': 4,
        'posts': 8, 'news': 4, 'subscribers': 15, 'seller_products': 25,
    },
    'full': {
        'users': 12, 'products': 40, 'orders': 12, 'reviews': 5,
        'posts': 8, 'news': 4, 'subscribers': 20, 'seller_products': 40,
    },
}


class Command(BaseCommand):
    help = 'Seed demo data for every feature of Shop-Seed, with category-matched images.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--preset',
            choices=list(QUICK_PRESETS),
            default='medium',
            help='Quick generation size. Individual options override this. '
                 '(tiny | small | medium | large | full)',
        )
        parser.add_argument('--users', type=int, default=None,
                            help='Number of customer users to create.')
        parser.add_argument('--products', type=int, default=None,
                            help='Number of products to create (max 40).')
        parser.add_argument('--orders', type=int, default=None,
                            help='Number of orders to create.')
        parser.add_argument('--reviews', type=int, default=None,
                            help='Approximate reviews per product.')
        parser.add_argument('--posts', type=int, default=None,
                            help='Number of blog posts to create (max 8).')
        parser.add_argument('--news', type=int, default=None,
                            help='Number of news items to create (max 4).')
        parser.add_argument('--subscribers', type=int, default=None,
                            help='Number of newsletter subscribers to create.')
        parser.add_argument('--seller-products', type=int, default=None,
                            help='Number of listings per seller to create.')

    def handle(self, *args, **options):
        self._image_cache = {}
        self._image_index = {}
        self.users = {}
        self.customers = []
        self.sellers = []
        self.sellers_by_username = {}
        self.categories_by_slug = {}
        self.products_by_slug = {}
        self.shipping_methods = []
        self.paid_combos = set()

        self.cfg = dict(QUICK_PRESETS[options['preset']])
        for key in ('users', 'products', 'orders', 'reviews', 'posts',
                    'news', 'subscribers', 'seller_products'):
            if options.get(key) is not None:
                self.cfg[key] = max(1, options[key])

        self.stdout.write(
            f'Seeding Shop-Seed database [{options["preset"]} preset]...'
        )

        self._create_groups()
        self._create_users()
        self._create_preferences()
        self._create_categories()
        self._create_products()
        self._create_deals()
        self._create_coupons()
        self._create_shipping_methods()
        self._create_orders()
        self._create_reviews()
        self._create_blog()
        self._create_news()
        self._create_newsletter()
        self._create_notifications()
        self._create_services()
        self._create_faq()
        self._create_stories()
        self._create_about()
        self._create_team()
        self._create_contact()
        self._create_documentation()

        self.stdout.write(self.style.SUCCESS(
            f'Database seeded successfully! '
            f'({Product.objects.count()} products, {Order.objects.count()} orders, '
            f'{ProductReview.objects.count()} reviews, {Post.objects.count()} posts)'
        ))

    # ------------------------------------------------------------------ images

    def _image_for_category(self, slug):
        if slug not in self._image_cache:
            images = []
            theme = CATEGORY_THEMES[slug]
            remote = _fetch_remote_image(theme['keyword'])
            if remote:
                images.append(remote)
            for _ in range(2 - len(images)):
                images.append(_generate_category_image(slug))
            self._image_cache[slug] = images
            self._image_index[slug] = 0
        images = self._image_cache[slug]
        self._image_index[slug] += 1
        index = (self._image_index[slug] - 1) % len(images)
        content = images[index]
        if not getattr(content, 'name', None):
            content.name = f'{slug}-{index}.jpg'
        content.name = f'{slug}-{index}-{random.randint(100, 999)}.jpg'
        return content

    def _attach_image(self, instance, field_name, slug, filename=None):
        try:
            content = self._image_for_category(slug)
        except Exception:
            content = _generate_avatar('X')
        if content:
            field = getattr(instance, field_name)
            field.save(filename or f'{instance.pk or 0}-{random.randint(100, 999)}.jpg', content)

    # ------------------------------------------------------------------- users

    def _create_groups(self):
        for name in ['customers', 'sellers', 'admins']:
            Group.objects.get_or_create(name=name)
        self.stdout.write('  Groups created')

    def _create_users(self):
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'is_superuser': True, 'is_staff': True,
                'first_name': 'Admin', 'last_name': 'User',
                'email': 'admin@shop-seed.com',
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
        admin.groups.add(Group.objects.get(name='admins'))
        self.users['admin'] = admin

        seller, _ = SellerProfile.objects.get_or_create(
            user=admin,
            defaults={
                'shop_name': 'Shop-Seed Official', 'phone': '+91-9876543210',
                'address': 'Mumbai, India', 'description': 'Official store of Shop-Seed.',
                'bank_account': '0000000000000000', 'account_holder_name': 'Admin User',
                'ifsc_code': 'HDFC0000000', 'bank_name': 'HDFC Bank',
                'is_verified': True,
            }
        )
        self._attach_image(seller, 'profile_picture', 'abstract', 'seller-admin.jpg')
        self.sellers_by_username['admin'] = seller

        test_users = [
            ('priya.sharma', 'Priya', 'Sharma'),
            ('rahul.verma', 'Rahul', 'Verma'),
            ('anjali.singh', 'Anjali', 'Singh'),
            ('vikram.patel', 'Vikram', 'Patel'),
            ('neha.gupta', 'Neha', 'Gupta'),
            ('arjun.nair', 'Arjun', 'Nair'),
            ('kavita.joshi', 'Kavita', 'Joshi'),
            ('rohit.kumar', 'Rohit', 'Kumar'),
            ('sneha.reddy', 'Sneha', 'Reddy'),
            ('amit.jain', 'Amit', 'Jain'),
            ('pooja.malhotra', 'Pooja', 'Malhotra'),
            ('karan.chopra', 'Karan', 'Chopra'),
        ]
        for uname, fn, ln in test_users[:self.cfg['users']]:
            u, created = User.objects.get_or_create(username=uname, defaults={
                'first_name': fn, 'last_name': ln, 'email': f'{uname}@example.com',
            })
            if created:
                u.set_password('test123')
                u.save()
            u.groups.add(Group.objects.get(name='customers'))
            profile, _ = CustomerProfile.objects.get_or_create(
                user=u,
                defaults={
                    'phone': f'+91-{random.randint(7000000000, 9999999999)}',
                    'address': 'Test Address',
                },
            )
            self._attach_image(profile, 'profile_picture', 'abstract', f'{uname}.jpg')
            self.users[uname] = u
            self.customers.append(profile)
        self.stdout.write(
            f'  {len(self.customers)}/{self.cfg["users"]} customer users ensured'
        )

        sellers_data = [
            ('fashion_hub', 'Fashion Hub', 'Delhi, India'),
            ('tech_store', 'Tech Store', 'Bangalore, India'),
            ('home_decor', 'Home Decor', 'Jaipur, India'),
        ]
        for uname, shop, addr in sellers_data:
            u, created = User.objects.get_or_create(username=uname, defaults={
                'first_name': shop, 'email': f'{uname}@example.com',
            })
            if created:
                u.set_password('test123')
                u.save()
            u.groups.add(Group.objects.get(name='sellers'))
            profile, _ = SellerProfile.objects.get_or_create(
                user=u,
                defaults={
                    'shop_name': shop, 'phone': f'+91-{random.randint(7000000000, 9999999999)}',
                    'address': addr, 'description': f'{shop} sells quality products on Shop-Seed.',
                    'bank_account': '0000000000000000', 'account_holder_name': shop,
                    'ifsc_code': 'HDFC0000000', 'bank_name': 'HDFC Bank',
                    'is_verified': True,
                }
            )
            self._attach_image(profile, 'profile_picture', 'abstract', f'{uname}.jpg')
            self.users[uname] = u
            self.sellers_by_username[uname] = profile
            self.sellers.append(profile)
        self.stdout.write(f'  {len(sellers_data)} seller users created')

    def _create_preferences(self):
        accents = [c[0] for c in UserPreference.ACCENT_CHOICES]
        fonts = [c[0] for c in UserPreference.FONT_CHOICES]
        langs = [c[0] for c in UserPreference.LANG_CHOICES]
        sizes = [c[0] for c in UserPreference.TEXT_SIZE_CHOICES]
        created = 0
        for user in User.objects.all():
            _, was_created = UserPreference.objects.get_or_create(
                user=user,
                defaults={
                    'theme': random.choice(['light', 'dark']),
                    'language': random.choice(langs),
                    'currency': random.choice(['USD', 'INR', 'EUR', 'GBP']),
                    'font_style': random.choice(fonts),
                    'accent': random.choice(accents),
                    'text_size': random.choice(sizes),
                },
            )
            created += int(was_created)
        self.stdout.write(f'  {created} user preferences created')

    def _create_categories(self):
        categories = [
            ('Electronics', 'electronics'), ('Fashion', 'fashion'),
            ('Home & Kitchen', 'home-kitchen'), ('Books', 'books'),
            ('Beauty', 'beauty'), ('Sports', 'sports'),
            ('Toys & Games', 'toys-games'), ('Automotive', 'automotive'),
        ]
        for name, slug in categories:
            cat, _ = Category.objects.get_or_create(name=name, slug=slug)
            self.categories_by_slug[slug] = cat
        self.stdout.write(f'  {len(categories)} categories created')

    # ---------------------------------------------------------------- products

    def _create_products(self):
        admin_seller = self.sellers_by_username['admin']
        created = 0
        for name, desc, price, cat_slug, brand, variants in PRODUCTS[:self.cfg['products']]:
            slug = slugify(name)[:50]
            product, was_created = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    'category': self.categories_by_slug[cat_slug],
                    'name': name, 'description': f'<p>{desc}</p>',
                    'price': price, 'available': True,
                    'brand': brand, 'seller': admin_seller,
                },
            )
            if was_created:
                self._attach_image(product, 'image', cat_slug, f'{slug}.jpg')
                for i in range(2):
                    ProductImage.objects.create(
                        product=product,
                        image=self._image_for_category(cat_slug),
                        alt_text=f'{name} gallery image {i + 1}',
                        sort_order=i + 1,
                    )
                if variants:
                    for vname in variants:
                        variant = ProductVariant.objects.create(
                            product=product, name=vname,
                            sku=f'{slug.upper()[:8]}-{random.randint(1000, 9999)}',
                            price=Decimal(str(price)), stock=random.randint(5, 60),
                            active=True,
                        )
                        if random.random() < 0.4:
                            VariantImage.objects.create(
                                variant=variant,
                                image=self._image_for_category(cat_slug),
                                sort_order=1,
                            )
                created += 1
            self.products_by_slug[slug] = product

        for i, seller in enumerate(self.sellers):
            listed = 0
            for j, (name, desc, price, cat_slug, brand, variants) in enumerate(PRODUCTS[:self.cfg['products']]):
                if listed >= self.cfg['seller_products']:
                    break
                if (i + j) % 4 != 0:
                    continue
                product = self.products_by_slug[slugify(name)[:50]]
                SellerProduct.objects.get_or_create(
                    seller=seller, product=product,
                    defaults={
                        'price': Decimal(str(int(price * random.uniform(0.92, 1.08)))),
                        'quantity': random.randint(10, 120),
                        'is_active_seller': True,
                    },
                )
                listed += 1
            self.stdout.write(f'    {seller.shop_name}: {listed} products listed')
        self.stdout.write(f'  {created} products created')

    def _create_deals(self):
        now = timezone.now()
        created = 0
        for slug in DEAL_PRODUCTS:
            product = self.products_by_slug.get(slug)
            if not product:
                continue
            _, was_created = Deal.objects.get_or_create(
                product=product,
                defaults={
                    'deal_price': round(float(product.price) * random.uniform(0.5, 0.85), -1),
                    'start_time': now - timedelta(days=1),
                    'end_time': now + timedelta(days=random.randint(5, 20)),
                },
            )
            created += int(was_created)
        self.stdout.write(f'  {created} deals created')

    def _create_coupons(self):
        now = timezone.now()
        coupons = [
            ('WELCOME20', 20, 30), ('SAVE15', 15, 15),
            ('FESTIVE25', 25, 45), ('FIRST10', 10, 7),
            ('BIGSALE', 30, 20), ('MEGA50', 50, 10), ('FREESHIP', 5, 12),
        ]
        for code, discount, days in coupons:
            Coupon.objects.get_or_create(
                code=code,
                defaults={
                    'discount': discount,
                    'valid_from': now - timedelta(days=1),
                    'valid_to': now + timedelta(days=days),
                    'active': True,
                }
            )
        self.stdout.write(f'  {len(coupons)} coupons created')

    # ---------------------------------------------------------------- shipping

    def _create_shipping_methods(self):
        methods = [
            ('Standard Delivery', 'Delivered in 5-7 business days.', Decimal('49.00'), '5-7 business days'),
            ('Express Delivery', 'Delivered in 2-3 business days.', Decimal('99.00'), '2-3 business days'),
            ('Free Delivery', 'Free delivery on orders above ₹999.', Decimal('0.00'), '5-7 business days'),
            ('Same Day Delivery', 'Delivered within 24 hours in metro cities.', Decimal('149.00'), 'Same day'),
        ]
        for name, desc, price, days in methods:
            method, _ = ShippingMethod.objects.get_or_create(
                name=name,
                defaults={'description': desc, 'price': price,
                          'estimated_delivery_days': days, 'is_active': True},
            )
            self.shipping_methods.append(method)
        self.stdout.write(f'  {len(methods)} shipping methods created')

    def _create_orders(self):
        if not self.customers or not self.products_by_slug:
            return
        products = list(self.products_by_slug.values())
        created = 0
        for i in range(min(self.cfg['orders'], len(self.customers))):
            profile = self.customers[i]
            user = profile.user
            order, _ = Order.objects.get_or_create(
                user=user,
                first_name=user.first_name, last_name=user.last_name,
                email=user.email,
                defaults={
                    'address': random.choice(ADDRESSES),
                    'postal_code': str(random.randint(100000, 999999)),
                    'city': random.choice(CITIES),
                },
            )
            method = random.choice(self.shipping_methods)
            order.shipping_cost = method.price
            order.shipping_method_name = method.name
            order.paid = random.choice([True, False])
            order.status = Order.Status.DELIVERED if order.paid else Order.Status.PENDING
            order.save()

            for _ in range(random.randint(1, 3)):
                product = random.choice(products)
                variant = product.active_variants.first()
                price = variant.effective_price if variant else product.current_price
                OrderItem.objects.get_or_create(
                    order=order, product=product,
                    defaults={
                        'variant': variant,
                        'variant_name': variant.name if variant else '',
                        'price': price,
                        'quantity': random.randint(1, 2),
                        'deal_applied': bool(
                            product.deals.filter(
                                start_time__lte=timezone.now(), end_time__gte=timezone.now()
                            ).exists()
                        ),
                    },
                )

            address, _ = ShippingAddress.objects.get_or_create(
                user=user,
                defaults={
                    'full_name': f'{user.first_name} {user.last_name}',
                    'address_line1': random.choice(ADDRESSES),
                    'address_line2': '', 'city': order.city,
                    'state': 'Maharashtra', 'postal_code': order.postal_code,
                    'country': 'India', 'phone': profile.phone, 'is_default': True,
                },
            )

            if order.paid:
                if not hasattr(order, 'payment'):
                    total = order.get_total_cost()
                    Payment.objects.create(
                        order=order, amount=total, currency='INR', status='captured',
                        razorpay_order_id=f'test_order_{order.id}',
                        razorpay_payment_id=f'test_pay_{order.id}',
                        razorpay_signature=f'sig_{order.id}',
                    )
                for item in order.items.all():
                    self.paid_combos.add((user.id, item.product_id))

                status = random.choice(['shipped', 'in_transit', 'delivered', 'delivered'])
                shipment, _ = Shipment.objects.get_or_create(
                    order=order,
                    defaults={
                        'shipping_address': address,
                        'shipping_method': method,
                        'tracking_number': f'SS{random.randint(10**9, 10**10 - 1)}',
                        'status': status,
                    },
                )
                if status in ('shipped', 'in_transit', 'delivered') and not shipment.shipped_at:
                    shipment.shipped_at = timezone.now() - timedelta(days=1)
                if status == 'delivered' and not shipment.delivered_at:
                    shipment.delivered_at = timezone.now()
                shipment.save()
            created += 1
        self.stdout.write(f'  {created} orders created')

    # ---------------------------------------------------------------- reviews

    def _create_reviews(self):
        users = [c.user for c in self.customers]
        products = list(self.products_by_slug.values())
        rpp = self.cfg['reviews']

        created_product_reviews = 0
        verified_user_ids = {uid for uid, _ in self.paid_combos}
        for product in random.sample(products, min(len(products), max(1, rpp * 3))):
            if not product.images.exists():
                continue
            candidates = list(verified_user_ids)
            if not candidates:
                break
            for uid in random.sample(candidates, min(2, len(candidates))):
                user = User.objects.filter(id=uid).first()
                if not user:
                    continue
                rating = random.randint(3, 5)
                pr, was_created = ProductReview.objects.get_or_create(
                    product=product, reviewer=user,
                    defaults={
                        'overall_rating': rating,
                        'performance': rating, 'value': max(1, rating - 1), 'quality': rating,
                        'recommendation_rating': random.randint(60, 95),
                        'pros': 'Solid build quality and a clean design.',
                        'cons': 'A slightly steep learning curve at first.',
                        'review_text': 'Verified purchase review generated from real demo orders.',
                        'status': ProductReview.Status.APPROVED,
                    },
                )
                if was_created:
                    created_product_reviews += 1
                    for voter in random.sample(users, min(2, len(users))):
                        pr.helpful_votes.add(voter)
                    if random.random() < 0.6:
                        ProductReviewImage.objects.create(
                            review=pr,
                            image=self._image_for_category(product.category.slug),
                        )

        target_review = ProductReview.objects.first()
        if target_review and not ReviewReport.objects.exists():
            ReviewReport.objects.create(
                review=target_review,
                reporter=random.choice(users),
                reason=ProductReview.ReportReason.INAPPROPRIATE,
                details='Suspected promotional content in the review.',
                status=ReviewReport.Status.PENDING,
            )
        self.stdout.write(
            f'  {created_product_reviews} product reviews created'
        )

    # -------------------------------------------------------------------- blog

    def _create_blog(self):
        for user in self.users.values():
            ensure_blog_profile(user)

        badges = [
            ('first_post', 'First Post', 'Published your first post', 'fa-pen-nib'),
            ('first_comment', 'First Comment', 'Joined the conversation', 'fa-comment'),
            ('popular_author', 'Popular Author', 'A post reached 20 likes', 'fa-fire'),
            ('top_commenter', 'Top Commenter', '10 helpful votes on your comments', 'fa-thumbs-up'),
        ]
        badge_objs = []
        for code, name, desc, icon in badges:
            badge, _ = Badge.objects.get_or_create(
                code=code, defaults={'name': name, 'description': desc, 'icon': icon},
            )
            badge_objs.append(badge)

        tags = []
        for name in BLOG_TAGS:
            tag, _ = BlogTag.objects.get_or_create(
                name=name, defaults={'slug': slugify(name)},
            )
            tags.append(tag)
        tags_by_name = {t.name: t for t in tags}

        customer_users = [c.user for c in self.customers]
        authors = (customer_users + [self.users['admin']])[:4]
        commenters = customer_users or authors
        now = timezone.now()

        posts = []
        for i, (title, ptype, tag_name, prod_slug, role, days_ago, pinned) in enumerate(
                BLOG_POST_SPECS[:self.cfg['posts']]):
            author = authors[i % len(authors)]
            product = self.products_by_slug.get(prod_slug)
            cat_slug = product.category.slug if product else 'abstract'
            post, was_created = Post.objects.get_or_create(
                title=title,
                defaults={
                    'author': author,
                    'slug': slugify(title)[:200],
                    'post_type': ptype,
                    'body': (
                        '<p>This is a demo post generated by the seed command. Replace this '
                        'copy with real editorial content.</p>'
                        '<h2>Why it matters</h2>'
                        '<p>The items below link to live catalogue products, so prices and '
                        'availability always stay current.</p>'
                        '<h2>Our take</h2>'
                        '<p>Shop what you need, read the details, and check the community '
                        'reviews before you buy.</p>'
                    ),
                    'excerpt': 'A quick look at products we shipped to our own desks.',
                    'status': Post.Status.PUBLISHED,
                    'publish_at': now - timedelta(days=days_ago),
                    'view_count': random.randint(50, 500),
                    'is_pinned': pinned,
                },
            )
            if was_created:
                self._attach_image(post, 'featured_image', cat_slug, f'post-{i}.jpg')
                post.tags.add(tags_by_name[tag_name])
                if product:
                    PostProduct.objects.get_or_create(
                        post=post, product=product, defaults={'role': role},
                    )
                for g in range(2):
                    BlogPostImage.objects.create(
                        post=post,
                        image=self._image_for_category(cat_slug),
                        caption=f'Gallery image {g + 1}',
                        order=g + 1,
                    )
            posts.append(post)

        authors_by_pk = {a.pk: a for a in authors}
        for i, post in enumerate(posts):
            commenter = commenters[i % len(commenters)]
            body = random.choice([
                'Really useful write-up — helped me decide what to buy. Thanks!',
                'Great breakdown. Bookmarked for later.',
                'Just what I was looking for, keep it up!',
            ])
            comment, _ = BlogComment.objects.get_or_create(
                post=post, author=commenter, body=body,
                defaults={'is_approved': True},
            )
            if random.random() < 0.5 and not comment.children.exists():
                replier = commenters[(i + 1) % len(commenters)]
                BlogComment.objects.get_or_create(
                    post=post, author=replier,
                    parent=comment,
                    body='Totally agree — I bought one after reading this.',
                )
            for voter in random.sample(commenters, min(2, len(commenters))):
                comment.helpful_votes.add(voter)

            for liker in random.sample(commenters, min(3, len(commenters))):
                if liker == post.author:
                    continue
                BlogLike.objects.get_or_create(user=liker, post=post)
                BlogNotification.objects.get_or_create(
                    recipient=post.author, actor=liker,
                    verb=BlogNotification.Verb.LIKE, content_type=ContentType.objects.get_for_model(Post),
                    object_id=post.pk,
                )

            BlogNotification.objects.get_or_create(
                recipient=post.author, actor=commenter,
                verb=BlogNotification.Verb.COMMENT,
                content_type=ContentType.objects.get_for_model(BlogComment),
                object_id=comment.pk,
            )
            for bookmarker in random.sample(commenters, min(2, len(commenters))):
                BlogBookmark.objects.get_or_create(user=bookmarker, post=post)
            for _ in range(4):
                viewer = random.choice(commenters)
                BlogPostView.objects.get_or_create(post=post, user=viewer,
                                                   ip_address=f'103.{random.randint(10, 90)}.{random.randint(10, 250)}.{random.randint(1, 254)}')

        num_follows = min(4, len(commenters), len(authors))
        for k in range(num_follows):
            follower = commenters[k]
            following = authors[(k * 2 + 1) % len(authors)]
            if follower != following:
                BlogFollow.objects.get_or_create(follower=follower, following=following)

        for user in commenters[:3]:
            profile = ensure_blog_profile(user)
            profile.award_badge('first_comment')
            profile.add_xp(random.randint(50, 300))

        BlogUserProfile.objects.filter(user__in=authors[:2]).update(xp=1500)
        for author in authors[:2]:
            ensure_blog_profile(author).award_badge('popular_author')

        if posts:
            post = posts[0]
            for user in commenters[:2]:
                BlogUserReaction.objects.get_or_create(
                    user=user, reaction=BlogUserReaction.Reaction.LOVE,
                    content_type=ContentType.objects.get_for_model(Post),
                    object_id=post.pk,
                )
            for actor in commenters[:2]:
                BlogActivityFeedItem.objects.get_or_create(
                    actor=actor, verb=BlogActivityFeedItem.Verb.LIKE, post=post,
                    defaults={'text': f'{actor.username} liked "{post.title}"'},
                )

            if not BlogPostReport.objects.exists():
                BlogPostReport.objects.create(
                    post=post, reporter=commenters[1] if len(commenters) > 1 else commenters[0],
                    reason=BlogPostReport.Reason.SPAM,
                    details='Possible promotional content in this post.',
                    status=BlogPostReport.Status.PENDING,
                )

        self.stdout.write(
            f'  {len(posts)} posts, {len(tags)} tags, {BlogComment.objects.count()} comments '
            f'created'
        )

    # -------------------------------------------------------------------- news

    def _create_news(self):
        author = self.users['admin']
        now = timezone.now()
        created = 0
        for index, (title, kind, body, pinned) in enumerate(NEWS_ITEMS[:self.cfg['news']]):
            _, was_created = NewsItem.objects.get_or_create(
                title=title,
                defaults={
                    'kind': kind, 'body': body, 'author': author,
                    'is_published': True, 'is_pinned': pinned,
                    'publish_at': now - timedelta(days=index),
                },
            )
            created += int(was_created)
        self.stdout.write(f'  {created} news items created')

    # -------------------------------------------------------------- newsletter

    def _create_newsletter(self):
        emails = [
            'priya@example.com', 'rahul@example.com', 'anjali@example.com',
            'vikram@example.com', 'neha@example.com', 'arjun@example.com',
            'kavita@example.com', 'rohit@example.com', 'fashion_hub@example.com',
            'tech_store@example.com', 'home_decor@example.com', 'sneha@example.com',
            'amit@example.com', 'pooja@example.com', 'karan@example.com',
            'divya@example.com', 'manish@example.com', 'reena@example.com',
            'sunil@example.com', 'farah@example.com',
        ]
        created = 0
        for email in emails[:self.cfg['subscribers']]:
            _, was_created = Subscriber.objects.get_or_create(
                email=email, defaults={'is_active': True},
            )
            created += int(was_created)
        self.stdout.write(f'  {created} newsletter subscribers created')

    # ------------------------------------------------------------ notifications

    def _create_notifications(self):
        sample = [
            ('order', AppNotification.Category.ORDER, 'Order confirmed!',
             'Your order has been placed successfully.', '/orders/'),
            ('payment', AppNotification.Category.PAYMENT, 'Payment received',
             'Your payment of the order was successful.', '/orders/'),
            ('shipping', AppNotification.Category.SHIPPING, 'Your order is on the way',
             'Track your shipment for live updates.', '/orders/'),
            ('deal', AppNotification.Category.DEAL, 'New deals just dropped',
             'Save up to 60% on electronics this week.', '/shop/'),
            ('review', AppNotification.Category.REVIEW, 'Share your experience',
             'You recently purchased a product, please leave a review.', '/account/'),
            ('account', AppNotification.Category.ACCOUNT, 'Security update',
             'Please update your password to keep your account safe.', '/account/'),
        ]
        roles = ['customer', 'seller', 'admin']
        created = 0
        for i, (icon, category, title, message, link) in enumerate(sample):
            recipient = self.customers[i % len(self.customers)].user if self.customers else None
            if recipient and AppNotification.objects.filter(recipient=recipient, title=title).exists():
                continue
            AppNotification.objects.create(
                recipient=recipient, role=roles[i % 3], category=category,
                title=title, message=message, link=link, icon=icon,
                is_read=random.random() < 0.4,
            )
            created += 1
        self.stdout.write(f'  {created} notifications created')

        created_prefs = 0
        for user in User.objects.all():
            _, was_created = NotificationPreference.objects.get_or_create(user=user)
            created_prefs += int(was_created)
        self.stdout.write(f'  {created_prefs} notification preferences created')

    # ------------------------------------------------------------ content pages

    def _create_services(self):
        services = [
            ('Free Shipping', 'Free delivery on orders above ₹999.',
             '<p>Enjoy free standard shipping on all orders above ₹999 with no minimum '
             'purchase limit.</p>'),
            ('Easy Returns', '30-day hassle-free return policy.',
             '<p>Changed your mind? Return any eligible product within 30 days for a full '
             'refund, no questions asked.</p>'),
            ('24/7 Support', 'Round the clock customer care.',
             '<p>Our support team is available 24/7 via chat, email, and phone.</p>'),
            ('Gift Wrapping', 'Premium gift wrapping service.',
             '<p>Make every order special with our premium gift wrapping and personalised '
             'message cards.</p>'),
        ]
        created = 0
        for title, desc, details in services:
            service, was_created = Service.objects.get_or_create(
                title=title, description=desc,
                defaults={'details': details},
            )
            if was_created:
                self._attach_image(service, 'image', 'abstract', f'service-{slugify(title)}.jpg')
                created += 1
        self.stdout.write(f'  {len(services)} services created')

    def _create_faq(self):
        faqs = [
            ('How do I track my order?', 'You can track your order from the Orders section in your account profile.'),
            ('What is the return policy?', 'We offer 30-day easy returns on all products with free pickup.'),
            ('How long does delivery take?', 'Standard delivery takes 3-5 business days. Express delivery is 1-2 days.'),
            ('Is my payment secure?', 'Yes, we use bank-grade encryption for all transactions.'),
            ('Can I cancel my order?', 'Orders can be cancelled within 24 hours of placing them.'),
            ('How do I become a seller?', 'Create a seller account from the seller section and verify your documents.'),
        ]
        for q, a in faqs:
            FAQ.objects.get_or_create(question=q, defaults={'answer': a})
        self.stdout.write(f'  {len(faqs)} FAQs created')

    def _create_stories(self):
        stories = [
            ('Our Journey', '<p>Shop-Seed started with a vision to make quality products '
                            'accessible to everyone.</p>'),
            ('Sustainability Pledge', '<p>We are committed to sustainable packaging and '
                                      'eco-friendly practices.</p>'),
            ('Inside our warehouses', '<p>A peek into how we pack and ship thousands of '
                                      'orders every single day.</p>'),
        ]
        for title, desc in stories:
            story, was_created = Story.objects.get_or_create(
                title=title, defaults={'description': desc},
            )
            if was_created:
                self._attach_image(story, 'image', 'abstract', f'story-{slugify(title)}.jpg')
        self.stdout.write(f'  {len(stories)} stories created')

    def _create_about(self):
        section, was_created = AboutSection.objects.get_or_create(
            title='About Shop-Seed',
            defaults={'content': 'Shop-Seed is India\'s fastest growing e-commerce platform. '
                                 'We connect millions of buyers with thousands of sellers across '
                                 'the country, offering everything from electronics to fashion.'},
        )
        if was_created:
            self._attach_image(section, 'image', 'abstract', 'about.jpg')
        self.stdout.write('  About section created')

    def _create_team(self):
        members = [
            ('Rajesh Kumar', 'CEO & Founder', 'Built Shop-Seed from a garage startup into a national marketplace.'),
            ('Sneha Patel', 'CTO', 'Leads engineering and drives our technology roadmap.'),
            ('Amit Singh', 'Head of Operations', 'Keeps 750+ cities humming with reliable deliveries.'),
            ('Priya Mehta', 'Marketing Director', 'Tells the Shop-Seed story to millions of shoppers.'),
        ]
        for name, role, bio in members:
            member, was_created = TeamMember.objects.get_or_create(
                name=name, role=role, defaults={'bio': bio},
            )
            if was_created:
                member.photo.save(
                    f'team-{slugify(name)}.jpg',
                    _generate_avatar(name),
                )
        self.stdout.write(f'  {len(members)} team members created')

    def _create_contact(self):
        ContactMessage.objects.get_or_create(
            name='Test User', email='test@example.com',
            subject='Test Message', defaults={'message': 'This is a test contact message for seeding.'},
        )
        self.stdout.write('  Contact messages created')

    def _create_documentation(self):
        docs = [
            ('Getting Started', 'getting-started', '📘', 'Learn how to navigate Shop-Seed and place your first order.'),
            ('Seller Guide', 'seller-guide', '🛠️', 'Complete guide for sellers to list and manage products.'),
            ('Payment Methods', 'payment-methods', '💳', 'Information about accepted payment methods and security.'),
            ('Shipping & Returns', 'shipping-and-returns', '🚚', 'Everything you need to know about delivery and returns.'),
        ]
        for title, slug, icon, content in docs:
            doc, was_created = DocumentationSection.objects.get_or_create(
                title=title, defaults={'slug': slug, 'icon': icon, 'content': content},
            )
            if was_created:
                self._attach_image(doc, 'image', 'abstract', f'doc-{slug}.jpg')
        self.stdout.write(f'  {len(docs)} documentation sections created')
