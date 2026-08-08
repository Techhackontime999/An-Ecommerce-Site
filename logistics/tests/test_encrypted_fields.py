from django.db import connection
from django.test import TestCase

from logistics.models import CourierCompany


class EncryptedCredentialsTests(TestCase):
    def setUp(self):
        self.company = CourierCompany.objects.create(
            name='Secure Courier',
            code='secure',
            api_key='secret-key-123',
            api_secret='topsecret-456',
        )

    def _raw_column(self, column):
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT {column} FROM logistics_couriercompany WHERE id = %s',
                [self.company.id],
            )
            return cursor.fetchone()[0]

    def test_plaintext_round_trip(self):
        self.company.refresh_from_db()
        self.assertEqual(self.company.api_key, 'secret-key-123')
        self.assertEqual(self.company.api_secret, 'topsecret-456')

    def test_database_stores_ciphertext(self):
        raw_key = self._raw_column('api_key')
        raw_secret = self._raw_column('api_secret')
        self.assertNotEqual(raw_key, 'secret-key-123')
        self.assertNotEqual(raw_secret, 'topsecret-456')
        self.assertNotIn('secret-key-123', raw_key)
        self.assertNotIn('topsecret-456', raw_secret)
        self.assertTrue(raw_key.startswith('gAAAA'))
        self.assertTrue(raw_secret.startswith('gAAAA'))

    def test_blank_values_stay_blank(self):
        blank = CourierCompany.objects.create(name='Blank', code='blank')
        blank.refresh_from_db()
        self.assertEqual(blank.api_key, '')
        self.assertEqual(blank.api_secret, '')
