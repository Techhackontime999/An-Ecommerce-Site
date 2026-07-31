from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0
    readonly_fields = ['price', 'quantity']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'first_name', 'last_name', 'city', 'paid', 'total', 'created']
    list_filter = ['paid', 'created', 'updated', 'city']
    search_fields = ['first_name', 'last_name', 'email', 'user__username']
    inlines = [OrderItemInline]
    list_select_related = ['user']
    date_hierarchy = 'created'
    readonly_fields = ['created', 'updated']
    actions = ['mark_as_paid']

    def total(self, obj):
        return obj.get_total_cost()
    total.short_description = 'Total (₹)'

    def mark_as_paid(self, request, queryset):
        queryset.update(paid=True)
    mark_as_paid.short_description = 'Mark selected orders as paid'
