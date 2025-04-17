from django.db import models
from shop.models import Product
from deals.models import Deal
from accounts.models import SellerProfile
# Create your models here.

# this below model is essential for management of same products for different seller and then map this model where you want to display products instead of shop.product model
class SellerProduct(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE) 
    product = models.ForeignKey(Product, on_delete=models.CASCADE)       
    deals = models.ForeignKey(Deal, on_delete=models.CASCADE)     
    quantity = models.PositiveIntegerField()     
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.seller.user.username} - {self.product.name}"                         
