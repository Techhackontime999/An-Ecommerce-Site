from django.db import models
from django.urls import reverse
from ckeditor.fields import RichTextField
from accounts.models import SellerProfile
from django.utils import timezone
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

    class Meta:
        ordering = ('name',)
        index_together = (('id', 'slug'),)

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
