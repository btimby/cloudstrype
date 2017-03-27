"""
Data models.

This file contains the models that pertain to the whole application.
"""
import mimetypes

from datetime import datetime, timedelta
from os.path import (
    normpath, dirname, splitext
)
from os.path import join as pathjoin
from os.path import split as pathsplit

from django.contrib.auth.base_user import (
    AbstractBaseUser, BaseUserManager
)
from django.contrib.postgres.fields import (
    JSONField, ArrayField
)
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import Max
from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _
from django.utils import timezone
from django.utils.dateformat import format
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
    """Manage User Model."""

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


class User(UidModelMixin, AbstractBaseUser):
    """
    User model.

    Created as placeholder for future expansion.
    """

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    email = models.EmailField(null=False, blank=False, unique=True,
                              max_length=255, verbose_name='email address')
    full_name = models.CharField(max_length=64)
    first_name = models.CharField(max_length=64, editable=False)
    last_name = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = UserManager()

    def __str__(self):
        return '<User: %s>' % self.email

    def save(self, *args, **kwargs):
        if self.full_name:
            self.first_name, _, self.last_name = self.full_name.partition(' ')
        return super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name

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
        for storage in OAuth2AccessToken.objects.filter(user=self):
            clients.append(storage.get_client())
        return clients

    def get_option(self, name, default=None):
        try:
            return getattr(self.options, name)
        except ObjectDoesNotExist:
            return default


class Option(models.Model):
    """
    Option model.

    System-wide options that users define from a preference interface.
    """

    RAID_TYPES = {
        0: _('RAID 0: Striping'),
        1: _('RAID 1: Mirroring'),
        3: _('RAID 3: Striping w/ parity'),
    }

    RAID_DESCRIPTIONS = {
        0: '''RAID level 0 breaks your files into chunks and writes the chunks
              to various clouds. This yields the most usable space due to the
              fact that no duplicates are stored. However, it is the least
              reliable since if any single cloud is unavailable, most or all of
              your files will be unavailable.''',

        1: '''RAID level 1 breaks your files into chunks and writes copies of
              each chunk to a different cloud. This yields less usable space
              since at least half your space is used to store replicas. However
              if any single cloud is unavailable your files remain accessible.

              * Note that as you increase your cloud storage portfolio, you can
              also increase the number of replicas stored. This increases
              reliability while decreasing usable space.''',

        3: '''RAID level 3 breaks your files into chunks and uses a mathmatical
              trick to gain redundancy without storing the file multiple times.
              RAID 3 uses 50% less space than storing a single replica, but
              provides the same level of redundancy. 50% more space is required
              than RAID 0 requires. This method yields the best trade-off
              between space and reliability but is less reliable than RAID
              level 1 with replica counts greater than 2.

              * RAID level 3 is the recommended option when using more than one
              cloud.''',
    }

    user = models.OneToOneField(User, related_name='options',
                                on_delete=models.CASCADE)
    raid_level = models.SmallIntegerField(null=False, default=1)
    raid_replicas = models.SmallIntegerField(null=False, default=1)
    attrs = JSONField(null=True)

    def __str__(self):
        return '<Option %s, %s, %s>' % (self.raid_level, self.raid_replicas,
                                        self.attrs)


class ServiceProvider(UidModelMixin, models.Model):
    """
    ServiceProvider model.

    An external provider of authentication or storage.
    """

    PROVIDER_DROPBOX = 1
    PROVIDER_ONEDRIVE = 2
    PROVIDER_BOX = 3
    PROVIDER_GDRIVE = 4
    PROVIDER_ARRAY = 5

    PROVIDERS = {
        PROVIDER_DROPBOX: "Dropbox",
        PROVIDER_ONEDRIVE: "Onedrive",
        PROVIDER_BOX: "Box",
        PROVIDER_GDRIVE: "Google Drive",
        PROVIDER_ARRAY: "Array",
    }

    class Meta:
        verbose_name = 'Service Provider'
        verbose_name_plural = 'Service Providers'

    provider = models.SmallIntegerField(null=False, choices=PROVIDERS.items())

    def __str__(self):
        return '<OAuth2Provider: %s>' % self.name

    @property
    def name(self):
        return self.PROVIDERS[self.provider]


