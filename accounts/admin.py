from django import forms
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from core.admin_actions import export_as_csv_action
from accounts.verification import approve_verification, reject_verification, suspend_verification
from .models import SellerProfile, CustomerProfile, SellerDocument


class SellerDocumentAdminForm(forms.ModelForm):
    """Plain FileInput so admin forms never expose the raw public media URL for
    a KYC document — access always goes through the authenticated view."""

    class Meta:
        model = SellerDocument
        fields = '__all__'
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.txt'}),
        }


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    actions = BaseUserAdmin.actions + (export_as_csv_action(
        description='Export selected users as CSV',
        fields=['id', 'username', 'first_name', 'last_name', 'email',
                'is_staff', 'is_superuser', 'is_active', 'date_joined', 'last_login'],
    ),)


class SellerDocumentInline(admin.TabularInline):
    model = SellerDocument
    form = SellerDocumentAdminForm
    extra = 0
    readonly_fields = ['uploaded_at', 'view_link']

    @admin.display(description='File')
    def view_link(self, obj):
        if obj is None or obj.pk is None:
            return ''
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">View</a>',
            reverse('accounts:seller_document', args=[obj.pk]),
        )


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ['shop_name', 'user', 'phone', 'is_verified', 'verification_status', 'created_at']
    search_fields = ['shop_name', 'user__username', 'phone', 'account_holder_name', 'ifsc_code']
    list_filter = ['is_verified', 'verification_status', 'created_at']
    list_select_related = ['user']
    date_hierarchy = 'created_at'
    readonly_fields = [
        'verification_status', 'verification_requested_at', 'verified_at',
        'rejected_at', 'reviewed_by', 'reviewed_at', 'created_at',
    ]
    inlines = [SellerDocumentInline]
    actions = ['approve_verification', 'reject_verification', 'suspend_verification']

    def approve_verification(self, request, queryset):
        for profile in queryset:
            approve_verification(profile, reviewer=request.user)
        self.message_user(request, f'{queryset.count()} seller(s) approved.')
    approve_verification.short_description = 'Approve selected sellers (manual review)'

    def reject_verification(self, request, queryset):
        """Reject with a required reason shown to the seller."""
        if 'apply' in request.POST:
            reason = (request.POST.get('reason') or '').strip()
            if not reason:
                self.message_user(request, 'A rejection reason is required.', level='error')
                return self._reject_page(request, queryset)
            for profile in queryset:
                reject_verification(profile, reviewer=request.user, reason=reason)
            self.message_user(request, f'{queryset.count()} seller(s) rejected.')
            return None
        return self._reject_page(request, queryset)
    reject_verification.short_description = 'Reject selected sellers (with reason)'

    def suspend_verification(self, request, queryset):
        if 'apply' in request.POST:
            reason = (request.POST.get('reason') or '').strip()
            if not reason:
                self.message_user(request, 'A suspension reason is required.', level='error')
                return self._suspend_page(request, queryset)
            for profile in queryset:
                suspend_verification(profile, reviewer=request.user, reason=reason)
            self.message_user(request, f'{queryset.count()} seller(s) suspended.')
            return None
        return self._suspend_page(request, queryset)
    suspend_verification.short_description = 'Suspend selected sellers (with reason)'

    def _reject_page(self, request, queryset):
        return self._reason_page(request, queryset, 'reject')

    def _suspend_page(self, request, queryset):
        return self._reason_page(request, queryset, 'suspend')

    def _reason_page(self, request, queryset, mode):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Reject seller verification' if mode == 'reject' else 'Suspend seller',
            'queryset': queryset,
            'action': 'reject_verification' if mode == 'reject' else 'suspend_verification',
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'mode': mode,
            'opts': self.model._meta,
            'media': self.media,
        }
        request.current_app = self.admin_site.name
        return render(request, 'admin/reject_verification.html', context)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'address']
    search_fields = ['user__username', 'phone', 'address']
    list_select_related = ['user']


@admin.register(SellerDocument)
class SellerDocumentAdmin(admin.ModelAdmin):
    form = SellerDocumentAdminForm
    list_display = ['seller_profile', 'document_type', 'view_link', 'uploaded_at']
    list_filter = ['document_type', 'uploaded_at']
    search_fields = ['seller_profile__shop_name', 'seller_profile__user__username', 'description']
    list_select_related = ['seller_profile']

    @admin.display(description='File')
    def view_link(self, obj):
        if obj is None or obj.pk is None:
            return ''
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">View</a>',
            reverse('accounts:seller_document', args=[obj.pk]),
        )
