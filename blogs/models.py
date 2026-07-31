from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from ckeditor.fields import RichTextField

from shop.models import Product


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('blogs:posts_by_tag', args=[self.slug])


class Post(models.Model):
    class PostType(models.TextChoices):
        ARTICLE = 'article', 'Article'
        TUTORIAL = 'tutorial', 'Tutorial'
        REVIEW = 'review', 'Product Review'
        COMPARISON = 'comparison', 'Comparison'
        GUIDE = 'guide', 'Buying Guide'
        BUYING_GUIDE = 'buying_guide', 'Buying Guide'
        QUESTION = 'question', 'Question'
        POLL = 'poll', 'Poll'
        VIDEO = 'video', 'Video'
        DEAL = 'deal', 'Deal'
        COUPON = 'coupon', 'Coupon'
        ANNOUNCEMENT = 'announcement', 'Announcement'
        NEWS = 'news', 'News'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        SCHEDULED = 'scheduled', 'Scheduled'
        ARCHIVED = 'archived', 'Archived'

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blog_posts',
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True)
    post_type = models.CharField(
        max_length=20,
        choices=PostType.choices,
        default=PostType.ARTICLE,
    )
    body = RichTextField()
    excerpt = models.CharField(max_length=300, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    publish_at = models.DateTimeField(default=timezone.now, db_index=True)
    featured_image = models.ImageField(upload_to='blog/%Y/%m/%d', blank=True)
    video_url = models.CharField(
        max_length=500,
        blank=True,
        help_text='Paste a YouTube or Vimeo link, or a direct .mp4/.webm file URL.',
    )
    is_pinned = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    tags = models.ManyToManyField(Tag, related_name='posts', blank=True)
    products = models.ManyToManyField(
        Product,
        through='PostProduct',
        related_name='blog_products',
        blank=True,
    )
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-publish_at',)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blogs:post_detail', args=[self.pk, self.slug])

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED and self.publish_at <= timezone.now()

    @property
    def plain_body(self):
        return strip_tags(self.body)

    @property
    def reading_time(self):
        words = len(self.plain_body.split())
        return max(1, round(words / 200))

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def bookmark_count(self):
        return self.bookmarks.count()

    @property
    def approved_comment_count(self):
        return self.comments.filter(is_approved=True).count()


class PostProduct(models.Model):
    class Role(models.TextChoices):
        FEATURED = 'featured', 'Featured'
        COMPARED = 'compared', 'Compared'
        RELATED = 'related', 'Related'
        AFFILIATE = 'affiliate', 'Affiliate'

    post = models.ForeignKey(
        Post,
        related_name='post_products',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        related_name='blog_mentions',
        on_delete=models.CASCADE,
    )
    role = models.CharField(
        max_length=12,
        choices=Role.choices,
        default=Role.RELATED,
    )
    position = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ('position',)
        unique_together = ('post', 'product')

    def __str__(self):
        return f"{self.product} in {self.post.title}"


class PostImage(models.Model):
    post = models.ForeignKey(
        Post,
        related_name='gallery_images',
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to='blog/%Y/%m/%d')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'id')

    def __str__(self):
        return f"Image {self.pk} for {self.post.title}"


class Comment(models.Model):
    class Status(models.TextChoices):
        VISIBLE = 'visible', 'Visible'
        HIDDEN = 'hidden', 'Hidden'

    post = models.ForeignKey(
        Post,
        related_name='comments',
        on_delete=models.CASCADE,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blog_comments',
        on_delete=models.CASCADE,
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='children',
        on_delete=models.CASCADE,
    )
    body = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.VISIBLE,
    )
    is_pinned = models.BooleanField(default=False)
    is_best_answer = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    edited = models.BooleanField(default=False)
    helpful_votes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='helpful_comments',
        blank=True,
    )
    mentions = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='mentioned_in_comments',
        blank=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return f"{self.author} on {self.post.title}"

    @property
    def helpful_count(self):
        return self.helpful_votes.count()


