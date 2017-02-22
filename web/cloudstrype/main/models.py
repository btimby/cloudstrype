from django.db import models
from django.contrib.auth.base_user import (
    AbstractBaseUser, BaseUserManager
)
from django.contrib.postgres.fields import (
    JSONField, ArrayField
)


class UserManager(BaseUserManager):
    def create_user(self, email, **kwargs):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        password = kwargs.pop('password', None)
        user = self.model(email=self.normalize_email(email), **kwargs)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email and password.
        """
        user = self.create_user(email, password=password)
        user.is_admin = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """
    Custom user model.

    Created as placeholder for future expansion.
    """

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    uid = models.CharField(null=False, blank=False, unique=True,
                           max_length=255)
    email = models.EmailField(null=False, blank=False, unique=True,
                              max_length=255, verbose_name='email address')
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = UserManager()

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        return self.is_admin


class OAuth2Provider(models.Model):
    """
    A storage provider or login provider that supports OAuth2.
    """

    class Meta:
        verbose_name = 'OAuth2 Provider'
        verbose_name_plural = 'OAuth2 Providers'

    name = models.CharField(null=False, unique=True, max_length=32)
    client_id = models.TextField(null=False)
    client_secret = models.TextField()
    authorization_url = models.URLField(null=False, max_length=255)
    access_token_url = models.URLField(null=False, max_length=255)
    user_profile_url = models.URLField(null=False, max_length=255)
    scope = ArrayField(models.CharField(max_length=32), null=True, blank=True)
    fields = JSONField(null=True, blank=True)

    def __str__(self):
        return 'OAuth2 Provider: %s' % self.name



class OAuth2AccessToken(models.Model):
    """
    An access token obtain for a user from a provider.
    """

    class Meta:
        verbose_name = 'OAuth2 Access Token'
        verbose_name_plural = 'OAuth2 Access Tokens'
        unique_together = ('provider', 'user')

    provider = models.ForeignKey(OAuth2Provider, related_name='tokens')
    user = models.ForeignKey(User, related_name='tokens')
    access_token = models.TextField()
    refresh_token = models.TextField(null=True)
    expires = models.DateTimeField(null=True)

    def __str__(self):
        return 'OAuth2 Access Token: %s - %s' % (self.user.email,
                                                 self.provider.name)
