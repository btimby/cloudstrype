from django.db import models
from django.contrib.auth.base_user import (
    AbstractBaseUser, BaseUserManager
)
from django.contrib.postgres.fields import JSONField

from allauth.socialaccount.models import SocialApp

from main import forms


class UserManager(BaseUserManager):
    def create_user(self, email, password=None):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(email=self.normalize_email(email))


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


class Provider(models.Model):
    """
    Storage provider.

    Represents a storage provider (cloud). Basically this model will represent
    the list of providers the user can "add" to their account.
    """

    PROVIDER_DROPBOX = 1
    PROVIDER_BOX = 2
    PROVIDER_ONEDRIVE = 3
    PROVIDER_S3 = 4
    PROVIDER_GOOGLE = 5
    PROVIDER_OWNCLOUD = 6
    PROVIDER_WEBDAV = 7
    PROVIDER_FTP = 8
    PROVIDER_DESKTOP_ARRAY = 9

    PROVIDER_NAMES = {
        PROVIDER_DROPBOX: 'Dropbox',
        PROVIDER_BOX: 'Box',
        PROVIDER_ONEDRIVE: 'Onedrive',
        PROVIDER_S3: 'S3',
        PROVIDER_GOOGLE: 'Google Drive',
        PROVIDER_OWNCLOUD: 'ownCloud',
        PROVIDER_WEBDAV: 'WebDAV',
        PROVIDER_FTP: 'FTP',
        PROVIDER_DESKTOP_ARRAY: 'Desktop Array',
    }

    PROVIDER_FORMS = {
        PROVIDER_DROPBOX: forms.OAuthForm,
        PROVIDER_BOX: forms.OAuthForm,
        PROVIDER_ONEDRIVE: forms.OAuthForm,
        PROVIDER_S3: forms.S3Form,
        PROVIDER_GOOGLE: forms.OAuthForm,
        PROVIDER_OWNCLOUD: forms.URLForm,
        PROVIDER_WEBDAV: forms.URLForm,
        PROVIDER_FTP: forms.URLForm,
        PROVIDER_DESKTOP_ARRAY: forms.DesktopArrayForm,
    }

    name = models.CharField(unique=True, max_length=32)
    type = models.SmallIntegerField(null=False, choices=PROVIDER_NAMES.items())

    def get_form(self, request):
        form = self.PROVIDER_FORMS.get(self.type)
        return form(request)


class ProviderOAuth(models.Model):
    provider = models.OneToOneField(Provider)
    socialapp = models.ForeignKey(SocialApp)


class Storage(models.Model):
    """
    Storage.

    Represents a user's account on a storage provider. Contains the information
    necessary to connect to a storage provider on a user's behalf.
    """
    provider = models.ForeignKey(Provider, related_name='instances')
    user = models.ForeignKey(User, related_name='storage')
    name = models.CharField(unique=True, max_length=32)
    # Contains connection details obtained via Provider.get_form()
    connection = JSONField()

