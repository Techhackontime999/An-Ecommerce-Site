import json
import re
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import resolve, reverse
from django.urls.exceptions import Resolver404
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import CommentForm, PostForm, PostReportForm
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
    PostReport,
    PostView,
    Tag,
    UserProfile,
    ensure_profile,
)
from shop.models import Product

MENTION_RE = re.compile(r'@(\w{1,30})')
HEADING_RE = re.compile(r'<h([23])[^>]*>(.*?)</h\1>', re.IGNORECASE | re.DOTALL)
IMG_RE = re.compile(r'<img(?![^>]*loading=)[^>]*>', re.IGNORECASE | re.DOTALL)
YT_RE = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{6,})'
)
VIMEO_RE = re.compile(r'(?:https?://)?(?:www\.)?vimeo\.com/(\d+)')
VIDEO_FILE_RE = re.compile(r'\.(mp4|webm|ogg)(\?|$)', re.IGNORECASE)


def _embed_url(url):
    if not url:
        return None
    m = YT_RE.search(url)
    if m:
        return f'https://www.youtube-nocookie.com/embed/{m.group(1)}'
    m = VIMEO_RE.search(url)
    if m:
        return f'https://player.vimeo.com/video/{m.group(1)}'
    return None


def _video_info(url):
    if not url:
        return None, None
    if VIDEO_FILE_RE.search(url):
        return None, url
    return _embed_url(url), None


def _resolve_product_url(url):
    """Turn a pasted product URL (absolute or relative) into a Product or None."""
    if not url:
        return None
    path = url.strip()
    if path.startswith(('http://', 'https://')):
        path = '/' + path.split('/', 3)[-1]
    try:
        match = resolve(path)
    except Resolver404:
        return None
    if match.namespace != 'shop' or match.url_name != 'product_detail':
        return None
    product_id = match.kwargs.get('id') or match.kwargs.get('pk')
    if product_id is None:
        return None
    try:
        return Product.objects.get(pk=product_id, available=True)
    except Product.DoesNotExist:
        return None


def _save_gallery_images(post, files, max_images=10):
    """Persist newly uploaded gallery photos onto a post."""
    if not files:
        return 0
    existing = post.gallery_images.count()
    saved = 0
    for index, upload in enumerate(files):
        if existing + saved >= max_images:
            break
        PostImage.objects.create(post=post, image=upload, order=existing + saved)
        saved += 1
    return saved


def _published_posts():
    return Post.objects.filter(
        status=Post.Status.PUBLISHED,
        publish_at__lte=timezone.now(),
    ).annotate(
        comment_count=Count('comments', filter=Q(comments__is_approved=True)),
    ).select_related('author__blog_profile').order_by('-publish_at')


def _sidebar():
    return {
        'sidebar_tags': Tag.objects.annotate(num_posts=Count('posts')).order_by('-num_posts')[:15],
        'sidebar_recent': _published_posts().prefetch_related('tags')[:5],
        'sidebar_authors': (
            UserProfile.objects.select_related('user')
            .annotate(num_posts=Count('user__blog_posts'))
            .order_by('-xp', '-num_posts')[:5]
        ),
    }


def _profile(user):
    return ensure_profile(user)


def _award_xp(user, amount):
    _profile(user).add_xp(amount)


def _notify(recipient, actor, verb, target):
    if recipient and actor and recipient != actor:
        Notification.objects.create(
            recipient=recipient,
            actor=actor,
            verb=verb,
            content_type=ContentType.objects.get_for_model(target),
            object_id=target.pk,
        )


def _record_activity(actor, verb, post=None, text=''):
    ActivityFeedItem.objects.create(actor=actor, verb=verb, post=post, text=text)


def _parse_mentions(body):
    usernames = []
    for match in MENTION_RE.findall(body or ''):
        if match not in usernames:
            usernames.append(match)
    return list(User.objects.filter(username__in=usernames))


