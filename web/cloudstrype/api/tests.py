from django.test import TestCase
from django.urls import reverse


class APITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        pass

    def test_cloud_list(self):
        r = self.client.get(reverse('api:clouds') + '?format=json')
        self.assertEqual(200, r.status_code)
