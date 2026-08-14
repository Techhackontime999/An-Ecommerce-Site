from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import LoaderConfig
from .services import config_to_dict, get_config_dict, invalidate


class LoaderConfigModelTests(TestCase):
    def test_get_solo_creates_singleton(self):
        first = LoaderConfig.get_solo()
        second = LoaderConfig.get_solo()
        self.assertEqual(first.pk, 1)
        self.assertEqual(second.pk, 1)
        self.assertEqual(LoaderConfig.objects.count(), 1)

    def test_save_bumps_version(self):
        config = LoaderConfig.get_solo()
        version_before = config.version
        config.duration_ms = 2000
        config.save()
        config.refresh_from_db()
        self.assertGreater(config.version, version_before)

    def test_config_dict_shape(self):
        data = config_to_dict(LoaderConfig.get_solo())
        for key in ('version', 'enabled', 'initial_type', 'navigation_type',
                    'logo_text', 'background_color', 'accent_color',
                    'duration_ms', 'exit_animation', 'show_on',
                    'device_desktop', 'device_tablet', 'device_mobile',
                    'lightweight_mobile', 'respect_reduced_motion',
                    'network_fallback', 'skeleton_enabled'):
            self.assertIn(key, data)


class LoaderConfigEndpointTests(TestCase):
    def setUp(self):
        # The loader config is cached; clear it so tests are order-independent.
        invalidate()

    def test_config_json_returns_defaults(self):
        response = self.client.get(reverse('loader:loader_config_json'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'max-age=300, public')
        data = response.json()
        self.assertTrue(data['enabled'])
        self.assertEqual(data['initial_type'], 'seed')
        self.assertEqual(data['navigation_type'], 'progress')

    def test_config_json_reflects_changes(self):
        config = LoaderConfig.get_solo()
        config.initial_type = 'logo'
        config.save()
        data = get_config_dict()
        self.assertEqual(data['initial_type'], 'logo')


class LoaderStudioAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='root', email='root@example.com', password='secret'
        )
        self.client.force_login(self.user)

    def test_studio_requires_superuser(self):
        self.client.logout()
        response = self.client.get(reverse('admin:loader_studio'))
        self.assertNotEqual(response.status_code, 200)

    def test_studio_page_renders(self):
        response = self.client.get(reverse('admin:loader_studio'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Loader Studio')

    def test_studio_save_updates_config(self):
        response = self.client.post(reverse('admin:loader_studio'), {
            'enabled': 'on',
            'initial_type': 'spinner',
            'navigation_type': 'logo',
            'logo_text': 'Shop-Seed',
            'background_color': '#111111',
            'accent_color': '#ff0000',
            'duration_ms': '1200',
            'exit_animation': 'zoom',
            'show_on': 'every_visit',
            'device_desktop': 'on',
            'device_tablet': 'on',
            'device_mobile': 'on',
        })
        self.assertEqual(response.status_code, 302)
        config = LoaderConfig.get_solo()
        self.assertEqual(config.initial_type, 'spinner')
        self.assertEqual(config.navigation_type, 'logo')
        self.assertEqual(config.duration_ms, 1200)
