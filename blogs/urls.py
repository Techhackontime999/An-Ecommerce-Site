from django.urls import path

from . import views
from .feeds import AtomLatestPostsFeed, LatestPostsFeed
from .sitemaps import PostSitemap

app_name = 'blogs'

sitemaps = {
    'posts': PostSitemap,
}

urlpatterns = [
    path('', views.blog_home, name='blog_home'),
    path('search/', views.post_search, name='post_search'),
    path('search/api/', views.post_search_api, name='post_search_api'),
    path('products/lookup/', views.product_lookup, name='product_lookup'),
    path('dashboard/', views.author_dashboard, name='author_dashboard'),
    path('bookmarks/', views.my_bookmarks, name='my_bookmarks'),
    path('trending/', views.trending, name='trending'),
    path('picks/', views.editors_picks, name='editors_picks'),
    path('search/', views.post_search, name='post_search'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('feed/', views.activity_feed, name='activity_feed'),
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('author/<str:username>/', views.author_posts, name='author_posts'),
    path('author/<str:username>/follow/', views.toggle_follow, name='toggle_follow'),
    path('profile/<str:username>/', views.user_profile, name='profile'),
    path('profile/<str:username>/<slug:tab>/', views.user_profile, name='profile_tab'),
    path('tag/<slug:tag_slug>/', views.posts_by_tag, name='posts_by_tag'),
    path('post/new/', views.post_create, name='post_create'),
    path('post/<int:pk>/<slug:slug>/', views.post_detail, name='post_detail'),
    path('post/<int:pk>/<slug:slug>/edit/', views.post_update, name='post_update'),
    path('post/<int:pk>/<slug:slug>/delete/', views.post_delete, name='post_delete'),
    path('post/<int:pk>/<slug:slug>/like/', views.post_like, name='post_like'),
    path('post/<int:pk>/<slug:slug>/bookmark/', views.post_bookmark, name='post_bookmark'),
    path('post/<int:pk>/<slug:slug>/comment/', views.add_comment, name='add_comment'),
    path('post/<int:pk>/<slug:slug>/report/', views.report_post, name='report_post'),
    path('post/<int:pk>/<slug:slug>/gallery/<int:gallery_pk>/delete/', views.gallery_image_delete, name='gallery_image_delete'),
    path('comment/<int:pk>/helpful/', views.toggle_helpful, name='toggle_helpful'),
    path('feed/rss/', LatestPostsFeed(), name='rss_feed'),
    path('feed/atom/', AtomLatestPostsFeed(), name='atom_feed'),
]
