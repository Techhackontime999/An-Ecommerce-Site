from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import SellerProfile
from shop.models import Category, Product

from reviews.models import ProductReview

from ...models import (
    ActivityFeedItem,
    Bookmark,
    Comment,
    Follow,
    Like,
    Notification,
    Post,
    PostProduct,
    PostReport,
    PostView,
    Tag,
    ensure_profile,
)


class Command(BaseCommand):
    help = 'Seeds the blog + product review module with demo content linked to real catalog data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Remove existing blog/review demo data before seeding.',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing blog/review demo data...'))
            for model in (
                ActivityFeedItem,
                PostReport,
                PostView,
                Notification,
                Follow,
                Like,
                Bookmark,
                Comment,
                PostProduct,
                ProductReview,
                Post,
                Tag,
            ):
                model.objects.all().delete()

        users = self._users()
        tags = self._tags()
        products = self._products()

        posts = self._posts(users, tags, products)
        self._engagement(users, posts)
        self._reviews(users, products)

        self.stdout.write(self.style.SUCCESS(
            f'Done. {len(posts)} posts, {len(tags)} tags, '
            f'{len(products)} linked products, {ProductReview.objects.count()} product reviews.'
        ))

    def _unique_slug(self, model, base):
        candidate = slugify(base)[:200] or 'item'
        original = candidate
        counter = 1
        while model.objects.filter(slug=candidate).exists():
            candidate = f'{original}-{counter}'
            counter += 1
        return candidate

    def _users(self):
        demo = [
            ('aria_author', 'Aria', 'Chen'),
            ('drew_writer', 'Drew', 'Patel'),
            ('mira_buyer', 'Mira', 'Sharma'),
            ('leo_reader', 'Leo', 'Martinez'),
        ]
        created = []
        for username, first, last in demo:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last},
            )
            if not user.email:
                user.email = f'{username}@shopseed.example'
                user.save()
            ensure_profile(user)
            created.append(user)
        return created

    def _tags(self):
        names = [
            'Gadgets', 'Audio', 'Smart Home', 'Kitchen', 'Gaming',
            'Deals', 'Buying Guides', 'Reviews', 'Setup Tips', 'Office',
        ]
        tags = []
        for name in names:
            tag, _ = Tag.objects.get_or_create(
                name=name,
                defaults={'slug': self._unique_slug(Tag, name)},
            )
            tags.append(tag)
        return tags

    def _products(self):
        category, _ = Category.objects.get_or_create(
            slug='demo',
            defaults={'name': 'Demo Collection'},
        )
        sellers = list(SellerProfile.objects.all())
        seed = [
            ('Aurora Desk Lamp', 'A dimmable desk lamp with a warm reading mode.'),
            ('Nimbus Headphones', 'Wireless over-ear headphones with 30h battery.'),
            ('Ember Kettle', 'Temperature-controlled electric kettle for pour-over.'),
            ('Forge Controller', 'Ergonomic wireless game controller.'),
            ('Slate Backpack', 'Water-resistant 20L urban backpack with laptop sleeve.'),
            ('Halo Speaker', 'Compact 360° smart speaker with rich bass.'),
        ]
        products = []
        for name, description in seed:
            product, _ = Product.objects.get_or_create(
                category=category,
                name=name,
                defaults={
                    'slug': self._unique_slug(Product, name),
                    'description': f'<p>{description}</p>',
                    'price': Decimal('49.99'),
                    'seller': sellers[0] if sellers else None,
                },
            )
            products.append(product)
        return products

    def _posts(self, users, tags, products):
        author = users[0]
        writer = users[1]
        now = timezone.now()
        tag_names = [t.name for t in tags]
        specs = [
            {
                'title': 'How we picked the best desk lamps of 2026',
                'post_type': Post.PostType.BUYING_GUIDE,
                'author': author,
                'tag': 'Buying Guides',
                'product': products[0],
                'role': PostProduct.Role.FEATURED,
                'days_ago': 10,
                'pinned': True,
            },
            {
                'title': 'Nimbus Headphones — three months later',
                'post_type': Post.PostType.REVIEW,
                'author': author,
                'tag': 'Reviews',
                'product': products[1],
                'role': PostProduct.Role.FEATURED,
                'days_ago': 6,
            },
            {
                'title': 'The 5-minute smart home starter setup',
                'post_type': Post.PostType.TUTORIAL,
                'author': writer,
                'tag': 'Setup Tips',
                'product': products[4],
                'role': PostProduct.Role.RELATED,
                'days_ago': 3,
            },
            {
                'title': 'Ember vs. classic kettles: is precision worth it?',
                'post_type': Post.PostType.COMPARISON,
                'author': writer,
                'tag': 'Kitchen',
                'product': products[2],
                'role': PostProduct.Role.COMPARED,
                'days_ago': 2,
            },
        ]
        posts = []
        for spec in specs:
            post, created = Post.objects.get_or_create(
                title=spec['title'],
                defaults={
                    'author': spec['author'],
                    'slug': self._unique_slug(Post, spec['title']),
                    'post_type': spec['post_type'],
                    'body': (
                        '<p>This is a demo post generated by the seed command. '
                        'Replace this copy with real editorial content.</p>'
                        '<h2>Why it matters</h2>'
                        '<p>The items below link to live catalogue products, so prices and '
                        'availability always stay current.</p>'
                        '<h2>Our take</h2>'
                        '<p>Shop what you need, read the details, and check the community '
                        'reviews before you buy.</p>'
                    ),
                    'excerpt': 'A quick look at a product we shipped to our own desks.',
                    'status': Post.Status.PUBLISHED,
                    'publish_at': now - timezone.timedelta(days=spec['days_ago']),
                    'view_count': 40 + spec['days_ago'] * 15,
                    'is_pinned': spec.get('pinned', False),
                },
            )
            if created:
                post.tags.add(tags[tag_names.index(spec['tag'])])
                if spec['product']:
                    PostProduct.objects.get_or_create(
                        post=post,
                        product=spec['product'],
                        defaults={'role': spec['role']},
                    )
            posts.append(post)
        return posts

    def _engagement(self, users, posts):
        reader = users[2]
        follower = users[3]
        now = timezone.now()
        for i, post in enumerate(posts):
            commenter = users[2 if i % 2 == 0 else 3]
            comment, _ = Comment.objects.get_or_create(
                post=post,
                author=commenter,
                defaults={
                    'body': 'Really useful write-up — helped me decide what to buy. Thanks!',
                    'created': now - timezone.timedelta(days=i, hours=3),
                },
            )
            Like.objects.get_or_create(user=reader, post=post)
            if post.author != follower:
                Follow.objects.get_or_create(follower=follower, following=post.author)
            PostView.objects.get_or_create(post=post, user=reader)

        post = posts[0]
        notification = Notification.objects.filter(
            recipient=post.author, actor=reader, verb=Notification.Verb.COMMENT,
        ).first()
        if not notification:
            Notification.objects.create(
                recipient=post.author,
                actor=reader,
                verb=Notification.Verb.COMMENT,
                target=Comment.objects.filter(post=post).first(),
            )

    def _reviews(self, users, products):
        reviewer = users[2]
        verified = users[3]
        specs = [
            (products[0], reviewer, 4, 75),
            (products[1], reviewer, 5, 90),
            (products[2], verified, 3, 55),
        ]
        for product, user, rating, recommendation in specs:
            ProductReview.objects.get_or_create(
                product=product,
                reviewer=user,
                defaults={
                    'overall_rating': rating,
                    'performance': rating,
                    'value': max(1, rating - 1),
                    'quality': rating,
                    'recommendation_rating': recommendation,
                    'pros': 'Solid build quality and a clean design.',
                    'cons': 'A slightly steep learning curve at first.',
                    'review_text': (
                        'Demo review generated by the seed command. Replace this with '
                        'real feedback from someone who actually used the product.'
                    ),
                    'status': ProductReview.Status.APPROVED,
                },
            )