class ArrayProvider(ServiceProvider):
    """
    ArrayProvider model.

    Represents a ServiceProvider for the Cloudstrype array.
    """

    def __str__(self):
        return '<ArrayProvider: %s>' % self.name

    def get_client(self, **kwargs):
        raise NotImplementedError('No provider client.')


class OAuth2Provider(ServiceProvider):
    """
    OAuth2Provider model.

    Represents a ServiceProvider for OAuth2 cloud storage.
    """

    client_id = models.TextField(null=False)
    client_secret = models.TextField()

    def __str__(self):
        return '<OAuth2Provider: %s>' % self.name

    def get_client(self, redirect_uri, **kwargs):
        return get_client(self, redirect_uri=redirect_uri)


class UserService(UidModelMixin, models.Model):
    """
    UserService model.

    Represents a ServiceProvider instance for a given user.
    """

    user = models.ForeignKey(User)
    provider = models.ForeignKey(ServiceProvider)
    size = models.BigIntegerField(default=0)
    used = models.BigIntegerField(default=0)
    # Provider-specific attribute storage, such as chunk storage location
    # directory ID.
    attrs = JSONField(null=True, blank=True)


class ArrayNode(UserService):
    """
    ArrayNode model.

    Represents a node within an array belonging to a user.
    """

    name = models.UUIDField()

    def __str__(self):
        return '<ArrayNode: %s>' % self.name

    def get_client(self, **kwargs):
        "Get an HTTP client to interact with this node."
        return ArrayClient(self, **kwargs)


class OAuth2AccessToken(UserService):
    """
    OAuth2AccessToken model.

    An access token obtained for a user from a provider. Represents an instance
    of a cloud service provider for a specific user.
    """

    class Meta:
        verbose_name = 'OAuth2 Access Token'
        verbose_name_plural = 'OAuth2 Access Tokens'

    provider_uid = models.CharField(null=False, blank=False, editable=False,
                                    max_length=255)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True)
    expires = models.DateTimeField(null=True)

    def __str__(self):
        return '<OAuth2AccessToken: %s@%s>' % (self.user.email,
                                               self.provider.name)

    def get_client(self, **kwargs):
        "Get an OAuth2 client to interact with this cloud."
        return get_client(self.provider, oauth_access=self, **kwargs)

    def update(self, access_token, refresh_token=None, expires=None, **kwargs):
        if 'expires_at' in kwargs:
            expires = datetime.fromtimestamp(kwargs['expires_at'],
                                             timezone.utc)
        elif 'expires_in' in kwargs:
            expires = datetime.now(timezone.utc) + \
                      timedelta(seconds=kwargs['expires_in'])
        else:
            expires = kwargs.get('expires', None)
        self.access_token = access_token
        if refresh_token:
            # This check is necessary because Google uses long-lived refresh
            # tokens, in other words they don't issue a new one when you
            # refresh. We need to retain the old one for re-use.
            #
            # See the final note of the following section:
            # https://developers.google.com/identity/protocols/OAuth2WebServer#offline  # NOQA
            self.refresh_token = refresh_token
        self.expires = expires
        self.save()

    def to_dict(self):
        token = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
        }
        if self.expires:
            token['expires_at'] = format(self.expires, 'U')
        return token


class Tag(models.Model):
    """
    Tag model.

    Contains all possible tag values system-wide. Tags can be assigned to files
    and directories.
    """

    name = models.CharField(null=False, max_length=32)


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
        if 'user' not in kwargs:
            raise ValueError('User required for directory creation')
        path = kwargs.get('path', None)
        parent = dirname(path)
        if parent:
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
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = models.ManyToManyField(Tag)
    attrs = JSONField(null=True, blank=True)
    search = SearchVectorField(null=True, blank=True, editable=False)

    objects = DirectoryManager()

    def __str__(self):
        return '<Directory: %s>' % self.path

    @property
    def path(self):
        return '/%s' % self.display_path.lstrip('/')


class DirectoryShare(models.Model):
    """
    DirectoryShare model.

    Represents a directory shared by one user to another.
    """

    class Meta:
        unique_together = ('directory', 'user')

    directory = models.ForeignKey(Directory, on_delete=models.CASCADE,
                                  related_name='shared_to')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='shared_directories')


