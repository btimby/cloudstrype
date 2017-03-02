from django.test import UnitTest
from django.test import Client


class TestAPI(UnitTest):
    def setUp(self):
        self.client = Client()

    def test_api(self):
        pass
