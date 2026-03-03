from django.test import TestCase
from django.urls import reverse


class ReferencesAccessTests(TestCase):
    def test_departments_requires_login(self):
        response = self.client.get(reverse('references:departments'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
