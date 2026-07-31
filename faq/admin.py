from django.contrib import admin
from .models import FAQ, Story


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'created_at']
    search_fields = ['question', 'answer']
    date_hierarchy = 'created_at'


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_at']
    search_fields = ['title', 'description']
    date_hierarchy = 'created_at'
