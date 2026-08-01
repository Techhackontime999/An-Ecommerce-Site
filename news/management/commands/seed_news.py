from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import NewsItem

SAMPLE_ITEMS = [
    {
        'kind': 'announcement',
        'title': 'Big Billion Days is coming — save up to 60%',
        'body': (
            '<p>Get ready for our biggest sale of the year. Enjoy up to 60% off on '
            'electronics, fashion, and home essentials. Exclusive early access for '
            'registered members.</p>'
        ),
        'is_pinned': True,
    },
    {
        'kind': 'news',
        'title': 'New seller support center now live',
        'body': (
            '<p>We have opened a dedicated support center for our sellers. Get help '
            'with onboarding, listings, payments, and more — 24/7.</p>'
        ),
    },
    {
        'kind': 'event',
        'title': 'Free shipping weekend: Aug 8 – Aug 10',
        'body': (
            '<p>Every order ships free this weekend, no minimum order value. Delivery '
            'within 24 hours in select cities.</p>'
        ),
    },
    {
        'kind': 'news',
        'title': 'We now ship to 750+ cities across India',
        'body': (
            '<p>Our logistics network has expanded. Track every order in real time '
            'from your profile page.</p>'
        ),
    },
]


class Command(BaseCommand):
    help = 'Seed sample announcements/news/events for the news ticker.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='admin',
            help='Author username for the seeded items (must exist).',
        )

    def handle(self, *args, **options):
        username = options['username']
        author = User.objects.filter(username=username).first()
        if author is None:
            self.stderr.write(
                self.style.ERROR(
                    f'User "{username}" not found. Create a superuser first '
                    '(python manage.py createsuperuser) and pass --username.'
                )
            )
            return

        now = timezone.now()
        created = 0
        for index, data in enumerate(SAMPLE_ITEMS):
            if NewsItem.objects.filter(title=data['title']).exists():
                continue
            NewsItem.objects.create(
                title=data['title'],
                kind=data['kind'],
                body=data['body'],
                author=author,
                is_published=True,
                is_pinned=data.get('is_pinned', False),
                publish_at=now - timedelta(days=index),
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f'Seeded {created} news item(s) for "{username}".'))
