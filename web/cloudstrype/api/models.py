from django.conf import settings
from django.db import models

from cloudstrype.main.models import User


class Token(models.Model):
    """
    Autentication token.
    """

    token = models.TextField()


class Provider(models.Model):
    """
    OAuth providers.

    OAuth providers that users can authorize us to access.
    """

    token = models.ForeignKey(Token, related_name='apptoken',
                              verbose_name='Application token')
    name = models.CharField(null=False, unique=True, max_length=32)


class UserToken(models.Model):
    """
    Store OAuth tokens.

    OAuth tokens obtained when a user authorized us to access their account.
    """

    class Meta:
        unique_together = ('user', 'provider')

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    provider = models.ForeignKey(Provider)
    token = models.ForeignKey(Token, related_name='clitoken',
                              verbose_name='OAuth client token')
