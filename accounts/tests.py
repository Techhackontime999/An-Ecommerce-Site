from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CustomerProfile, SellerDocument, SellerProfile
from .security import failure_count, is_locked
from .verification import (
    approve_verification,
    reject_verification,
    submit_for_verification,
    suspend_verification,
)
from .views import _hash_otp, send_phone_otp


class LoginSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='alice', password='pass1234')
        self.client = Client(SERVER_NAME='localhost')
        self.login_url = reverse('accounts:login')

    def test_successful_login_resets_failure_counters(self):
        self.client.post(self.login_url, {'username': 'alice', 'password': 'wrong'})
        self.assertEqual(failure_count('login-username', 'alice'), 1)
        response = self.client.post(self.login_url, {'username': 'alice', 'password': 'pass1234'})
        self.assertRedirects(response, reverse('shop:product_list'), fetch_redirect_response=False)
        self.assertEqual(failure_count('login-username', 'alice'), 0)

    def test_account_locks_after_five_failures(self):
        locked = get_user_model().objects.create_user(username='alice-locked', password='pass1234')
        for _ in range(5):
            self.client.post(self.login_url, {'username': 'alice-locked', 'password': 'wrong'})
        self.assertTrue(is_locked('login-username', 'alice-locked'))
        # Even a correct password is rejected while the account is locked.
        response = self.client.post(self.login_url, {'username': 'alice-locked', 'password': 'pass1234'})
        self.assertTrue(response.context['user'].is_anonymous)

    def test_open_redirect_rejected_on_login(self):
        CustomerProfile.objects.create(
            user=self.user, phone='9999999999', address='x',
            is_email_verified=True, is_phone_verified=True,
        )
        response = self.client.post(
            self.login_url,
            {'username': 'alice', 'password': 'pass1234', 'next': 'https://evil.com/phish'},
        )
        self.assertRedirects(response, reverse('shop:product_list'), fetch_redirect_response=False)
        self.assertNotIn('evil.com', response.url)

    def test_same_host_next_allowed_on_login(self):
        CustomerProfile.objects.create(
            user=self.user, phone='9999999999', address='x',
            is_email_verified=True, is_phone_verified=True,
        )
        response = self.client.post(
            self.login_url,
            {'username': 'alice', 'password': 'pass1234', 'next': '/products/'},
        )
        self.assertEqual(response.url, '/products/')


class PhoneOtpTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='bob', password='pass1234')
        self.profile = CustomerProfile.objects.create(user=self.user, phone='9999999999', address='x')
        self.client = Client(SERVER_NAME='localhost')
        self.verify_url = reverse('accounts:verify_phone')
        self._set_pending()

    def _set_pending(self):
        session = self.client.session
        session['pending_verify_user_id'] = self.user.id
        session.save()

    def _seed_otp(self, otp='123456', expiry_delta=300, attempts=0):
        session = self.client.session
        session['phone_otp_hash'] = _hash_otp(otp)
        session['phone_otp_expiry'] = timezone.now().timestamp() + expiry_delta
        session['phone_otp_attempts'] = attempts
        session['phone_otp_last_sent'] = timezone.now().timestamp()
        session['phone_otp_resend_count'] = 0
        session.save()

    def test_correct_otp_verifies_phone(self):
        self._seed_otp()
        response = self.client.post(self.verify_url, {'otp': '123456'})
        self.assertRedirects(response, reverse('accounts:verify'), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_phone_verified)
        self.assertNotIn('phone_otp_hash', self.client.session)

    def test_wrong_otp_increments_attempts(self):
        self._seed_otp()
        self.client.post(self.verify_url, {'otp': '000000'})
        self.assertEqual(self.client.session['phone_otp_attempts'], 1)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_phone_verified)

    def test_expired_otp_is_rejected(self):
        self._seed_otp(expiry_delta=-1)
        response = self.client.post(self.verify_url, {'otp': '123456'})
        self.assertContains(response, 'Invalid or expired')
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_phone_verified)

    def test_max_attempts_burns_the_code(self):
        self._seed_otp(attempts=4)
        response = self.client.post(self.verify_url, {'otp': '000000'})
        self.assertContains(response, 'Too many incorrect codes')
        self.assertNotIn('phone_otp_hash', self.client.session)
        self.client.post(self.verify_url, {'otp': '123456'})
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_phone_verified)

    @mock.patch('accounts.views.secrets.randbelow', return_value=424242)
    def test_send_otp_stores_hash_not_plaintext(self, _randbelow):
        from django.contrib.sessions.backends.db import SessionStore
        request = RequestFactory().post(self.verify_url)
        request.session = SessionStore()
        send_phone_otp(request, self.user)
        self.assertNotIn('424242', request.session['phone_otp_hash'])
        self.assertIn('phone_otp_expiry', request.session)

    def test_resend_otp_respects_cooldown(self):
        session = self.client.session
        session['phone_otp_last_sent'] = timezone.now().timestamp()
        session['phone_otp_resend_count'] = 0
        session.save()
        response = self.client.get(reverse('accounts:resend_otp'))
        self.assertRedirects(response, reverse('accounts:verify_phone'), fetch_redirect_response=False)

    def test_resend_otp_limited_to_three(self):
        session = self.client.session
        session['phone_otp_last_sent'] = timezone.now().timestamp() - 120
        session['phone_otp_resend_count'] = 3
        session.save()
        response = self.client.get(reverse('accounts:resend_otp'))
        self.assertRedirects(response, reverse('accounts:verify_phone'), fetch_redirect_response=False)


