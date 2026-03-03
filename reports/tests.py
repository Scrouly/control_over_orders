from django.test import TestCase
from django.urls import reverse


class ReportViewsTests(TestCase):
    def test_deadline_filter_invalid_date_shows_error(self):
        response = self.client.get(reverse('reports:deadline_filter'), {'deadline': 'invalid-date'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error'], 'Неверный формат даты.')
