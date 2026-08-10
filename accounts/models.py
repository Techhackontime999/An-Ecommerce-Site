# accounts/models.py

from django.apps import apps
from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify
from django.db.models import Avg
from django.db.models import Count

from core.validators import validate_image_file, validate_document_file

# from shop.models import Product

class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=15, blank=True, null=True)  # Optional GST field
    bank_account = models.CharField(max_length=100)
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    description = models.TextField(blank=True)

    # --- Verification -------------------------------------------------------
    # A seller may only sell once an admin has reviewed their KYC / business
    # documents and approved them. New registrations start *unverified*.
    is_verified = models.BooleanField(default=False, db_index=True)  # effective "can sell" flag, set by the verification service

    class VerificationStatus(models.TextChoices):
        UNSUBMITTED = 'unsubmitted', 'Not submitted for review'
        PENDING = 'pending', 'Under review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        SUSPENDED = 'suspended', 'Suspended'

    verification_status = models.CharField(
        max_length=12,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNSUBMITTED,
        db_index=True,
        help_text='Workflow state of the seller verification review.',
    )
    verification_requested_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text='Admin feedback shown to the seller when a submission is rejected.')
    reviewed_by = models.ForeignKey(
        'auth.User', null=True, blank=True, related_name='seller_reviews_done',
        on_delete=models.SET_NULL, help_text='Admin who last reviewed this seller.',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        help_text='Platform commission for this seller (e.g. 0.10 = 10%). '
                  'Leave empty to use the marketplace default.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    profile_picture = models.ImageField(upload_to='seller_profiles/', null=True, blank=True, validators=[validate_image_file])
    slug = models.SlugField(unique=True, blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

  
    def update_rating(self):
        from reviews.models import SellerReview
        avg = SellerReview.objects.filter(seller_profile=self).aggregate(avg_rating=Avg('rating'))['avg_rating']
        self.rating = round(avg or 0.00, 2)
        self.save()

      
    def reviews_count(self):
        return self.seller_reviews.count()

    def composite_score(self):
        import math
        return round((self.rating or 0) * math.log(self.reviews_count() + 1), 2)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.shop_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_name} ({self.user.username}'s Seller Profile)"
    








class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    profile_picture = models.ImageField(upload_to='customer_profiles/', null=True, blank=True, validators=[validate_image_file])
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class SellerDocument(models.Model):
    """A document uploaded by a seller as part of KYC / business verification."""

    class DocumentType(models.TextChoices):
        GST_CERTIFICATE = 'gst_certificate', 'GST certificate'
        BUSINESS_PROOF = 'business_proof', 'Business registration proof'
        ID_PROOF = 'id_proof', 'Owner ID proof'
        BANK_PROOF = 'bank_proof', 'Bank account proof'
        ADDRESS_PROOF = 'address_proof', 'Business address proof'
        OTHER = 'other', 'Other'

    seller_profile = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='documents',
    )
    document_type = models.CharField(
        max_length=20, choices=DocumentType.choices, default=DocumentType.OTHER,
    )
    file = models.FileField(upload_to='seller_documents/', validators=[validate_document_file])
    description = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-uploaded_at',)

    def __str__(self):
        return f'{self.get_document_type_display()} — {self.seller_profile.shop_name}'
