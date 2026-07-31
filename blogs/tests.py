from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Comment, Post, Tag


class BlogBaseTestCase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username='author1', password='pass1234'
        )
        self.reader = User.objects.create_user(
            username='reader1', password='pass1234'
        )
        self.tag = Tag.objects.create(name='Gadgets', slug='gadgets')
        self.post = Post.objects.create(
            author=self.author,
            title='Best Gadgets of 2026',
            slug='best-gadgets-2026',
            body='<p>Some great content.</p>',
            status=Post.Status.PUBLISHED,
            publish_at=timezone.now() - timezone.timedelta(days=1),
        )
        self.post.tags.add(self.tag)
        self.draft = Post.objects.create(
            author=self.author,
            title='Draft Post',
            slug='draft-post',
            body='<p>Not published.</p>',
            status=Post.Status.DRAFT,
        )


class PostModelTests(BlogBaseTestCase):
    def test_is_published_true_for_published(self):
        self.assertTrue(self.post.is_published)

    def test_is_published_false_for_draft(self):
        self.assertFalse(self.draft.is_published)

    def test_absolute_url(self):
        self.assertEqual(
            self.post.get_absolute_url(),
            reverse('blogs:post_detail', args=[self.post.pk, self.post.slug]),
        )


class BlogViewTests(BlogBaseTestCase):
    def test_home_shows_published_only(self):
        response = self.client.get(reverse('blogs:blog_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Best Gadgets of 2026')
        self.assertNotContains(response, 'Draft Post')

    def test_home_shows_sidebar_tags(self):
        response = self.client.get(reverse('blogs:blog_home'))
        self.assertContains(response, 'Gadgets')

    def test_post_detail_renders(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Some great content.')
        self.assertContains(response, 'Comments')

    def test_draft_returns_404(self):
        response = self.client.get(self.draft.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_author_posts(self):
        response = self.client.get(reverse('blogs:author_posts', args=['author1']))
        self.assertRedirects(response, reverse('blogs:profile', args=['author1']))

    def test_author_posts_unknown_author_404(self):
        response = self.client.get(reverse('blogs:author_posts', args=['nobody']))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('blogs:profile', args=['nobody']))
        self.assertEqual(response.status_code, 404)

    def test_posts_by_tag(self):
        response = self.client.get(reverse('blogs:posts_by_tag', args=['gadgets']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Best Gadgets of 2026')

    def test_view_count_increments_once_per_session(self):
        url = self.post.get_absolute_url()
        self.client.get(url)
        self.client.get(url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 1)


class CommentTests(BlogBaseTestCase):
    def test_add_comment_requires_login(self):
        url = reverse('blogs:add_comment', args=[self.post.pk, self.post.slug])
        response = self.client.post(url, {'body': 'Hello'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_add_comment_as_authenticated_user(self):
        self.client.login(username='reader1', password='pass1234')
        url = reverse('blogs:add_comment', args=[self.post.pk, self.post.slug])
        response = self.client.post(url, {'body': 'Great read!'})
        self.assertRedirects(response, self.post.get_absolute_url() + '#comments')
        self.assertEqual(Comment.objects.filter(post=self.post, author=self.reader).count(), 1)

    def test_reply_to_comment(self):
        self.client.login(username='reader1', password='pass1234')
        parent = Comment.objects.create(post=self.post, author=self.reader, body='Parent')
        url = reverse('blogs:add_comment', args=[self.post.pk, self.post.slug])
        self.client.post(url, {'body': 'Reply', 'parent_id': parent.pk})
        reply = Comment.objects.get(parent=parent)
        self.assertEqual(reply.body, 'Reply')

    def test_helpful_toggle(self):
        self.client.login(username='reader1', password='pass1234')
        comment = Comment.objects.create(post=self.post, author=self.reader, body='Helpful')
        url = reverse('blogs:toggle_helpful', args=[comment.pk])
        self.client.post(url)
        self.assertEqual(comment.helpful_votes.count(), 1)
        self.client.post(url)
        self.assertEqual(comment.helpful_votes.count(), 0)


class EngagementTests(BlogBaseTestCase):
    def test_like_toggle(self):
        self.client.login(username='reader1', password='pass1234')
        url = reverse('blogs:post_like', args=[self.post.pk, self.post.slug])
        self.client.post(url)
        self.assertEqual(self.post.likes.count(), 1)
        self.client.post(url)
        self.assertEqual(self.post.likes.count(), 0)

    def test_bookmark_toggle(self):
        self.client.login(username='reader1', password='pass1234')
        url = reverse('blogs:post_bookmark', args=[self.post.pk, self.post.slug])
        self.client.post(url)
        self.assertEqual(self.post.bookmarks.count(), 1)
        self.client.post(url)
        self.assertEqual(self.post.bookmarks.count(), 0)

    def test_like_requires_login(self):
        url = reverse('blogs:post_like', args=[self.post.pk, self.post.slug])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_follow_toggle(self):
        self.client.login(username='reader1', password='pass1234')
        url = reverse('blogs:toggle_follow', args=[self.author.username])
        self.client.post(url)
        self.assertEqual(self.reader.following.count(), 1)
        self.client.post(url)
        self.assertEqual(self.reader.following.count(), 0)

    def test_report_post(self):
        self.client.login(username='reader1', password='pass1234')
        url = reverse('blogs:report_post', args=[self.post.pk, self.post.slug])
        response = self.client.post(url, {'reason': 'spam', 'details': 'Looks like spam.'})
        self.assertRedirects(response, self.post.get_absolute_url())
        from .models import PostReport
        self.assertEqual(PostReport.objects.filter(post=self.post, reporter=self.reader).count(), 1)

    def test_like_awards_xp_to_author(self):
        self.client.login(username='reader1', password='pass1234')
        from .models import ensure_profile
        profile = ensure_profile(self.author)
        url = reverse('blogs:post_like', args=[self.post.pk, self.post.slug])
        self.client.post(url)
        profile.refresh_from_db()
        self.assertGreaterEqual(profile.xp, 2)


class CommunityPageTests(BlogBaseTestCase):
    def test_trending_renders(self):
        response = self.client.get(reverse('blogs:trending'))
        self.assertEqual(response.status_code, 200)

    def test_editors_picks_renders(self):
        response = self.client.get(reverse('blogs:editors_picks'))
        self.assertEqual(response.status_code, 200)

    def test_search_finds_post(self):
        url = reverse('blogs:post_search') + '?q=Gadgets'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Best Gadgets of 2026')

    def test_search_empty_query_renders(self):
        response = self.client.get(reverse('blogs:post_search'))
        self.assertEqual(response.status_code, 200)

    def test_leaderboard_renders(self):
        response = self.client.get(reverse('blogs:leaderboard'))
        self.assertEqual(response.status_code, 200)

    def test_rss_feed_renders(self):
        response = self.client.get(reverse('blogs:rss_feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Best Gadgets of 2026')

    def test_notifications_requires_login(self):
        response = self.client.get(reverse('blogs:notifications'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_notifications_page_renders_for_authenticated(self):
        self.client.login(username='reader1', password='pass1234')
        response = self.client.get(reverse('blogs:notifications'))
        self.assertEqual(response.status_code, 200)

    def test_profile_shows_posts_tab(self):
        response = self.client.get(reverse('blogs:profile', args=['author1']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Best Gadgets of 2026')

    def test_profile_reviews_tab(self):
        response = self.client.get(reverse('blogs:profile_tab', args=['author1', 'reviews']))
        self.assertEqual(response.status_code, 200)

    def test_profile_unknown_user_404(self):
        response = self.client.get(reverse('blogs:profile', args=['nobody']))
        self.assertEqual(response.status_code, 404)
