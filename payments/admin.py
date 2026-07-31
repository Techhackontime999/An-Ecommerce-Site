from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'amount', 'currency', 'status', 'razorpay_payment_id', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['razorpay_order_id', 'razorpay_payment_id', 'order__id']
    list_select_related = ['order']
    date_hierarchy = 'created_at'
    readonly_fields = ['razorpay_order_id', 'razorpay_payment_id', 'amount', 'currency', 'created_at']
