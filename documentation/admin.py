from django.contrib import admin
from .models import DocumentationSection


@admin.register(DocumentationSection)
class DocumentationSectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'content_preview']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}

    def content_preview(self, obj):
        return obj.content[:75] + '...' if len(obj.content) > 75 else obj.content
    content_preview.short_description = 'Content'
