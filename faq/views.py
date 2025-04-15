from django.shortcuts import render
from .models import FAQ
from .models import Story
def faq_view(request):
    faqs = FAQ.objects.all()
    stories = Story.objects.all()  # Assuming a Story model exists
    return render(request, 'faq/faq.html', {'faqs': faqs ,'stories': stories})