def make_seller(**overrides):
    user = get_user_model().objects.create_user(username='seller_' + str(get_user_model().objects.count()),
                                                password='pass1234')
    defaults = {
        'user': user,
        'shop_name': 'Test Shop',
        'bank_account': '123456789',
        'account_holder_name': 'Seller',
        'ifsc_code': 'HDFC0001234',
        'phone': '9999999999',
        'address': 'Test address',
        'is_email_verified': True,
        'is_phone_verified': True,
    }
    defaults.update(overrides)
    return SellerProfile.objects.create(**defaults)


class SellerVerificationTests(TestCase):
    """The core guarantee: a seller is never verified unless an admin approves."""

    def test_new_seller_profile_is_not_verified(self):
        profile = make_seller()
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.UNSUBMITTED)

    def test_submit_requires_contact_verified(self):
        profile = make_seller(is_email_verified=False, is_phone_verified=False)
        ok, detail = submit_for_verification(profile)
        self.assertFalse(ok)
        self.assertEqual(detail, 'verify_contact_first')
        profile.refresh_from_db()
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.UNSUBMITTED)

    def test_submit_sets_pending_but_not_verified(self):
        profile = make_seller()
        ok, detail = submit_for_verification(profile)
        self.assertTrue(ok)
        self.assertEqual(detail, 'submitted')
        profile.refresh_from_db()
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.PENDING)
        self.assertFalse(profile.is_verified)
        self.assertIsNotNone(profile.verification_requested_at)

    def test_approve_is_only_way_to_become_verified(self):
        profile = make_seller()
        approve_verification(profile, reviewer=get_user_model().objects.create_user(username='admin1'))
        profile.refresh_from_db()
        self.assertTrue(profile.is_verified)
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.APPROVED)
        self.assertIsNotNone(profile.verified_at)

    def test_reject_keeps_seller_unverified_with_reason(self):
        profile = make_seller()
        reviewer = get_user_model().objects.create_user(username='admin2', is_staff=True)
        reject_verification(profile, reviewer=reviewer, reason='GST certificate illegible.')
        profile.refresh_from_db()
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.REJECTED)
        self.assertEqual(profile.rejection_reason, 'GST certificate illegible.')
        self.assertEqual(profile.reviewed_by, reviewer)

    def test_reject_always_sets_a_reason(self):
        profile = make_seller()
        reject_verification(profile, reason='')
        profile.refresh_from_db()
        self.assertTrue(profile.rejection_reason)

    def test_suspend_revokes_an_approved_seller(self):
        profile = make_seller()
        approve_verification(profile)
        self.assertTrue(profile.is_verified)
        suspend_verification(profile, reason='Chargeback fraud.')
        profile.refresh_from_db()
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.SUSPENDED)

    def test_dashboard_gate_blocks_unverified_seller(self):
        from django.contrib.auth.models import Group
        user = get_user_model().objects.create_user(username='seller_dash', password='pass1234')
        SellerProfile.objects.create(
            user=user, shop_name='Shop', bank_account='1', account_holder_name='A',
            ifsc_code='HDFC0001234', phone='9999999999', address='x',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('seller:seller_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not approved')

    def test_seller_verification_page_uploads_document(self):
        user = get_user_model().objects.create_user(username='seller_doc', password='pass1234')
        SellerProfile.objects.create(
            user=user, shop_name='Doc Shop', bank_account='1', account_holder_name='A',
            ifsc_code='HDFC0001234', phone='9999999999', address='x',
        )
        self.client.force_login(user)
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile('gst.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        response = self.client.post(
            reverse('seller:verification'),
            {'document_type': 'gst_certificate', 'file': upload, 'description': 'GST cert'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SellerDocument.objects.filter(description='GST cert').exists())

    def test_seller_verification_page_submit_for_review(self):
        profile = make_seller()
        self.client.force_login(profile.user)
        response = self.client.post(reverse('seller:verification'), {'action': 'submit'})
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.PENDING)

    def test_admin_approve_action_verifies_seller(self):
        admin = get_user_model().objects.create_user(username='super', password='pass1234', is_superuser=True, is_staff=True)
        self.client.force_login(admin)
        profile = make_seller()
        url = reverse('admin:accounts_sellerprofile_changelist')
        data = {'action': 'approve_verification', '_selected_action': [str(profile.pk)]}
        response = self.client.post(url, data)
        self.assertRedirects(response, url, fetch_redirect_response=False)
        profile.refresh_from_db()
        self.assertTrue(profile.is_verified)

    def test_admin_reject_action_requires_reason(self):
        admin = get_user_model().objects.create_user(username='super2', password='pass1234', is_superuser=True, is_staff=True)
        self.client.force_login(admin)
        profile = make_seller()
        url = reverse('admin:accounts_sellerprofile_changelist')
        # First POST selects the action (shows the intermediate page).
        response = self.client.post(url, {'action': 'reject_verification', '_selected_action': [str(profile.pk)]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reason')
        # No reason -> rejected.
        response = self.client.post(
            url,
            {'action': 'reject_verification', 'apply': 'yes', '_selected_action': [str(profile.pk)], 'reason': ''},
        )
        profile.refresh_from_db()
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.UNSUBMITTED)
        # With a reason -> rejected.
        response = self.client.post(
            url,
            {'action': 'reject_verification', 'apply': 'yes', '_selected_action': [str(profile.pk)], 'reason': 'Bad docs'},
        )
        self.assertRedirects(response, url, fetch_redirect_response=False)
        profile.refresh_from_db()
        self.assertEqual(profile.verification_status, SellerProfile.VerificationStatus.REJECTED)
        self.assertFalse(profile.is_verified)
