from django.db import models
from django.urls import reverse
from ckeditor.fields import RichTextField
from accounts.models import SellerProfile
from django.utils import timezone
from django.db.models import Index
from django.db.models import Avg

class Category(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, unique=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'category'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_list_by_category', args=[self.slug])


class ProductQuerySet(models.QuerySet):
    """QuerySet with bulk-loading helpers for the price/rating properties.

    ``current_price``, ``average_rating`` and ``rating_count`` each issue a
    query per product when accessed on a plain queryset. These helpers load the
    same data with a single correlated query / prefetch, eliminating the N+1
    pattern on listing pages.
    """

    def with_rating(self):
        from django.db.models import (
            Avg,
            Count,
            FloatField,
            IntegerField,
            OuterRef,
            Subquery,
            Value,
        )
        from django.db.models.functions import Coalesce
        from reviews.models import ProductReview

        approved = ProductReview.objects.filter(
            product=OuterRef('pk'), status=ProductReview.Status.APPROVED
        )
        return self.annotate(
            _avg_rating=Coalesce(
                Subquery(
                    approved.values('product').annotate(
                        a=Avg('overall_rating')
                    ).values('a'),
                    output_field=FloatField(),
                ),
                Value(0.0, output_field=FloatField()),
            ),
            _rating_count=Coalesce(
                Subquery(
                    approved.values('product').annotate(
                        c=Count('pk')
                    ).values('c'),
                    output_field=IntegerField(),
                ),
                Value(0, output_field=IntegerField()),
            ),
        )

    def with_deal_price(self):
        from deals.models import Deal

        now = timezone.now()
        return self.prefetch_related(
            models.Prefetch(
                'deals',
                queryset=Deal.objects.filter(
                    start_time__lte=now, end_time__gte=now
                ).order_by('id'),
                to_attr='_active_deals',
            )
        )


class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products',
                                 on_delete=models.CASCADE)
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, db_index=True)
    image = models.ImageField(upload_to='products/%Y/%m/%d', blank=True)
    description = RichTextField(blank=True) 
    # remove below price if you mapped not with actual shop.product price make with seller assossiated price in  seller.models called seller_product model
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0, help_text='Inventory for products without variants.')
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    brand = models.CharField(max_length=100 , blank=True)
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    # add this field

    # class Meta:
    #     ordering = ('name',)
    #     index_together = (('id', 'slug'),)
    

    class Meta:
        ordering = ('name',)
        indexes = [
        Index(fields=['id', 'slug']),
        ]

    objects = ProductQuerySet.as_manager()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.id, self.slug])
    @property
    def current_price(self):
        active_deals = getattr(self, '_active_deals', None)
        if active_deals is not None:
            return active_deals[0].deal_price if active_deals else self.price
        now = timezone.now()
        active_deal = self.deals.filter(start_time__lte=now, end_time__gte=now).first()
        if active_deal:
            return active_deal.deal_price
        return self.price
    @property
    def average_rating(self):
        if hasattr(self, '_avg_rating'):
            value = self._avg_rating
            return 0 if value == 0 else round(value, 1)
        reviews = self.product_reviews.filter(status='approved')
        if reviews.exists():
            return round(reviews.aggregate(a=Avg('overall_rating'))['a'], 1)
        return 0

    @property
    def rating_count(self):
        if hasattr(self, '_rating_count'):
            return self._rating_count
        return self.product_reviews.filter(status='approved').count()

    def gallery_images(self):
        return self.images.all()

    @property
    def active_variants(self):
        return self.variants.filter(active=True)

    @property
    def first_active_variant(self):
        return self.active_variants.first()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images',
                                on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/%Y/%m/%d')
    is_main = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('sort_order', 'id')

    def __str__(self):
        return f'Image for {self.product.name} ({self.id})'


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name='variants',
                                on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    sku = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2,
                                null=True, blank=True,
                                help_text='Optional. Defaults to the product price.')
    stock = models.PositiveIntegerField(default=0)
    description = RichTextField(blank=True,
                                help_text='Optional. Own description for this variant.')
    image = models.ImageField(upload_to='products/%Y/%m/%d/variants', blank=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('id',)

    def __str__(self):
        return f'{self.product.name} — {self.name}'

    @property
    def effective_price(self):
        if self.price is not None:
            return self.price
        return self.product.current_price


class VariantImage(models.Model):
    variant = models.ForeignKey(ProductVariant, related_name='images',
                                on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/%Y/%m/%d/variants')
    sort_order = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('sort_order', 'id')

    def __str__(self):
        return f'Image for variant {self.variant.name} ({self.id})'






