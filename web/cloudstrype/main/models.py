from os.path import normpath, dirname
from os.path import join as pathjoin
from os.path import split as pathsplit

from django.contrib.auth.base_user import (
    AbstractBaseUser, BaseUserManager
)
from django.contrib.postgres.fields import (
    JSONField, ArrayField
)
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import Max
from django.db.models.query import QuerySet
from django.utils import timezone
from hashids import Hashids


HASHIDS = Hashids(min_length=24)


class UidQuerySet(QuerySet):
    """
    QuerySet with uid capabilities.

    Allow objects to be easily selected by uid.
    """

    @staticmethod
    def _args(kwargs):
        uid = kwargs.pop('uid', None)
        if uid:
            kwargs['id'] = HASHIDS.decode(uid)[0]

    def filter(self, *args, **kwargs):
        UidQuerySet._args(kwargs)
        return super().filter(*args, **kwargs)


class UidManagerMixin(object):
    """
    Mix in Uid capabilities for a Manager.

    A Model can use a custom manager with this mixin to gain uid capabilities.
    """

    def get_queryset(self):
        "Return UidQuerySet instance."
        return UidQuerySet(self.model, using=self._db)


class UidManager(UidManagerMixin, models.Manager):
    """
    Basic manager with Uid capabilities.

    A Model can use this Manager to add uid capabilities if it does not
    otherwise need a custom Manager.
    """

    pass


class UidModelMixin(object):
    """
    Mix in Uid capabilities for a Model.

    Adds a uid property and uses UidManager by default.
    """

    @property
    def uid(self):
        "Return a random-looking id."
        return HASHIDS.encode(self.id)

    objects = UidManager()


class UserManager(BaseUserManager):
    def create_user(self, email, **kwargs):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        password = kwargs.pop('password', None)
        if 'full_name' in kwargs:
            kwargs['full_name'] = kwargs['full_name'].title()
        user = self.model(email=self.normalize_email(email), **kwargs)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **kwargs):
        """
        Creates and saves a superuser with the given email and password.
        """
        return self.create_user(email, password=password, is_admin=True,
                                is_active=True, **kwargs)


class User(AbstractBaseUser):
    """
    Custom user model.

    Created as placeholder for future expansion.
    """

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    uid = models.CharField(null=False, blank=False, editable=False,
                           unique=True, max_length=255)
    email = models.EmailField(null=False, blank=False, unique=True,
                              max_length=255, verbose_name='email address')
    full_name = models.CharField(max_length=64)
    first_name = models.CharField(max_length=64, editable=False)
    last_name = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.full_name:
            self.first_name, _, self.last_name = self.full_name.partition(' ')
        if not self.uid:
            self.uid = self.email
        return super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name

    def __str__(self):
        return '<User: %s "%s">' % (self.email, self.full_name)

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

    def get_clients(self):
        clients = []
        for storage in OAuth2StorageToken.objects.filter(token__user=self):
            clients.append(storage.get_client())
        return clients

    def get_option(self, name, default=None):
        try:
            return getattr(self.options, name)
        except ObjectDoesNotExist:
            return default


class Option(models.Model):
    user = models.OneToOneField(User, related_name='options',
                                on_delete=models.CASCADE)
    replicas = models.SmallIntegerField(null=True, blank=True)
    attrs = JSONField()


class OAuth2Provider(UidModelMixin, models.Model):
    """
    A storage provider or login provider that supports OAuth2.
    """

    PROVIDER_DROPBOX = 1
    PROVIDER_ONEDRIVE = 2
    PROVIDER_BOX = 3
    PROVIDER_GDRIVE = 4
    PROVIDER_AMAZON = 5
    PROVIDER_SMARTFILE = 6

    PROVIDERS = {
        PROVIDER_DROPBOX: "Dropbox",
        PROVIDER_ONEDRIVE: "Onedrive",
        PROVIDER_BOX: "Box",
        PROVIDER_GDRIVE: "Google Drive",
        PROVIDER_AMAZON: "Amazon",
        PROVIDER_SMARTFILE: "SmartFile",
    }

    STORAGE_PROVIDERS = [
        PROVIDER_DROPBOX,
        PROVIDER_ONEDRIVE,
        PROVIDER_BOX,
        PROVIDER_GDRIVE,
        PROVIDER_SMARTFILE,
    ]

    class Meta:
        verbose_name = 'OAuth2 Provider'
        verbose_name_plural = 'OAuth2 Providers'

    provider = models.SmallIntegerField(null=False, choices=PROVIDERS.items())
    client_id = models.TextField(null=False)
    client_secret = models.TextField()

    @property
    def name(self):
        return self.PROVIDERS[self.provider]

    def __str__(self):
        return 'OAuth2 Provider: %s' % self.name

    def get_client(self, redirect_uri, **kwargs):
        from main.fs.cloud import OAuth2APIClient
        return OAuth2APIClient.get_client(self, redirect_uri=redirect_uri)

    @property
    def is_storage(self):
        return self.provider in self.STORAGE_PROVIDERS


