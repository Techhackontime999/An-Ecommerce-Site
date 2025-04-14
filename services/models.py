
# Create your models here.
from django.db import models
from ckeditor.fields import RichTextField

class Service(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    details = RichTextField() 
    image = models.ImageField(upload_to='services/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
