from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from ckeditor.fields import RichTextField


class NewsItem(models.Model):
    class Kind(models.TextChoices):
        ANNOUNCEMENT = 'announcement', 'Announcement'
        NEWS = 'news', 'News'
        EVENT = 'event', 'Event'

    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True)
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.ANNOUNCEMENT,
        db_index=True,
    )
    body = RichTextField()
    excerpt = models.CharField(
        max_length=240,
        blank=True,
        help_text='Short teaser shown in the ticker. Leave empty to auto-generate.',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='news_items',
        on_delete=models.CASCADE,
    )
    is_published = models.BooleanField(default=True, db_index=True)
    is_pinned = models.BooleanField(default=False, help_text='Pinned items scroll first.')
    publish_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='Optional: hide this item automatically after this time.',
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-is_pinned', '-publish_at')
        verbose_name = 'News item'
        verbose_name_plural = 'News items'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('news:detail', args=[self.pk, self.slug])

    @property
    def is_active(self):
        now = timezone.now()
        if not self.is_published:
            return False
        if self.publish_at and self.publish_at > now:
            return False
        if self.expires_at and self.expires_at < now:
            return False
        return True

    @property
    def short_excerpt(self):
        if self.excerpt:
            return self.excerpt
        text = self.body
        if len(text) > 160:
            return text[:160].rsplit(' ', 1)[0] + '…'
        return text

    def _unique_slug(self):
        base = slugify(self.title)[:200] or 'news'
        qs = NewsItem.objects.all()
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        candidate = base
        counter = 1
        while qs.filter(slug=candidate).exists():
            candidate = f'{base}-{counter}'
            counter += 1
        return candidate
