"""Seller verification workflow.

A new seller starts *unverified*. They submit their KYC / business documents,
an admin reviews them, and only an explicit approval flips ``is_verified`` on.

Every transition here keeps ``is_verified`` in sync with ``verification_status``
and notifies the affected users so the state machine is the single source of
truth — nothing should write either field directly.
"""

import logging

from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse

from .models import SellerProfile

logger = logging.getLogger(__name__)


def _notify(user, category, title, message, link='', icon='store'):
    from notifications.models import Notification
    from notifications.services import notify
    notify(user, category, title, message, link=link, icon=icon)


def _notify_reviewers(title, message):
    """Notify all staff so an unclaimed submission never waits silently."""
    staff = User.objects.filter(is_staff=True)
    for user in staff:
        _notify(
            user,
            'account',
            title,
            message,
            link=reverse('admin:accounts_sellerprofile_changelist'),
            icon='clipboard-check',
        )


def submit_for_verification(seller, *, actor=None):
    """Seller asks an admin to review their account.

    Returns (ok, detail). Requires email + phone verification to discourage
    fake submissions, but never auto-verifies.
    """
    if seller.verification_status == SellerProfile.VerificationStatus.APPROVED:
        return True, 'already_approved'
    if seller.verification_status == SellerProfile.VerificationStatus.PENDING:
        return True, 'already_pending'
    if not seller.is_email_verified or not seller.is_phone_verified:
        return False, 'verify_contact_first'

    seller.verification_status = SellerProfile.VerificationStatus.PENDING
    seller.is_verified = False
    seller.verification_requested_at = timezone.now()
    seller.rejection_reason = ''
    seller.save(update_fields=[
        'verification_status', 'is_verified', 'verification_requested_at',
        'rejection_reason', 'reviewed_by', 'reviewed_at',
    ])

    _notify(
        seller.user,
        'account',
        'Verification submitted',
        'Your seller verification is now under review. You will be notified once an admin reviews it.',
        link=reverse('seller:verification'),
    )
    _notify_reviewers(
        'Seller verification request',
        f'{seller.shop_name} ({seller.user.username}) has submitted their business documents for review.',
    )
    return True, 'submitted'


def approve_verification(seller, *, reviewer=None, note=''):
    """Approve a seller after reviewing their documents — the only way a
    seller becomes ``is_verified``."""
    seller.verification_status = SellerProfile.VerificationStatus.APPROVED
    seller.is_verified = True
    seller.verified_at = timezone.now()
    seller.rejected_at = None
    seller.rejection_reason = ''
    seller.reviewed_by = reviewer
    seller.reviewed_at = timezone.now()
    seller.save(update_fields=[
        'verification_status', 'is_verified', 'verified_at', 'rejected_at',
        'rejection_reason', 'reviewed_by', 'reviewed_at',
    ])
    _notify(
        seller.user,
        'account',
        'You are approved to sell!',
        f'Your seller verification was approved. You can now add products and start selling on Shop-Seed.'
        + (f' {note}' if note else ''),
        link=reverse('seller:seller_dashboard'),
    )
    return seller


def reject_verification(seller, *, reviewer=None, reason=''):
    """Reject a submission. A reason is required so the seller can fix it and
    resubmit. Rejection never verifies the seller."""
    if not reason:
        reason = 'Your submitted documents could not be verified. Please review the requirements and resubmit.'
    seller.verification_status = SellerProfile.VerificationStatus.REJECTED
    seller.is_verified = False
    seller.rejected_at = timezone.now()
    seller.rejection_reason = reason
    seller.reviewed_by = reviewer
    seller.reviewed_at = timezone.now()
    seller.save(update_fields=[
        'verification_status', 'is_verified', 'rejected_at', 'rejection_reason',
        'reviewed_by', 'reviewed_at',
    ])
    _notify(
        seller.user,
        'account',
        'Seller verification was not approved',
        reason,
        link=reverse('seller:verification'),
    )
    return seller


def suspend_verification(seller, *, reviewer=None, reason=''):
    """Revoke an already-approved seller (fraud, policy violation)."""
    if not reason:
        reason = 'Your selling privileges have been suspended.'
    seller.verification_status = SellerProfile.VerificationStatus.SUSPENDED
    seller.is_verified = False
    seller.reviewed_by = reviewer
    seller.reviewed_at = timezone.now()
    seller.save(update_fields=[
        'verification_status', 'is_verified', 'reviewed_by', 'reviewed_at',
    ])
    _notify(
        seller.user,
        'account',
        'Your selling account has been suspended',
        reason,
        link=reverse('seller:verification'),
    )
    return seller
