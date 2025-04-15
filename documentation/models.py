# in documentation/models.py
from django.db import models
from django.utils.text import slugify
from ckeditor.fields import RichTextField

class DocumentationSection(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    
    icon = models.CharField(max_length=20, blank=True, help_text="Example: 📘 or 🛠️")
    content = RichTextField(blank=True) 
    image = models.ImageField(upload_to='documentation_images/', null=True, blank=True)
    # In Django model

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