def _process_body(body):
    toc = []

    def repl(match):
        level = int(match.group(1))
        inner = match.group(2)
        text = re.sub(r'<[^>]+>', '', inner).strip()
        anchor = slugify(text)[:60] or 'section-{}'.format(len(toc) + 1)
        toc.append({'level': level, 'title': text, 'anchor': anchor})
        return f'<h{level} id="{anchor}">{inner}</h{level}>'

    body_html = HEADING_RE.sub(repl, body or '')

    def lazy_img(match):
        tag = match.group(0)
        if 'loading=' in tag.lower():
            return tag
        return tag[:-1] + ' loading="lazy" decoding="async">'

    body_html = IMG_RE.sub(lazy_img, body_html)
    return body_html, toc


def _trending_posts(days=7, limit=12):
    since = timezone.now() - timezone.timedelta(days=days)
    qs = (
        _published_posts()
        .annotate(
            views_7d=Count('views', filter=Q(views__created__gte=since)),
            likes_7d=Count('likes', filter=Q(likes__created__gte=since)),
            bookmarks_7d=Count('bookmarks', filter=Q(bookmarks__created__gte=since)),
            comments_7d=Count('comments', filter=Q(
                comments__created__gte=since,
                comments__is_approved=True,
            )),
        )
        .prefetch_related('tags', 'author')
    )
    scored = []
    for post in qs:
        age_days = max((timezone.now() - post.publish_at).days, 1)
        raw = (
            post.views_7d
            + 3 * post.likes_7d
            + 2 * post.bookmarks_7d
            + 5 * post.comments_7d
        )
        scored.append((post, raw / (1 + age_days * 0.2)))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [post for post, _ in scored[:limit]]


def _paginate(request, qs, per_page=9):
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    return page_obj, page_obj.object_list


def _user_context(actor):
    return {
        'actor': actor,
        'profile': ensure_profile(actor) if actor.is_authenticated else None,
    }


