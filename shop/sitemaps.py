from django.contrib.sitemaps import Sitemap

from .models import Category, Product


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Product.objects.filter(available=True).order_by('-updated')

    def lastmod(self, obj):
        return obj.updated


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Category.objects.all()
