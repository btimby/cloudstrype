from django.test import TestCase, Client
from django.urls import reverse


class APITestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_cloud_list(self):
        r = self.client.get(reverse('api:clouds') + '?format=json')
        self.assertEqual(200, r.status_code)
