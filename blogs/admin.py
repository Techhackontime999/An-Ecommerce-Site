from django.contrib import admin
from django.utils import timezone

from .models import (
    ActivityFeedItem,
    Badge,
    Bookmark,
    Comment,
    Follow,
    Like,
    Notification,
    Post,
    PostImage,
    PostProduct,
    PostReport,
    PostView,
    Tag,
    UserProfile,
    UserReaction,
)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    ordering = ('name',)
    list_display = ('name', 'slug', 'created')


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'description')
    search_fields = ('code', 'name')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'xp', 'created')
    list_filter = ('badges',)
    search_fields = ('user__username', 'bio')
    filter_horizontal = ('badges',)
    readonly_fields = ('level',)


class PostProductInline(admin.TabularInline):
    model = PostProduct
    extra = 1
    autocomplete_fields = ('product',)


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'post_type', 'status', 'publish_at', 'view_count', 'like_count', 'is_pinned')
    list_filter = ('status', 'post_type', 'tags', 'is_pinned')
    search_fields = ('title', 'author__username', 'tags__name')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'publish_at'
    raw_id_fields = ('author',)
    filter_horizontal = ('tags',)
    inlines = (PostProductInline, PostImageInline)
    actions = ('publish_selected', 'pin_selected', 'archive_selected')

    @admin.display(description='Likes')
    def like_count(self, obj):
        return obj.likes.count()

    @admin.action(description='Publish selected drafts')
    def publish_selected(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status=Post.Status.DRAFT).update(
            status=Post.Status.PUBLISHED,
            publish_at=now,
        )
        self.message_user(request, f'{updated} post(s) published.')

    @admin.action(description='Pin selected posts')
    def pin_selected(self, request, queryset):
        updated = queryset.update(is_pinned=True)
        self.message_user(request, f'{updated} post(s) pinned.')

    @admin.action(description='Archive selected posts')
    def archive_selected(self, request, queryset):
        updated = queryset.update(status=Post.Status.ARCHIVED)
        self.message_user(request, f'{updated} post(s) archived.')


@admin.register(PostProduct)
class PostProductAdmin(admin.ModelAdmin):
    list_display = ('post', 'product', 'role', 'position')
    list_filter = ('role',)
    search_fields = ('post__title', 'product__name')
    autocomplete_fields = ('post', 'product')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'post', 'status', 'is_approved', 'is_pinned', 'is_best_answer', 'created')
    list_filter = ('status', 'is_approved', 'is_pinned', 'is_best_answer')
    search_fields = ('author__username', 'body', 'post__title')
    raw_id_fields = ('author', 'post', 'parent', 'mentions')
    filter_horizontal = ('mentions',)
    actions = ('approve_comments', 'hide_comments')

    @admin.action(description='Approve selected comments')
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_approved=True, status=Comment.Status.VISIBLE)
        self.message_user(request, f'{updated} comment(s) approved.')

    @admin.action(description='Hide selected comments')
    def hide_comments(self, request, queryset):
        updated = queryset.update(status=Comment.Status.HIDDEN)
        self.message_user(request, f'{updated} comment(s) hidden.')


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created')
    search_fields = ('user__username', 'post__title')
    raw_id_fields = ('user', 'post')


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created')
    raw_id_fields = ('user', 'post')


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'following', 'created')
    raw_id_fields = ('follower', 'following')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'actor', 'verb', 'is_read', 'created')
    list_filter = ('verb', 'is_read')
    search_fields = ('recipient__username', 'actor__username')
    raw_id_fields = ('recipient', 'actor')


@admin.register(UserReaction)
class UserReactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'reaction', 'created')
    list_filter = ('reaction',)
    raw_id_fields = ('user',)


@admin.register(ActivityFeedItem)
class ActivityFeedItemAdmin(admin.ModelAdmin):
    list_display = ('actor', 'verb', 'post', 'created')
    list_filter = ('verb',)
    raw_id_fields = ('actor', 'post')


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'ip_address', 'created')
    list_filter = ('created',)
    raw_id_fields = ('post', 'user')


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ('post', 'caption', 'order')
    list_filter = ('post',)
    raw_id_fields = ('post',)


@admin.register(PostReport)
class PostReportAdmin(admin.ModelAdmin):
    list_display = ('post', 'reporter', 'reason', 'status', 'created')
    list_filter = ('status', 'reason')
    search_fields = ('post__title', 'reporter__username')
    raw_id_fields = ('post', 'reporter', 'handled_by')
    actions = ('mark_reviewed', 'dismiss_reports')

    @admin.action(description='Mark selected reports reviewed')
    def mark_reviewed(self, request, queryset):
        updated = queryset.update(status=PostReport.Status.REVIEWED, handled_by=request.user)
        self.message_user(request, f'{updated} report(s) marked reviewed.')

    @admin.action(description='Dismiss selected reports')
    def dismiss_reports(self, request, queryset):
        updated = queryset.update(status=PostReport.Status.DISMISSED, handled_by=request.user)
        self.message_user(request, f'{updated} report(s) dismissed.')
