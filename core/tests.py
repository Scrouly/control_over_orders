from django.test import TestCase
from django.urls import reverse


class CoreAccessTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
