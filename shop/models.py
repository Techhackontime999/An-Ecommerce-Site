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


class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products',
                                 on_delete=models.CASCADE)
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, db_index=True)
    image = models.ImageField(upload_to='products/%Y/%m/%d', blank=True)
    description = RichTextField(blank=True) 
    # remove below price if you mapped not with actual shop.product price make with seller assossiated price in  seller.models called seller_product model
    price = models.DecimalField(max_digits=10, decimal_places=2)
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


    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.id, self.slug])
    @property
    def current_price(self):
        now = timezone.now()
        active_deal = self.deals.filter(start_time__lte=now, end_time__gte=now).first()
        if active_deal:
            return active_deal.deal_price
        return self.price
    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return round(sum([r.rating for r in reviews]) / reviews.count(), 1)
        return 0
    @property
    def rating_count(self):
        return self.reviews.count()

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