class OAuth2AccessToken(UidModelMixin, models.Model):
    """
    An access token obtain for a user from a provider.
    """

    class Meta:
        verbose_name = 'OAuth2 Access Token'
        verbose_name_plural = 'OAuth2 Access Tokens'

    provider = models.ForeignKey(OAuth2Provider, related_name='tokens',
                                 on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='tokens',
                             on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True)
    expires = models.DateTimeField(null=True)

    def __str__(self):
        return 'OAuth2 Access Token: %s for %s' % (self.user.email,
                                                   self.provider.name)

    def get_client(self, **kwargs):
        from main.fs.cloud import OAuth2APIClient
        return OAuth2APIClient.get_client(self.provider, oauth_access=self,
                                          **kwargs)


class OAuth2LoginToken(UidModelMixin, models.Model):
    """
    Track tokens used for login vs. storage.
    """

    class Meta:
        verbose_name = 'OAuth2 Login Token'
        verbose_name_plural = 'OAuth2 Login Tokens'

    user = models.OneToOneField(User)
    token = models.ForeignKey(OAuth2AccessToken, on_delete=models.CASCADE)

    def __str__(self):
        return 'OAuth2 Login Token: %s for %s' % (self.user.email,
                                                  self.token.provider.name)


class OAuth2StorageToken(UidModelMixin, models.Model):
    """
    Track tokens used for storage vs. login.
    """

    class Meta:
        verbose_name = 'OAuth2 Storage Token'
        verbose_name_plural = 'OAuth2 Storage Tokens'

    user = models.ForeignKey(User, related_name='storage',
                             on_delete=models.CASCADE)
    token = models.OneToOneField(OAuth2AccessToken, on_delete=models.CASCADE)
    size = models.BigIntegerField(default=0)
    used = models.BigIntegerField(default=0)
    # Provider-specific attribute storage, such as chunk storage location
    # directory ID.
    attrs = JSONField(null=True, blank=True)

    def __str__(self):
        return 'OAuth2 Storage Token: %s for %s' % (self.user.email,
                                                    self.token.provider.name)

    def get_client(self):
        return self.token.get_client(oauth_storage=self)


class DirectoryQuerySet(UidQuerySet):
    """
    QuerySet for Directories.

    Allow filtering by full path or uid.
    """

    @staticmethod
    def _args(kwargs):
        """Convert path to name/parents."""
        UidQuerySet._args(kwargs)
        path = kwargs.pop('path', None)
        if path:
            parents = normpath(path).split('/')
            name = parents.pop()
            kwargs['name'] = name.lower()
            kwargs['display_name'] = name
            kwargs['display_path'] = path
            kwargs['parents'] = [p.lower() for p in parents]

    def filter(self, *args, **kwargs):
        """Filter objects using full path."""
        DirectoryQuerySet._args(kwargs)
        kwargs.pop('display_name', None)
        kwargs.pop('display_path', None)
        return super().filter(*args, **kwargs)


class DirectoryManager(models.Manager):
    """Manage Directory model."""

    def get_queryset(self):
        """
        Override default QuerySet.

        Allow filtering with full path.
        """
        return DirectoryQuerySet(self.model, using=self._db)

    def create(self, *args, **kwargs):
        path = kwargs.get('path', None)
        parent = dirname(path)
        if parent:
            if 'user' not in kwargs:
                raise ValueError('User required for directory creation')
            user = kwargs['user']
            kwargs['parent'], _ = Directory.objects.get_or_create(user=user,
                                                                  path=parent)
        DirectoryQuerySet._args(kwargs)
        return super().create(*args, **kwargs)

    def get_or_create(self, *args, **kwargs):  # noqa: D402
        """
        Override default get_or_create().

        Does not include display_name and display_path in the query portion,
        but ensures they are set to the requested values during save.
        """
        # It might be better to do this in save().
        DirectoryQuerySet._args(kwargs)
        display_name = kwargs.pop('display_name', None)
        display_path = kwargs.pop('display_path', None)
        obj, created = super().get_or_create(*args, **kwargs)
        if created:
            obj.display_name = display_name
            obj.display_path = display_path
        return obj, created


