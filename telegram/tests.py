from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from telegram.notifications import send_telegram_message


class TelegramViewsTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse('telegram:health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'service': 'telegram'})


class TelegramNotificationTests(TestCase):
    @override_settings(TELEGRAM_BOT_TOKEN='token')
    @patch('telegram.notifications.requests.post')
    def test_send_telegram_message_retries_and_succeeds(self, mocked_post):
        fail = Mock(status_code=500, text='err')
        ok = Mock(status_code=200, text='ok')
        mocked_post.side_effect = [fail, ok]

        sent = send_telegram_message('123', 'hello')

        self.assertTrue(sent)
        self.assertEqual(mocked_post.call_count, 2)
