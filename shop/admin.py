from django.contrib import admin
from django.utils import timezone
from core.admin_actions import export_as_csv_action
from .models import Category, Product, ProductImage, ProductVariant, VariantImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class VariantImageInline(admin.TabularInline):
    model = VariantImage
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
    actions = [
        export_as_csv_action(
            description='Export selected products as CSV',
            fields=['id', 'name', 'slug', 'category', 'brand', 'seller',
                    'price', 'available', 'created', 'updated'],
        ),
    ]

    def has_active_deal(self, obj):
        return obj.deals.filter(end_time__gte=timezone.now()).exists()
    has_active_deal.boolean = True
    has_active_deal.short_description = 'On Deal?'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['name', 'product', 'sku', 'effective_price', 'stock', 'active']
    list_filter = ['active', 'product__category']
    list_editable = ['stock', 'active']
    search_fields = ['name', 'sku', 'product__name']
    list_select_related = ['product']
    inlines = [VariantImageInline]
