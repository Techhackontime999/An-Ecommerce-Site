from django.db import models
from ckeditor.fields import RichTextField

class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = RichTextField() 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ['-created_at']

    def __str__(self):
        return self.question

class Story(models.Model):
    title = models.CharField(max_length=200)
    description = RichTextField() 
    image = models.ImageField(upload_to='stories/', blank=True, null=True)
    url = models.URLField(blank=True, help_text="Optional: Link to full story, YouTube video, or article")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title