class Badge(models.Model):
    code = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    icon = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='blog_profile',
        on_delete=models.CASCADE,
    )
    bio = models.CharField(max_length=300, blank=True)
    avatar = models.ImageField(upload_to='blog/authors/%Y/%m/%d', blank=True)
    xp = models.PositiveIntegerField(default=0)
    badges = models.ManyToManyField(Badge, related_name='profiles', blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-xp',)

    def __str__(self):
        return self.user.username

    @property
    def level(self):
        total = 0
        level = 1
        while total + self._level_requirement(level) <= self.xp:
            total += self._level_requirement(level)
            level += 1
        return level

    @property
    def level_progress(self):
        requirement = self._level_requirement(self.level)
        earned = self.xp - sum(
            self._level_requirement(l) for l in range(1, self.level)
        )
        return min(100, round(earned / requirement * 100))

    def _level_requirement(self, level):
        return 100 * level

    def add_xp(self, amount):
        self.xp += amount
        self.save(update_fields=['xp'])

    def award_badge(self, code):
        defaults = {
            'first_post': ('First Post', 'Published your first post', 'fa-pen-nib'),
            'first_comment': ('First Comment', 'Joined the conversation', 'fa-comment'),
            'popular_author': ('Popular Author', 'A post reached 20 likes', 'fa-fire'),
            'top_commenter': ('Top Commenter', '10 helpful votes on your comments', 'fa-thumbs-up'),
        }
        badge = Badge.objects.filter(code=code).first()
        if not badge and code in defaults:
            name, description, icon = defaults[code]
            badge = Badge.objects.create(code=code, name=name, description=description, icon=icon)
        if badge:
            self.badges.add(badge)


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blog_likes',
        on_delete=models.CASCADE,
    )
    post = models.ForeignKey(
        Post,
        related_name='likes',
        on_delete=models.CASCADE,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ('-created',)

    def __str__(self):
        return f"{self.user} likes {self.post}"


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blog_bookmarks',
        on_delete=models.CASCADE,
    )
    post = models.ForeignKey(
        Post,
        related_name='bookmarks',
        on_delete=models.CASCADE,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ('-created',)

    def __str__(self):
        return f"{self.user} bookmarked {self.post.title}"


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='following',
        on_delete=models.CASCADE,
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='followers',
        on_delete=models.CASCADE,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        ordering = ('-created',)

    def __str__(self):
        return f"{self.follower} follows {self.following}"


class Notification(models.Model):
    class Verb(models.TextChoices):
        COMMENT = 'comment', 'commented on'
        REPLY = 'reply', 'replied to your comment'
        LIKE = 'like', 'liked'
        FOLLOW = 'follow', 'started following you'
        HELPFUL = 'helpful', 'found your comment helpful'
        MENTION = 'mention', 'mentioned you'
        REVIEW = 'review', 'left a review'
        BADGE = 'badge', 'earned a badge'
        ANNOUNCEMENT = 'announcement', 'posted'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blog_notifications',
        on_delete=models.CASCADE,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='notifications_sent',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey('content_type', 'object_id')
    is_read = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created',)
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created']),
        ]

    def __str__(self):
        return f"{self.actor} {self.get_verb_display()} {self.target}"


class UserReaction(models.Model):
    class Reaction(models.TextChoices):
        LIKE = 'like', 'Like'
        LOVE = 'love', 'Love'
        HELPFUL = 'helpful', 'Helpful'
        CELEBRATE = 'celebrate', 'Celebrate'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blog_reactions',
        on_delete=models.CASCADE,
    )
    reaction = models.CharField(
        max_length=12,
        choices=Reaction.choices,
        default=Reaction.LIKE,
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')

    def __str__(self):
        return f"{self.user} {self.reaction} {self.content_object}"


class ActivityFeedItem(models.Model):
    class Verb(models.TextChoices):
        POST = 'post', 'published a post'
        COMMENT = 'comment', 'commented'
        REVIEW = 'review', 'reviewed a product'
        LIKE = 'like', 'liked a post'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blog_activity',
        on_delete=models.CASCADE,
    )
    verb = models.CharField(max_length=12, choices=Verb.choices)
    post = models.ForeignKey(
        Post,
        null=True,
        blank=True,
        related_name='activity_items',
        on_delete=models.CASCADE,
    )
    text = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f"{self.actor} {self.get_verb_display()}"


class PostView(models.Model):
    post = models.ForeignKey(
        Post,
        related_name='views',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='blog_post_views',
        on_delete=models.SET_NULL,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f"view of {self.post}"


class PostReport(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWED = 'reviewed', 'Reviewed'
        DISMISSED = 'dismissed', 'Dismissed'

    class Reason(models.TextChoices):
        SPAM = 'spam', 'Spam'
        INAPPROPRIATE = 'inappropriate', 'Inappropriate content'
        MISLEADING = 'misleading', 'Misleading'
        COPYRIGHT = 'copyright', 'Copyright'
        OTHER = 'other', 'Other'

    post = models.ForeignKey(
        Post,
        related_name='reports',
        on_delete=models.CASCADE,
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='post_reports',
        on_delete=models.CASCADE,
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='handled_post_reports',
        on_delete=models.SET_NULL,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f"{self.reporter} reported {self.post}"


def ensure_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _unique_slug(instance, base):
    slug = slugify(base)[:200] or 'post'
    qs = Post.objects.all()
    if instance.pk:
        qs = qs.exclude(pk=instance.pk)
    candidate = slug
    counter = 1
    while qs.filter(slug=candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate
