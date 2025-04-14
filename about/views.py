
# Create your views here.
# about/views.py

from django.shortcuts import render
from .models import AboutSection, TeamMember

def about_view(request):
    sections = AboutSection.objects.all()
    team = TeamMember.objects.all()
    return render(request, 'about/about.html', {
        'sections': sections,
        'team': team
    })