def blog_home(request):
    feed = request.GET.get('feed', 'recent')
    if feed == 'trending':
        posts = _trending_posts(days=7, limit=30)
    elif feed == 'picks':
        posts = _published_posts().filter(is_pinned=True).prefetch_related('tags', 'author')
    else:
        feed = 'recent'
        posts = _published_posts().prefetch_related('tags', 'author')

    pinned_posts = [p for p in _published_posts().filter(is_pinned=True).prefetch_related('tags', 'author')[:3]]

    if feed == 'recent':
        if not pinned_posts:
            pinned_posts = list(posts[:3])
        pinned_ids = [p.id for p in pinned_posts]
        posts = [p for p in posts if p.id not in pinned_ids]

    paginator = Paginator(posts, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'feed': feed,
        'pinned_posts': pinned_posts,
        'page_obj': page_obj,
        'posts': page_obj.object_list,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/blog_home.html', context)


def post_detail(request, pk, slug):
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related('tags', 'products', 'gallery_images'),
        pk=pk,
        slug=slug,
    )
    is_staff_or_author = request.user.is_staff or request.user == post.author
    if not post.is_published and not is_staff_or_author:
        raise Http404

    if post.is_published:
        session_key = f'blog_viewed_{post.pk}'
        first_view = not request.session.get(session_key)
        if first_view:
            Post.objects.filter(pk=post.pk).update(view_count=F('view_count') + 1)
            request.session[session_key] = True
        PostView.objects.create(
            post=post,
            user=request.user if request.user.is_authenticated else None,
            ip_address=request.META.get('REMOTE_ADDR'),
        )

    body_html, toc = _process_body(post.body)
    post.body_html = body_html
    post.video_embed, post.video_file = _video_info(post.video_url)

    comments = list(
        Comment.objects.filter(post=post, is_approved=True, parent__isnull=True)
        .select_related('author')
        .order_by('-is_pinned', 'created')
    )
    replies = list(
        Comment.objects.filter(post=post, is_approved=True, parent__isnull=False)
        .select_related('author', 'parent')
        .order_by('created')
    )
    reply_map = {}
    for reply in replies:
        reply_map.setdefault(reply.parent_id, []).append(reply)
    for comment in comments:
        comment.replies = reply_map.get(comment.pk, [])
    for reply in replies:
        reply.replies = reply_map.get(reply.pk, [])

    related_posts = (
        _published_posts()
        .filter(tags__in=post.tags.all())
        .exclude(pk=post.pk)
        .distinct()
        .prefetch_related('tags', 'author')[:4]
    )
    if not related_posts:
        related_posts = (
            _published_posts()
            .exclude(pk=post.pk)
            .annotate(
                score=Count('views', filter=Q(
                    views__created__gte=timezone.now() - timezone.timedelta(days=14),
                )),
            )
            .order_by('-score')[:4]
        )
    more_from_author = (
        _published_posts()
        .filter(author=post.author)
        .exclude(pk=post.pk)
        .prefetch_related('tags')[:3]
    )

    absolute_url = request.build_absolute_uri(post.get_absolute_url())
    share_text = quote(post.title)
    og_image = None
    if post.featured_image:
        og_image = request.build_absolute_uri(post.featured_image.url)
    context = {
        'post': post,
        'comment_tree': comments,
        'comment_count': post.approved_comment_count,
        'form': CommentForm(),
        'related_posts': related_posts,
        'more_from_author': more_from_author,
        'canonical_url': request.build_absolute_uri(request.path),
        'og_image': og_image,
        'blog_home_url': request.build_absolute_uri(reverse('blogs:blog_home')),
        'toc': toc,
        'reading_time': post.reading_time,
        'is_liked': bool(post.likes.filter(user=request.user).exists()) if request.user.is_authenticated else False,
        'is_bookmarked': bool(Bookmark.objects.filter(user=request.user, post=post).exists()) if request.user.is_authenticated else False,
        'is_following_author': bool(Follow.objects.filter(follower=request.user, following=post.author).exists()) if request.user.is_authenticated else False,
        'share_url': absolute_url,
        'share_whatsapp': f'https://wa.me/?text={share_text}%20{quote(absolute_url)}',
        'share_x': f'https://twitter.com/intent/tweet?url={quote(absolute_url)}&text={share_text}',
        'can_moderate': request.user == post.author,
        'schema_json': json.dumps({
            '@context': 'https://schema.org',
            '@type': 'Article',
            'headline': post.title,
            'description': post.meta_description or post.excerpt or post.plain_body[:300],
            'author': {'@type': 'Person', 'name': post.author.get_full_name() or post.author.username},
            'datePublished': post.publish_at.isoformat(),
            'dateModified': post.updated.isoformat(),
            'image': post.featured_image.url if post.featured_image else None,
            'mainEntityOfPage': absolute_url,
            'wordCount': len(post.plain_body.split()),
        }),
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/post_detail.html', context)


def user_profile(request, username, tab='posts'):
    author = get_object_or_404(User, username=username)
    profile = UserProfile.objects.filter(user=author).first()
    posts = _published_posts().filter(author=author).prefetch_related('tags')
    followers_count = author.followers.count()
    following_count = author.following.count()
    is_following = (
        Follow.objects.filter(follower=request.user, following=author).exists()
        if request.user.is_authenticated else False
    )

    context = {
        'author': author,
        'profile': profile,
        'tab': tab,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
    }

    if tab == 'reviews':
        from reviews.models import ProductReview
        reviews = ProductReview.objects.filter(
            reviewer=author,
            status=ProductReview.Status.APPROVED,
        ).select_related('product')
        page_obj, items = _paginate(request, reviews, per_page=9)
        context['page_obj'] = page_obj
        context['reviews'] = items
    elif tab == 'bookmarks':
        bookmarks = Bookmark.objects.filter(user=author).select_related('post')
        page_obj, items = _paginate(request, bookmarks, per_page=9)
        context['page_obj'] = page_obj
        context['posts'] = [b.post for b in items]
    else:
        tab = 'posts'
        page_obj, items = _paginate(request, posts, per_page=9)
        context['page_obj'] = page_obj
        context['posts'] = items

    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/profile.html', context)


def author_posts(request, username):
    return redirect('blogs:profile', username=username)


def posts_by_tag(request, tag_slug):
    tag = get_object_or_404(Tag, slug=tag_slug)
    posts = _published_posts().filter(tags=tag).prefetch_related('tags')
    page_obj, post_list = _paginate(request, posts)
    context = {
        'tag': tag,
        'page_obj': page_obj,
        'posts': post_list,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/posts_by_tag.html', context)


def trending(request):
    posts = _trending_posts(days=30, limit=60)
    paginator = Paginator(posts, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'days': 30,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/trending.html', context)


def editors_picks(request):
    posts = _published_posts().filter(is_pinned=True).prefetch_related('tags')
    page_obj, post_list = _paginate(request, posts)
    context = {
        'page_obj': page_obj,
        'posts': post_list,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/editors_picks.html', context)


def post_search(request):
    query = request.GET.get('q', '').strip()
    posts = _published_posts().prefetch_related('tags')
    if query:
        posts = posts.filter(
            Q(title__icontains=query)
            | Q(body__icontains=query)
            | Q(tags__name__icontains=query)
            | Q(author__username__icontains=query)
        ).distinct()
    page_obj, post_list = _paginate(request, posts)
    context = {
        'query': query,
        'page_obj': page_obj,
        'posts': post_list,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/search.html', context)


def post_search_api(request):
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        posts = (
            _published_posts()
            .filter(
                Q(title__icontains=query)
                | Q(tags__name__icontains=query)
                | Q(author__username__icontains=query)
            )
            .distinct()[:8]
        )
        results = [
            {
                'title': post.title,
                'url': post.get_absolute_url(),
                'author': post.author.username,
                'date': post.publish_at.strftime('%b %d, %Y'),
                'reading_time': post.reading_time,
            }
            for post in posts
        ]
    return JsonResponse({'query': query, 'results': results})


def product_lookup(request):
    url = request.GET.get('url', '').strip()
    product = _resolve_product_url(url)
    if product is None:
        return JsonResponse({
            'found': False,
            'error': 'That is not a valid Shop-Seed product link (or the product is unavailable).',
        })
    return JsonResponse({
        'found': True,
        'id': product.pk,
        'name': product.name,
        'slug': product.slug,
        'url': product.get_absolute_url(),
        'price': str(product.current_price),
        'image': product.image.url if product.image else None,
    })


@login_required
@require_POST
def gallery_image_delete(request, pk, slug, gallery_pk):
    image = get_object_or_404(PostImage, pk=gallery_pk)
    if request.user != image.post.author:
        raise Http404
    image.delete()
    messages.success(request, 'Photo removed.')
    return redirect('blogs:post_update', pk=image.post.pk, slug=image.post.slug)


def leaderboard(request):
    top_authors = UserProfile.objects.select_related('user').annotate(
        num_posts=Count('user__blog_posts'),
        total_likes=Count('user__blog_posts__likes'),
    ).order_by('-xp')[:10]

    top_commenters = list(
        User.objects.annotate(
            total_helpful=Count('blog_comments__helpful_votes', distinct=True),
        ).order_by('-total_helpful')[:10]
    )

    from reviews.models import ProductReview
    top_reviewers = list(
        User.objects.annotate(
            total_reviews=Count('product_reviews', filter=Q(product_reviews__status='approved')),
        ).order_by('-total_reviews')[:10]
    )

    context = {
        'top_authors': top_authors,
        'top_commenters': top_commenters,
        'top_reviewers': top_reviewers,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/leaderboard.html', context)


@login_required
def activity_feed(request):
    followed = list(request.user.following.values_list('following_id', flat=True))
    feed_posts = (
        _published_posts()
        .filter(author_id__in=followed)
        .prefetch_related('tags', 'author')[:24]
    )
    activities = ActivityFeedItem.objects.filter(actor_id__in=followed).select_related('actor')[:30]
    context = {
        'feed_posts': feed_posts,
        'activities': activities,
        'following_count': len(followed),
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/activity_feed.html', context)


@login_required
def notifications_list(request):
    notif_list = request.user.blog_notifications.select_related('actor').prefetch_related(
        'content_object'
    )
    page_obj, items = _paginate(request, notif_list, per_page=20)
    unread_count = request.user.blog_notifications.filter(is_read=False).count()
    context = {
        'page_obj': page_obj,
        'notifications': items,
        'unread_count': unread_count,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/notifications.html', context)


@login_required
@require_POST
def mark_notifications_read(request):
    request.user.blog_notifications.filter(is_read=False).update(is_read=True)
    return redirect('blogs:notifications')


@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.slug = form.cleaned_data.get('slug') or form._auto_slug()
            if not post.slug:
                from .models import _unique_slug
                post.slug = _unique_slug(post, post.title)
            if post.status == Post.Status.PUBLISHED and not post.is_published:
                post.status = Post.Status.SCHEDULED
            post.save()
            form.save_m2m()
            role = form.cleaned_data.get('product_role')
            if role:
                post.post_products.filter(role__isnull=False).update(role=role)
            _save_gallery_images(post, request.FILES.getlist('gallery'))
            _award_xp(request.user, 25)
            _record_activity(request.user, ActivityFeedItem.Verb.POST, post=post)
            if not _profile(request.user).badges.filter(code='first_post').exists():
                _profile(request.user).award_badge('first_post')
            messages.success(request, 'Your post has been published.')
            return redirect(post.get_absolute_url())
        messages.error(request, 'Please fix the errors below.')
    else:
        form = PostForm()
    context = {'form': form, 'editing': False}
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/post_form.html', context)


@login_required
def post_update(request, pk, slug):
    post = get_object_or_404(Post, pk=pk, slug=slug)
    if request.user != post.author:
        raise Http404
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.slug = form.cleaned_data.get('slug') or form._auto_slug() or post.slug
            updated.save()
            form.save_m2m()
            role = form.cleaned_data.get('product_role')
            if role:
                post.post_products.update(role=role)
            _save_gallery_images(post, request.FILES.getlist('gallery'))
            messages.success(request, 'Your post has been updated.')
            return redirect(post.get_absolute_url())
        messages.error(request, 'Please fix the errors below.')
    else:
        form = PostForm(instance=post)
    context = {'form': form, 'post': post, 'editing': True}
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/post_form.html', context)


@login_required
@require_POST
def post_delete(request, pk, slug):
    post = get_object_or_404(Post, pk=pk, slug=slug)
    if request.user != post.author:
        raise Http404
    post.status = Post.Status.ARCHIVED
    post.save(update_fields=['status'])
    messages.success(request, 'Post archived.')
    return redirect('blogs:blog_home')


@login_required
@require_POST
def post_like(request, pk, slug):
    post = get_object_or_404(Post, pk=pk, slug=slug)
    like = Like.objects.filter(user=request.user, post=post).first()
    if like:
        like.delete()
    else:
        Like.objects.create(user=request.user, post=post)
        _notify(post.author, request.user, Notification.Verb.LIKE, post)
        _award_xp(post.author, 2)
        if post.likes.count() >= 20 and not _profile(post.author).badges.filter(code='popular_author').exists():
            _profile(post.author).award_badge('popular_author')
    return redirect(post.get_absolute_url())


@login_required
@require_POST
def post_bookmark(request, pk, slug):
    post = get_object_or_404(Post, pk=pk, slug=slug)
    bookmark = Bookmark.objects.filter(user=request.user, post=post).first()
    if bookmark:
        bookmark.delete()
    else:
        Bookmark.objects.create(user=request.user, post=post)
    return redirect(post.get_absolute_url())


@login_required
def my_bookmarks(request):
    bookmarks = (
        Bookmark.objects.filter(
            user=request.user,
            post__status=Post.Status.PUBLISHED,
            post__publish_at__lte=timezone.now(),
        )
        .select_related('post', 'post__author')
        .order_by('-created')
    )
    post_ids = [b.post_id for b in bookmarks]
    posts = list(_published_posts().filter(pk__in=post_ids))
    order = {pk: i for i, pk in enumerate(post_ids)}
    posts.sort(key=lambda p: order.get(p.pk, 0))
    total_read = sum(p.reading_time for p in posts)
    context = {
        'posts': posts,
        'total_saved': len(posts),
        'total_read': total_read,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/bookmarks.html', context)


@login_required
def author_dashboard(request):
    since_28 = timezone.now() - timezone.timedelta(days=28)
    posts = list(
        Post.objects.filter(author=request.user)
        .annotate(
            comments_count=Count('comments', filter=Q(comments__is_approved=True)),
            likes_count=Count('likes'),
            bookmarks_count=Count('bookmarks'),
            views_28d=Count('views', filter=Q(views__created__gte=since_28)),
        )
        .order_by('-publish_at')
    )
    published = [p for p in posts if p.is_published]
    drafts = [p for p in posts if p.status == Post.Status.DRAFT]

    def totals(attr):
        return sum(getattr(p, attr) for p in published)

    total_views = totals('view_count')
    total_likes = totals('likes_count')
    total_bookmarks = totals('bookmarks_count')
    total_comments = totals('comments_count')
    views_28d = sum(p.views_28d for p in published)

    insights = []
    top = max(published, key=lambda p: p.view_count) if published else None
    if top and top.view_count:
        insights.append({
            'icon': 'fa-trophy',
            'text': f'"{top.title}" is your most-read post with {top.view_count} views.',
        })
    if published:
        avg = round(total_views / len(published), 1)
        insights.append({
            'icon': 'fa-chart-line',
            'text': f'Your posts average {avg} views each.',
        })
    if total_bookmarks:
        insights.append({
            'icon': 'fa-bookmark',
            'text': f'Readers saved your posts {total_bookmarks} times — a strong trust signal.',
        })
    if views_28d:
        insights.append({
            'icon': 'fa-bolt',
            'text': f'Your posts got {views_28d} reads in the last 28 days.',
        })
    if drafts:
        insights.append({
            'icon': 'fa-feather-alt',
            'text': f'You have {len(drafts)} draft{"" if len(drafts) == 1 else "s"} waiting. Publish to grow your audience.',
        })
    if not posts:
        insights.append({
            'icon': 'fa-lightbulb',
            'text': 'No posts yet — write your first one and it will appear here.',
        })

    context = {
        'posts': posts,
        'published_count': len(published),
        'draft_count': len(drafts),
        'total_views': total_views,
        'total_likes': total_likes,
        'total_bookmarks': total_bookmarks,
        'total_comments': total_comments,
        'views_28d': views_28d,
        'insights': insights,
    }
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/dashboard.html', context)


@login_required
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return redirect('blogs:profile', username=username)
    follow = Follow.objects.filter(follower=request.user, following=target).first()
    if follow:
        follow.delete()
        messages.info(request, f'Unfollowed @{username}.')
    else:
        Follow.objects.create(follower=request.user, following=target)
        _notify(target, request.user, Notification.Verb.FOLLOW, target)
        messages.success(request, f'You now follow @{username}.')
    return redirect('blogs:profile', username=username)


@login_required
@require_POST
def add_comment(request, pk, slug):
    post = get_object_or_404(Post, pk=pk, slug=slug)
    if not post.is_published or not post.allow_comments:
        raise Http404
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        mentioned = _parse_mentions(comment.body)
        comment.mentions.add(*[u for u in mentioned if u != request.user])
        _record_activity(request.user, ActivityFeedItem.Verb.COMMENT, post=post)
        _award_xp(request.user, 5)
        if not _profile(request.user).badges.filter(code='first_comment').exists():
            _profile(request.user).award_badge('first_comment')
        if comment.parent:
            _notify(comment.parent.author, request.user, Notification.Verb.REPLY, comment)
        else:
            _notify(post.author, request.user, Notification.Verb.COMMENT, comment)
        for user in mentioned:
            if user != comment.parent.author and user != post.author:
                _notify(user, request.user, Notification.Verb.MENTION, comment)
    else:
        messages.error(request, 'Could not post your comment.')
    return redirect(reverse('blogs:post_detail', args=[post.pk, post.slug]) + '#comments')


@login_required
@require_POST
def toggle_helpful(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if request.user in comment.helpful_votes.all():
        comment.helpful_votes.remove(request.user)
    else:
        comment.helpful_votes.add(request.user)
        _notify(comment.author, request.user, Notification.Verb.HELPFUL, comment)
        _award_xp(comment.author, 10)
        if comment.author.blog_comments.filter(helpful_votes__isnull=False).distinct().count() >= 10:
            if not _profile(comment.author).badges.filter(code='top_commenter').exists():
                _profile(comment.author).award_badge('top_commenter')
    return redirect(reverse('blogs:post_detail', args=[comment.post.pk, comment.post.slug]) + '#comments')


@login_required
def report_post(request, pk, slug):
    post = get_object_or_404(Post, pk=pk, slug=slug)
    if request.method == 'POST':
        form = PostReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.post = post
            report.reporter = request.user
            report.save()
            messages.success(request, 'Thanks — our moderation team will review this post.')
            return redirect(post.get_absolute_url())
    else:
        form = PostReportForm()
    context = {'post': post, 'form': form}
    context.update(_sidebar())
    context.update(_user_context(request.user))
    return render(request, 'blogs/report_post.html', context)
