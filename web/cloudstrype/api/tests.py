from django.test import TestCase
from django.test import Client


class TestAPI(TestCase):
    def setUp(self):
        self.client = Client()

    def test_api(self):
        pass
