from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'razorpay_order_id', 'razorpay_payment_id', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['razorpay_order_id', 'razorpay_payment_id', 'order__id']
