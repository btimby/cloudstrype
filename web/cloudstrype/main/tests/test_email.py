from django.core import mail
from django.test import TestCase

from main.email import send_mail


class EmailTest(TestCase):
    def test_send_email(self):
        # Raise ValueError when template is missing.
        with self.assertRaises(ValueError):
            send_mail('bad-name', 'Subject', 'foo@bar.org')

        send_mail('test1', 'Subject', 'foo@bar.org')
        self.assertEqual(1, len(mail.outbox))

        # Should work when missing html, and also when template has .text
        # extension rather than .txt.
        send_mail('test2', 'Subject', 'foo@bar.org')
        self.assertEqual(2, len(mail.outbox))
