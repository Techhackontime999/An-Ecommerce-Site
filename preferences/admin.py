from django.contrib import admin

from .models import UserPreference


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'language', 'currency', 'font_style', 'accent', 'text_size', 'updated_at']
    search_fields = ['user__username', 'user__email']
    list_filter = ['theme', 'language', 'currency', 'font_style', 'accent', 'text_size']