class Directory(UidModelMixin, models.Model):
    """
    Directory model.

    Represents a directory in the FS.
    """

    class Meta:
        unique_together = ('user', 'name', 'parents')

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', null=True, related_name='dirs',
                               on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=45)
    display_path = models.TextField()
    parents = ArrayField(models.CharField(max_length=45))
    tags = ArrayField(models.CharField(max_length=36), null=True)
    attrs = JSONField(null=True, blank=True)

    objects = DirectoryManager()

    def __str__(self):
        return '<Directory: %s>' % self.path

    @property
    def path(self):
        return '/%s' % self.display_path.lstrip('/')


class FileQuerySet(UidQuerySet):
    @staticmethod
    def _args(kwargs):
        path = kwargs.pop('path', None)
        if path:
            if 'user' not in kwargs:
                raise ValueError('User required for directory creation')
            user = kwargs['user']
            directory, kwargs['name'] = pathsplit(path)
            kwargs['directory'], _ = Directory.objects.get_or_create(
                user=user, path=directory)

    def filter(self, *args, **kwargs):
        FileQuerySet._args(kwargs)
        return super().filter(*args, **kwargs)


class FileManager(models.Manager):
    def get_queryset(self):
        """
        Override default QuerySet

        Allow filtering wth full path.
        """
        return FileQuerySet(self.model, using=self._db)

    def create(self, *args, **kwargs):
        FileQuerySet._args(kwargs)
        return super().create(*args, **kwargs)


class File(UidModelMixin, models.Model):
    """
    File model.

    Represents a file in the FS.
    """

    class Meta:
        unique_together = ('directory', 'name')

    user = models.ForeignKey(User, related_name='files',
                             on_delete=models.CASCADE)
    directory = models.ForeignKey(Directory, related_name='files',
                                  on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    size = models.IntegerField(default=0)
    md5 = models.CharField(max_length=32)
    sha1 = models.CharField(max_length=40)
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = ArrayField(models.CharField(max_length=36), null=True)
    attrs = JSONField(null=True, blank=True)

    objects = FileManager()

    def __str__(self):
        return '<File: %s>' % self.path

    @property
    def path(self):
        return pathjoin(self.directory.path, self.name)

    @transaction.atomic
    def add_chunk(self, chunk):
        "Adds a chunk to a file, taking care to set the serial number."
        fc = FileChunk(file=self, chunk=chunk)
        fc.serial = (FileChunk.objects.filter(file=self).aggregate(
            Max('serial'))['serial__max'] or 0) + 1
        fc.save()
        return fc


class Chunk(UidModelMixin, models.Model):
    """
    Chunk model.

    Represents a unique chunk of data.
    """

    file = models.ManyToManyField(to=File, through='FileChunk',
                                  related_name='chunks')
    md5 = models.CharField(max_length=32)


class FileChunk(models.Model):
    """
    FileChunk model.

    A file consists of a series of chunks. This model ties chunks to a file,
    ordering is provided by `serial`.
    """

    # TODO: Make a model or QuerySet that always orders by serial.

    class Meta:
        unique_together = ('file', 'serial')

    file = models.ForeignKey(File, on_delete=models.CASCADE)
    chunk = models.ForeignKey(Chunk, on_delete=models.PROTECT)
    serial = models.IntegerField(default=0)


class ChunkStorage(models.Model):
    """
    ChunkStorage model.

    Represents a chunk in cloud storage.
    """

    class Meta:
        unique_together = ('chunk', 'storage')

    chunk = models.ForeignKey(Chunk, related_name='storage',
                              on_delete=models.CASCADE)
    storage = models.ForeignKey(OAuth2StorageToken, on_delete=models.CASCADE)
    # Provider-specific attribute storage, such as the chunk's file ID.
    attrs = JSONField(null=True, blank=True)
