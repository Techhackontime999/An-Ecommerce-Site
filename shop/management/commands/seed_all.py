import random
import io
import random
from decimal import Decimal
from datetime import timedelta
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.conf import settings
from shop.models import Category, Product
from accounts.models import SellerProfile, CustomerProfile
from deals.models import Deal
from coupons.models import Coupon
from reviews.models import Review
from order.models import Order, OrderItem
from payments.models import Payment
from services.models import Service
from faq.models import FAQ, Story
from about.models import AboutSection, TeamMember
from contact.models import ContactMessage
from documentation.models import DocumentationSection


def _generate_placeholder_image(name):
    try:
        from PIL import Image, ImageDraw, ImageFont
        size = 400
        img = Image.new('RGB', (size, size), (
            random.randint(30, 70), random.randint(30, 70), random.randint(30, 70)
        ))
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), name[:2].upper(), font_size=80)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((size - tw) / 2, (size - th) / 2 - 20), name[:2].upper(),
                  fill=(249, 115, 22), font_size=80)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=70)
        return ContentFile(buf.getvalue())
    except ImportError:
        return None


class Command(BaseCommand):
    help = 'Seed complete test data for Shop-Seed e-commerce platform'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Shop-Seed database...')

        self._create_groups()
        self._create_users()
        self._create_categories()
        self._create_products()
        self._create_deals()
        self._create_coupons()
        self._create_reviews()
        self._create_orders()
        self._create_services()
        self._create_faq()
        self._create_stories()
        self._create_about()
        self._create_team()
        self._create_contact()
        self._create_documentation()

        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))

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
        SellerProfile.objects.get_or_create(
            user=admin,
            defaults={
                'shop_name': 'Shop-Seed Official', 'phone': '+91-9876543210',
                'address': 'Mumbai, India',
            }
        )
        self.stdout.write('  Admin user created')

        test_users = [
            ('priya.sharma', 'Priya', 'Sharma'),
            ('rahul.verma', 'Rahul', 'Verma'),
            ('anjali.singh', 'Anjali', 'Singh'),
            ('vikram.patel', 'Vikram', 'Patel'),
            ('neha.gupta', 'Neha', 'Gupta'),
            ('arjun.nair', 'Arjun', 'Nair'),
            ('kavita.joshi', 'Kavita', 'Joshi'),
            ('rohit.kumar', 'Rohit', 'Kumar'),
        ]
        for uname, fn, ln in test_users:
            u, created = User.objects.get_or_create(username=uname, defaults={
                'first_name': fn, 'last_name': ln, 'email': f'{uname}@example.com',
            })
            if created:
                u.set_password('test123')
                u.save()
            u.groups.add(Group.objects.get(name='customers'))
            CustomerProfile.objects.get_or_create(
                user=u,
                defaults={'phone': f'+91-{random.randint(7000000000, 9999999999)}', 'address': 'Test Address'},
            )
        self.stdout.write(f'  {len(test_users)} customer users created')

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
            SellerProfile.objects.get_or_create(
                user=u,
                defaults={
                    'shop_name': shop, 'phone': f'+91-{random.randint(7000000000, 9999999999)}',
                    'address': addr, 'is_verified': True,
                }
            )
        self.stdout.write(f'  {len(sellers_data)} seller users created')

    def _create_categories(self):
        categories = [
            ('Electronics', 'electronics'), ('Fashion', 'fashion'),
            ('Home & Kitchen', 'home-kitchen'), ('Books', 'books'),
            ('Beauty', 'beauty'), ('Sports', 'sports'),
            ('Toys & Games', 'toys-games'), ('Automotive', 'automotive'),
        ]
        for name, slug in categories:
            Category.objects.get_or_create(name=name, slug=slug)
        self.stdout.write(f'  {len(categories)} categories created')

    def _create_products(self):
        admin = User.objects.filter(username='admin').first()
        seller = SellerProfile.objects.filter(user=admin).first()
        categories = list(Category.objects.all())
        if not categories:
            return

        product_data = [
            ('Wireless Bluetooth Headphones', 'Premium noise-cancelling headphones with 30hr battery', 2999, 'electronics', True),
            ('Smart Watch Pro', 'Fitness tracker with heart rate monitor', 4999, 'electronics', True),
            ('USB-C Hub 7-in-1', 'Multi-port adapter for laptops', 1499, 'electronics', False),
            ('Cotton T-Shirt', 'Premium cotton regular fit tee', 799, 'fashion', False),
            ('Denim Jacket', 'Classic blue denim jacket', 2499, 'fashion', True),
            ('Running Shoes', 'Lightweight cushioned running shoes', 3999, 'fashion', True),
            ('Leather Wallet', 'Genuine leather bifold wallet', 1299, 'fashion', False),
            ('Sunglasses', 'UV protection polarized sunglasses', 1999, 'fashion', False),
            ('Non-Stick Cookware Set', '5-piece kitchen cookware set', 3499, 'home-kitchen', True),
            ('Bed Sheet Set', 'Cotton king-size bedsheet with 4 pillow covers', 1599, 'home-kitchen', False),
            ('Table Lamp', 'LED desk lamp with adjustable brightness', 999, 'home-kitchen', False),
            ('The Great Gatsby', 'F. Scott Fitzgerald classic novel', 399, 'books', False),
            ('Python Programming', 'Complete guide to Python 3', 599, 'books', False),
            ('Face Moisturizer', 'Vitamin C face cream 50ml', 899, 'beauty', False),
            ('Perfume Gift Set', 'Designer fragrance collection', 2499, 'beauty', True),
            ('Yoga Mat', 'Premium non-slip exercise mat', 1199, 'sports', False),
            ('Dumbbell Set', 'Adjustable 10kg pair dumbbells', 2999, 'sports', True),
            ('Board Game', 'Family strategy board game', 999, 'toys-games', False),
            ('Remote Control Car', 'High-speed RC off-road car', 1999, 'toys-games', True),
            ('Car Phone Mount', 'Universal dashboard phone holder', 499, 'automotive', False),
            ('Air Freshener', 'Premium car air freshener 3-pack', 349, 'automotive', False),
            ('LED Strip Lights', 'Smart RGB music sync LED strips 5m', 1299, 'home-kitchen', True),
            ('Wireless Mouse', 'Ergonomic silent click mouse', 899, 'electronics', False),
            ('Backpack', 'Waterproof 40L travel backpack', 1999, 'fashion', True),
        ]

        count = 0
        for name, desc, price, cat_slug, has_deal in product_data:
            cat = categories[random.randint(0, len(categories)-1)]
            slug = name.lower().replace(' ', '-').replace('&', 'and')[:50]
            if not Product.objects.filter(slug=slug).exists():
                product = Product.objects.create(
                    category=cat, name=name, slug=slug, description=desc,
                    price=price, available=True, seller=seller,
                    brand=random.choice(['Premium', 'Elite', 'Urban', 'Classic', 'Modern'])
                )
                img_content = _generate_placeholder_image(name)
                if img_content:
                    product.image.save(f'{slug}.jpg', img_content)
                count += 1
        self.stdout.write(f'  {count} products created')

    def _create_deals(self):
        products = list(Product.objects.all()[:8])
        now = timezone.now()
        for p in products:
            deal_price = round(float(p.price) * random.uniform(0.5, 0.85), -1)
            Deal.objects.get_or_create(
                product=p,
                defaults={
                    'deal_price': deal_price,
                    'start_time': now - timedelta(days=1),
                    'end_time': now + timedelta(days=random.randint(5, 20)),
                }
            )
        self.stdout.write(f'  {len(products)} deals created')

    def _create_coupons(self):
        now = timezone.now()
        coupons = [
            ('WELCOME20', 20, 30), ('SAVE15', 15, 15),
            ('FESTIVE25', 25, 45), ('FIRST10', 10, 7),
            ('BIGSALE', 30, 20),
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

    def _create_reviews(self):
        users = list(CustomerProfile.objects.all())
        products = list(Product.objects.all())
        comments = [
            'Amazing product! Highly recommend.', 'Good quality for the price.',
            'Fast delivery. Product as described.', 'Decent but could be better.',
            'Exceeded my expectations!', 'Not what I expected, but okay.',
            'Perfect! Will buy again.', 'Great value for money.',
            'Loved it! 5 stars.', 'Average quality overall.',
        ]
        created = 0
        for product in products[:15]:
            for user in random.sample(users, min(3, len(users))):
                if not Review.objects.filter(product=product, user=user.user).exists():
                    Review.objects.create(
                        product=product, user=user.user,
                        rating=random.randint(3, 5),
                        comment=random.choice(comments)
                    )
                    created += 1
        self.stdout.write(f'  {created} reviews created')

    def _create_orders(self):
        users = list(CustomerProfile.objects.all())
        products = list(Product.objects.all())
        if not users or not products:
            return

        created = 0
        for i in range(min(8, len(users))):
            user = users[i]
            order = Order.objects.create(
                user=user.user, first_name=user.user.first_name or 'Test',
                last_name=user.user.last_name or 'User',
                email=user.user.email, address=user.address or 'Test Address',
                postal_code=str(random.randint(100000, 999999)),
                city=random.choice(['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Pune']),
                paid=random.choice([True, False])
            )
            for _ in range(random.randint(1, 3)):
                product = random.choice(products)
                OrderItem.objects.create(
                    order=order, product=product,
                    price=product.current_price, quantity=random.randint(1, 2)
                )
            if order.paid:
                total = sum(item.get_cost() for item in order.items.all())
                Payment.objects.create(
                    order=order, amount=total,
                    currency='INR', status='captured',
                    razorpay_order_id=f'test_order_{order.id}',
                    razorpay_payment_id=f'test_pay_{order.id}'
                )
            created += 1
        self.stdout.write(f'  {created} orders created')

    def _create_services(self):
        services = [
            ('Free Shipping', 'Free delivery on orders above $49', 'shipping'),
            ('Easy Returns', '30-day hassle-free return policy', 'returns'),
            ('24/7 Support', 'Round the clock customer care', 'support'),
            ('Gift Wrapping', 'Premium gift wrapping service', 'gift'),
        ]
        for title, desc, _ in services:
            Service.objects.get_or_create(title=title, description=desc, details=desc)
        self.stdout.write(f'  {len(services)} services created')

    def _create_faq(self):
        faqs = [
            ('How do I track my order?', 'You can track your order from the Orders section in your account profile.'),
            ('What is the return policy?', 'We offer 30-day easy returns on all products with free pickup.'),
            ('How long does delivery take?', 'Standard delivery takes 3-5 business days. Express delivery is 1-2 days.'),
            ('Is my payment secure?', 'Yes, we use bank-grade encryption for all transactions.'),
            ('Can I cancel my order?', 'Orders can be cancelled within 24 hours of placing them.'),
        ]
        for q, a in faqs:
            FAQ.objects.get_or_create(question=q, defaults={'answer': a})
        self.stdout.write(f'  {len(faqs)} FAQs created')

    def _create_stories(self):
        stories = [
            ('Our Journey', 'Shop-Seed started with a vision to make quality products accessible to everyone.'),
            ('Sustainability Pledge', 'We are committed to sustainable packaging and eco-friendly practices.'),
        ]
        for title, desc in stories:
            Story.objects.get_or_create(title=title, description=desc)
        self.stdout.write(f'  {len(stories)} stories created')

    def _create_about(self):
        AboutSection.objects.get_or_create(
            title='About Shop-Seed',
            defaults={'content': 'Shop-Seed is India\'s fastest growing e-commerce platform. We connect millions of buyers with thousands of sellers across the country, offering everything from electronics to fashion.'}
        )
        self.stdout.write('  About section created')

    def _create_team(self):
        members = [
            ('Rajesh Kumar', 'CEO & Founder'), ('Sneha Patel', 'CTO'),
            ('Amit Singh', 'Head of Operations'), ('Priya Mehta', 'Marketing Director'),
        ]
        for name, role in members:
            TeamMember.objects.get_or_create(name=name, role=role, defaults={'bio': f'{role} at Shop-Seed with years of experience.'})
        self.stdout.write(f'  {len(members)} team members created')

    def _create_contact(self):
        ContactMessage.objects.get_or_create(
            name='Test User', email='test@example.com',
            subject='Test Message', defaults={'message': 'This is a test contact message for seeding.'}
        )
        self.stdout.write('  Contact messages created')

    def _create_documentation(self):
        docs = [
            ('Getting Started', 'getting-started', 'Learn how to navigate Shop-Seed and place your first order.'),
            ('Seller Guide', 'seller-guide', 'Complete guide for sellers to list and manage products.'),
            ('Payment Methods', 'payment-methods', 'Information about accepted payment methods and security.'),
        ]
        for title, slug, content in docs:
            DocumentationSection.objects.get_or_create(title=title, slug=slug, defaults={'content': content})
        self.stdout.write(f'  {len(docs)} documentation sections created')