class FileQuerySet(UidQuerySet):
    @staticmethod
    def _args(kwargs):
        path = kwargs.pop('path', None)
        if path:
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
        if 'user' not in kwargs:
            raise ValueError('User required for file creation')
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
    mime = models.CharField(max_length=64)
    raid_level = models.SmallIntegerField(null=False, default=1)
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = models.ManyToManyField(Tag)
    attrs = JSONField(null=True, blank=True)
    search = SearchVectorField(null=True, blank=True, editable=False)

    objects = FileManager()

    def __str__(self):
        return '<File: %s>' % self.path

    def save(self, *args, **kwargs):
        if not self.mime:
            # If mimetype is unknown, try to determine file's mime type based
            # on it's name.
            self.mime, _ = mimetypes.guess_type(self.name, strict=False)
            if self.mime is None:
                self.mime = 'application/octet-stream'
        return super().save(*args, **kwargs)

    @property
    def path(self):
        return pathjoin(self.directory.path, self.name)

    @property
    def extension(self):
        return splitext(self.name)[1]

    @transaction.atomic
    def add_chunk(self, chunk):
        "Adds a chunk to a file, taking care to set the serial number."
        fc = FileChunk(file=self, chunk=chunk)
        fc.serial = (FileChunk.objects.filter(file=self).select_for_update(
            ).aggregate(Max('serial'))['serial__max'] or 0) + 1
        fc.save()
        return fc


class FileStat(models.Model):
    """
    FileStat model.

    Represents stats about a file.
    """

    file = models.OneToOneField(File, on_delete=models.CASCADE,
                                related_name='stats')
    reads = models.IntegerField()
    last = models.DateTimeField(auto_now=True)


class FileShare(models.Model):
    """
    FileShare model.

    Represents a file shared by a user to another user.
    """

    class Meta:
        unique_together = ('file', 'user')

    file = models.ForeignKey(File, on_delete=models.CASCADE,
                             related_name='shared_to')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='shared_files')


class Chunk(UidModelMixin, models.Model):
    """
    Chunk model.

    Represents a unique chunk of data. There is a many to many relationship
    between chunks and files. This may allow future de-dupe, as a chunk with
    the same content can be shared by many files.
    """

    file = models.ManyToManyField(to=File, through='FileChunk',
                                  related_name='chunks')
    md5 = models.CharField(max_length=32)

    def __str__(self):
        return '<Chunk %s %s>' % (self.uid, self.md5)


class FileChunkManager(models.Manager):
    """
    Manage FileChunks.
    """

    def get_queryset(self):
        """
        Return QuerySet with default ordering.
        """
        return QuerySet(self.model, using=self._db).order_by('serial')


class FileChunk(models.Model):
    """
    FileChunk model.

    A file consists of a series of chunks. This model ties chunks to a file,
    ordering for a given file is provided by `serial`.
    """

    class Meta:
        unique_together = ('file', 'serial')

    file = models.ForeignKey(File, on_delete=models.CASCADE)
    chunk = models.ForeignKey(Chunk, on_delete=models.PROTECT)
    serial = models.IntegerField(default=0)

    objects = FileChunkManager()

    def __str__(self):
        return '<FileChunk %s[%s]>' % (self.file.path, self.serial)


class ChunkService(models.Model):
    """
    ChunkStorage model.

    Represents a chunk stored in a provider. Each chunk may exist in multiple
    storage services (for redundancy).
    """

    class Meta:
        unique_together = ('chunk', 'service')

    chunk = models.ForeignKey(Chunk, related_name='services',
                              on_delete=models.CASCADE)
    service = models.ForeignKey(UserService, related_name='chunks',
                                on_delete=models.CASCADE)
    # Provider-specific attribute storage, such as the chunk's file ID.
    attrs = JSONField(null=True, blank=True)

    def __str__(self):
        return '<ChunkService %s@%s>' % (self.chunk,
                                         self.service.provider.name)


from main.fs.clouds import get_client  # NOQA
from main.fs.array import ArrayClient  # NOQA
