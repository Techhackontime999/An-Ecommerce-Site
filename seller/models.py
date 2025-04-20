# from django.db import models
# from shop.models import Product
# from deals.models import Deal
# from accounts.models import SellerProfile
# # Create your models here.

# # this below model is essential for management of same products for different seller and then map this model where you want to display products instead of shop.product model
# class SellerProduct(models.Model):
#     seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE) 
#     product = models.ForeignKey(Product, on_delete=models.CASCADE)       
#     deals = models.ForeignKey(Deal, on_delete=models.CASCADE)     
#     quantity = models.PositiveIntegerField()     
#     price = models.DecimalField(max_digits=10, decimal_places=2)

#     def __str__(self):
#         return f"{self.seller.user.username} - {self.product.name}"                         




from django.db import models
from shop.models import Product
from deals.models import Deal  # adjust import based on your structure
from accounts.models import SellerProfile
from django.utils import timezone

class SellerProduct(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="seller_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="seller_products")
    deals = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="seller_products")
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # This field is_active_seller tells you whether the seller is currently offering the product for sale or not.
    is_active_seller = models.BooleanField(default=True)  # useful for deactivating listings
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('seller', 'product')  # seller can't list same product twice

    def __str__(self):
        return f"{self.seller.shop_name} sells {self.product.name}"
