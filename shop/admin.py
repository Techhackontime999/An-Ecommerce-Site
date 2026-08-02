from django.contrib import admin
from django.utils import timezone
from .models import Category, Product, ProductImage, ProductVariant


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'product_count']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('products')

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'available', 'created', 'has_active_deal']
    list_filter = ['available', 'category', 'created', 'updated']
    list_editable = ['price', 'available']
    search_fields = ['name', 'description', 'brand']
    prepopulated_fields = {'slug': ('name',)}
    list_select_related = ['category', 'seller']
    date_hierarchy = 'created'
    inlines = [ProductImageInline, ProductVariantInline]

    def has_active_deal(self, obj):
        return obj.deals.filter(end_time__gte=timezone.now()).exists()
    has_active_deal.boolean = True
    has_active_deal.short_description = 'On Deal?'
