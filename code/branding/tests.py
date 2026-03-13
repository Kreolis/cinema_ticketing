from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from branding.models import Branding, clear_active_branding_cache, get_active_branding


class ActiveBrandingCacheTests(TestCase):
	def setUp(self):
		clear_active_branding_cache()

	def tearDown(self):
		clear_active_branding_cache()

	def test_get_active_branding_uses_cache_after_first_lookup(self):
		branding = Branding.objects.create(name='Active Branding', is_active=True)

		with CaptureQueriesContext(connection) as first_lookup:
			first_result = get_active_branding()

		with CaptureQueriesContext(connection) as second_lookup:
			second_result = get_active_branding()

		self.assertEqual(first_result.pk, branding.pk)
		self.assertEqual(second_result.pk, branding.pk)
		self.assertGreater(len(first_lookup), 0)
		self.assertEqual(len(second_lookup), 0)

	def test_get_active_branding_cache_is_invalidated_when_active_branding_changes(self):
		first_branding = Branding.objects.create(name='First Branding', is_active=True)
		self.assertEqual(get_active_branding().pk, first_branding.pk)

		second_branding = Branding.objects.create(name='Second Branding', is_active=True)

		active_branding = get_active_branding()
		self.assertEqual(active_branding.pk, second_branding.pk)
		self.assertFalse(Branding.objects.get(pk=first_branding.pk).is_active)
