from django.contrib import admin

from .models import NewsItem


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'is_published', 'is_pinned', 'publish_at', 'author')
    list_filter = ('kind', 'is_published', 'is_pinned')
    list_editable = ('is_published', 'is_pinned')
    search_fields = ('title', 'body', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'publish_at'
    readonly_fields = ('created', 'updated')
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'kind', 'body', 'excerpt'),
        }),
        ('Publishing', {
            'fields': ('author', 'is_published', 'is_pinned', 'publish_at', 'expires_at'),
        }),
        ('Metadata', {
            'fields': ('created', 'updated'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)
