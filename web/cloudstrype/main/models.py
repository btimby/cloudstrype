"""
Data models.

This file contains the models that pertain to the whole application.
"""
import functools
import uuid
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
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import Max
from django.db.models import Q
from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _
from django.utils import timezone
from django.utils.dateformat import format
from hashids import Hashids


def SET_FIELD(field_name, value):
    """
    Delete option.

    Like django.db.models.SET but sets a field OTHER than the fk.
    """
    if callable(value):
        def set_on_delete(collector, field, sub_objs, using):
            field = field.model._meta.get_field(field_name)
            collector.add_field_update(field, value(), sub_objs)
    else:
        def set_on_delete(collector, field, sub_objs, using):
            field = field.model._meta.get_field(field_name)
            collector.add_field_update(field, value, sub_objs)
    set_on_delete.deconstruct = lambda: ('SET_FIELD', (field_name, value,), {})
    return set_on_delete


class UidQuerySet(QuerySet):
    """
    QuerySet with uid capabilities.

    Allow objects to be easily selected by uid.
    """

    @staticmethod
    def _args(model, kwargs):
        uid = kwargs.pop('uid', None)
        if uid:
            try:
                kwargs['id'] = model.get_hashids().decode(uid)[0]
            except IndexError:
                # Decode problem, invalid uid...
                raise model.DoesNotExist()

    def filter(self, *args, **kwargs):
        UidQuerySet._args(self.model, kwargs)
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

    _hashids = None

    @classmethod
    def get_hashids(cls):
        # TODO: There is probably a much cleaner way to do this...
        if cls._hashids is None:
            cls._hashids = Hashids(min_length=24, salt=cls._meta.label)
        return cls._hashids

    @property
    def uid(self):
        "Return a random-looking id."
        return self.get_hashids().encode(self.id)

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
        for storage in BaseUserStorage.objects.filter(user=self):
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


class BaseStorage(UidModelMixin, models.Model):
    """
    BaseStorage model.

    An external provider of storage.
    """

    PROVIDER_DROPBOX = 1
    PROVIDER_ONEDRIVE = 2
    PROVIDER_BOX = 3
    PROVIDER_GOOGLE = 4
    PROVIDER_ARRAY = 5
    PROVIDER_BASIC = 6

    PROVIDERS = {
        PROVIDER_DROPBOX: "Dropbox",
        PROVIDER_ONEDRIVE: "Onedrive",
        PROVIDER_BOX: "Box",
        PROVIDER_GOOGLE: "Google Drive",
        PROVIDER_ARRAY: "Array",
        PROVIDER_BASIC: "Basic",
    }

    PROVIDER_SLUGS = {
        PROVIDER_DROPBOX: "dropbox",
        PROVIDER_ONEDRIVE: "onedrive",
        PROVIDER_BOX: "box",
        PROVIDER_GOOGLE: "google",
        PROVIDER_ARRAY: "array",
        PROVIDER_BASIC: "basic",
    }

    class Meta:
        verbose_name = 'Storage'
        verbose_name_plural = 'Storage'

    provider = models.SmallIntegerField(null=False, choices=PROVIDERS.items())

    def __str__(self):
        return '<BaseStorage: %s>' % self.name

    @property
    def name(self):
        return self.PROVIDERS[self.provider]

    @property
    def slug(self):
        return self.PROVIDER_SLUGS[self.provider]

    def get_client(self, *args, **kwargs):
        for subclass in ('oauth2storage', 'arraystorage', 'basicstorage'):
            try:
                return getattr(self, subclass).get_client(*args, **kwargs)
            except ObjectDoesNotExist:
                continue
        raise ValueError('Invalid BaseStorage instance')


class ArrayStorage(BaseStorage):
    """
    ArrayStorage model.

    Represents storage access via array system.
    """

    def __str__(self):
        return '<ArrayProvider: %s>' % self.name

    def get_client(self, **kwargs):
        raise NotImplementedError('No client available.')


class OAuth2Storage(BaseStorage):
    """
    OAuth2Storage model.

    Represents Storage accessed via HTTP and OAuth2.
    """

    client_id = models.TextField(null=False)
    client_secret = models.TextField()

    def __str__(self):
        return '<OAuth2Storage: %s>' % self.name

    def get_client(self, redirect_uri, **kwargs):
        return get_client(self, redirect_uri=redirect_uri)


class BasicStorage(BaseStorage):
    """
    BasicStorage model.

    Represents storage accessed via URL and secure by username/password.
    """

    def __str__(self):
        return '<BasicStorage: %s>' % self.name

    def get_client(self, **kwargs):
        "Get an HTTP client to interact with this node."
        raise NotImplementedError('No client available.')


class BaseUserStorage(UidModelMixin, models.Model):
    """
    BaseUserStorage model.

    Represents a Storage instance for a given user.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='storages')
    storage = models.ForeignKey(BaseStorage)
    size = models.BigIntegerField(default=0)
    used = models.BigIntegerField(default=0)
    # Provider-specific attribute storage, such as chunk storage location
    # directory ID.
    attrs = JSONField(null=True, blank=True)

    def __str__(self):
        return '<BaseUserStorage: %s/%s>' % (self.storage, self.user)

    def get_client(self, *args, **kwargs):
        for subclass in ('oauth2userstorage', 'arrayuserstorage',
                         'basicuserstorage'):
            try:
                return getattr(self, subclass).get_client(*args, **kwargs)
            except ObjectDoesNotExist:
                continue
        raise ValueError('Invalid BaseStorage instance')


class ArrayUserStorage(BaseUserStorage):
    """
    ArrayUserStorage model.

    Represents a node within an array belonging to a user.
    """

    name = models.UUIDField(default=uuid.uuid4)

    def __str__(self):
        return '<ArrayUserStorage: %s>' % self.name

    def get_client(self, **kwargs):
        "Get an HTTP client to interact with this node."
        return ArrayClient(self, **kwargs)


class OAuth2UserStorage(BaseUserStorage):
    """
    OAuth2UserStorage model.

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
        return '<OAuth2UserStorage: %s@%s>' % (self.user.email,
                                               self.storage.name)

    def get_client(self, **kwargs):
        "Get an OAuth2 client to interact with this cloud."
        return get_client(self.storage, user_storage=self, **kwargs)

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


class BasicUserStorage(BaseUserStorage):
    url = models.URLField(max_length=256)
    username = models.CharField(max_length=256)
    # TODO: encrypt this.
    password = models.CharField(max_length=256)

    def __str__(self):
        return '<BasicServer: %s>' % self.url

    def get_client(self, **kwargs):
        # TODO: get a protocol specific client for this server.
        pass


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
    def _args(model, kwargs):
        """Convert path to name/parents."""
        UidQuerySet._args(model, kwargs)
        path = kwargs.pop('path', None)
        if path:
            parents = normpath(path.lstrip('/')).split('/')
            kwargs['name'] = parents.pop()
            obj = None
            for part in parents:
                obj = Directory.objects.get(name=part, parent=obj)
            kwargs['parent'] = obj

    def filter(self, *args, **kwargs):
        """Filter objects using full path."""
        try:
            DirectoryQuerySet._args(self.model, kwargs)
        except Directory.DoesNotExist:
            # We failed to find a parent for the given path, thus it cannot
            # exist.
            return super().none()
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
        # Preserve this arg (_args() pops it...)
        path = kwargs.get('path', None)
        try:
            DirectoryQuerySet._args(self.model, kwargs)
        except Directory.DoesNotExist:
            # Parent missing, create...
            parent = dirname(path.lstrip('/'))
            kwargs['parent'], _ = Directory.objects.get_or_create(
                user=kwargs['user'], path=parent)
        return super().create(*args, **kwargs)

    def get_or_create(self, *args, **kwargs):  # noqa: D402
        """
        Override default get_or_create().
        """
        # It might be better to do this in save().
        DirectoryQuerySet._args(self.model, kwargs)
        return super().get_or_create(*args, **kwargs)

    def children_of(self, dir, user=None, dirs_only=False, name=None):
        if user is None:
            user = dir.user

        dir_q_kwargs = {'parent': dir, 'user': user}
        if name:
            dir_q_kwargs['name'] = name
        dir_q = Q(**dir_q_kwargs)

        dir_q_kwargs = {'shared_with__parent': dir, 'shared_with__user': user}
        if name:
            dir_q_kwargs['shared_with__name'] = name
        dir_q |= Q(**dir_q_kwargs)

        return self.filter(dir_q), File.objects.none() if dirs_only else \
            File.objects.children_of(dir, user, name=name)


class Directory(UidModelMixin, models.Model):
    """
    Directory model.

    Represents a directory in the FS.
    """

    class Meta:
        unique_together = ('user', 'name', 'parent')

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', null=True, related_name='dirs',
                               on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = models.ManyToManyField(Tag)
    attrs = JSONField(null=True, blank=True)
    search = SearchVectorField(null=True, blank=True, editable=False)

    objects = DirectoryManager()

    def __str__(self):
        return '<Directory: %s>' % self.name

    def get_name(self, user):
        if self.user == user:
            return self.name
        return self.shared_with.get(user=user).name

    def get_path(self, user):
        parent_path = self.parent.get_path(user) if self.parent else '/'
        return pathjoin(parent_path, self.get_name(user))

    def add_tag(self, tag):
        if isinstance(tag, str):
            tag, _ = Tag.objects.get_or_create(name=tag)
        self.tags.add(tag)

    def share(self, user):
        """
        Share the directory with another user.
        """
        # The shared directory will show up in the receiving user's "root".
        name = self.name + ' (%s)' % self.user.email
        share = DirectoryShare.objects.create(
            user=user, directory=self, name=name)
        user.shared_directories.add(share)
        return share


class DirectoryShare(models.Model):
    """
    DirectoryShare model.

    Represents a directory shared by one user to another.
    """

    class Meta:
        unique_together = ('directory', 'user')

    directory = models.ForeignKey(Directory, on_delete=models.CASCADE,
                                  related_name='shared_with')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='shared_directories')
    parent = models.ForeignKey(Directory, null=True,
                               related_name='shared_dirs',
                               on_delete=models.SET_NULL)
    name = models.CharField(max_length=255)


class FileQuerySet(UidQuerySet):
    # Delete the objects using their delete() method. Make sure to 
    def delete(self):
        for m in self:
            m.delete()
        self._result_cache = None

    delete.alters_data = True
    delete.queryset_only = True

    @staticmethod
    def _args(model, kwargs):
        UidQuerySet._args(model, kwargs)
        path = kwargs.pop('path', None)
        if path:
            parent, kwargs['name'] = pathsplit(path.lstrip('/'))
            parent = parent if parent else None
            if parent:
                parent, _ = Directory.objects.get_or_create(
                    user=kwargs['user'], path=parent)
            kwargs['parent'] = parent

    def filter(self, *args, **kwargs):
        FileQuerySet._args(self.model, kwargs)
        return super().filter(*args, **kwargs)


class FileManager(models.Manager):
    def get_queryset(self):
        """
        Override default QuerySet

        Allow filtering wth full path.
        """
        return FileQuerySet(self.model, using=self._db)

    @transaction.atomic
    def create(self, *args, **kwargs):
        if 'user' not in kwargs:
            raise ValueError('User required for file creation')
        FileQuerySet._args(self.model, kwargs)
        version = kwargs['version'] = FileVersion.objects.create()
        version.file = super().create(*args, **kwargs)
        version.save(update_fields=['file'])
        return version.file

    def get_or_create(self, *args, **kwargs):  # noqa: D402
        """
        Override default get_or_create().
        """
        # It might be better to do this in save().
        FileQuerySet._args(self.model, kwargs)
        return super().get_or_create(*args, **kwargs)

    def children_of(self, dir, user=None, name=None):
        if user is None:
            user = dir.user

        file_q_kwargs = {'parent': dir, 'user': user}
        if name:
            file_q_kwargs['name'] = name
        file_q = Q(**file_q_kwargs)

        file_q_kwargs = {'shared_with__parent': dir, 'shared_with__user': user}
        if name:
            file_q_kwargs['shared_with__name'] = name
        file_q |= Q(**file_q_kwargs)

        return self.filter(file_q)

    def delete(self):
        return self.get_queryset().delete()


class AllFile(models.Model):
    """
    This model backs File and DeadFile.
    """

    class Meta:
        # Weird bug, when this attr is in place, the created migration fails
        # with:
        #
        # ProgrammingError: referenced relation "main_livefile" is not a table
        #
        # When it is not in place, tests fail with:
        #
        # ProgrammingError: relation "main_allfile" does not exist
        #
        # My solution is to remove the field from the migration (it is
        # commented out) and leave this attr.
        db_table = 'main_file'

    user = models.ForeignKey(User, related_name='+',
                             on_delete=models.DO_NOTHING)
    # If the parent directory is deleted, set parent to NULL, this is done
    # because we soft-delete files, thus the file instance stays and we need
    # to maintain referential integrity. This must be done here for two reasons:
    #
    # 1. We need to do two things, and on_delete supports only one. We do the
    #    other thing in the File model.
    # 2. Since we cannot control the order of fields being set, once the
    #    soft-delete is performed by File, we cannot set parent to NULL using
    #    that model, as the instance vanishes from it's backing view.
    parent = models.ForeignKey(Directory, null=True, related_name='+',
                               on_delete=models.SET_NULL)
    version = models.ForeignKey('FileVersion', null=False, blank=False,
                                related_name='+')
    name = models.CharField(max_length=255)
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = models.ManyToManyField(Tag, through='AllFileTag')
    attrs = JSONField(null=True, blank=True)
    search = SearchVectorField(null=True, blank=True, editable=False)
    deleted = models.DateTimeField(null=True)

    objects = FileManager()


class File(UidModelMixin, models.Model):
    """
    File model.

    Represents a file in the FS. Backed by a view that filters out deleted IS
    NOT NULL.
    """

    class Meta:
        managed = False
        db_table = 'main_livefile'
        unique_together = ('parent', 'name')

    user = models.ForeignKey(User, related_name='files',
                             on_delete=models.CASCADE)
    # If the parent directory is deleted, soft-delete this file. It's parent is
    # set to NULL in the AllFile model.
    parent = models.ForeignKey(Directory, null=True, related_name='files',
                               on_delete=SET_FIELD('deleted', timezone.now))
    version = models.ForeignKey('FileVersion', null=False, blank=False,
                                related_name='current_of',
                                on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = models.ManyToManyField(Tag, through='FileTag')
    attrs = JSONField(null=True, blank=True)
    search = SearchVectorField(null=True, blank=True, editable=False)
    deleted = models.DateTimeField(null=True)

    objects = FileManager()

    @property
    def size(self):
        return self.version.size

    @property
    def md5(self):
        return self.version.md5

    @property
    def sha1(self):
        return self.version.sha1

    @property
    def mime(self):
        return self.version.mime

    @property
    def raid_level(self):
        return self.version.raid_level

    def __str__(self):
        return '<File: %s>' % self.name

    def __init__(self, *args, **kwargs):
        # Divert args to the version.
        v_kwargs = {}
        for name in ('size', 'md5', 'sha1', 'mime'):
            try:
                v_kwargs[name] = kwargs.pop(name)
            except KeyError:
                pass
        kwargs['version'] = FileVersion.objects.create(**v_kwargs)
        return super().__init__(*args, **kwargs)

    def guess_mime(self):
        mime, _ = mimetypes.guess_type(self.name, strict=False)
        return mime if mime else 'application/octet-stream'

    def save(self, *args, **kwargs):
        # Create an initial version if one is missing.
        if not self.version:
            self.version = FileVersion.objects.create(mime=self.guess_mime())
        else:
            self.version.mime = self.guess_mime()
            self.version.save(update_fields=['mime'])
        self.version.file = super().save(*args, **kwargs)
        self.version.save()
        return self

    def get_extension(self, user):
        return splitext(self.get_name(user))[1]

    def get_name(self, user):
        if self.user == user:
            return self.name
        return self.shared_with.get(user=user).name

    def get_path(self, user):
        parent_path = self.parent.get_path(user) if self.parent else '/'
        return pathjoin(parent_path, self.get_name(user))

    def revert(self, version):
        self.current = version
        self.save(update_fields=['current'])

    def add_tag(self, tag):
        if isinstance(tag, str):
            tag, _ = Tag.objects.get_or_create(name=tag)
        return FileTag.objects.create(file=self, tag=tag)

    @transaction.atomic
    def add_version(self):
        self.version = FileVersion.objects.create(file=self,
                                                  mime=self.guess_mime())
        # save() does not work, likely due to the cyclic relationship.
        File.objects.filter(pk=self.pk).update(version_id=self.version.pk)
        return self.version

    def share(self, user):
        """
        Share the directory with another user.
        """
        # The shared directory will show up in the receiving user's "root".
        name = self.name + ' (%s)' % self.user.email
        share = FileShare.objects.create(
            user=user, file=self, name=name)
        user.shared_directories.add(share)
        return share

    def delete(self):
        self.deleted = timezone.now()
        self.save(update_fields=['deleted'])


class DeadFile(UidModelMixin, models.Model):
    """
    View.

    Represents all deleted files. Backed by a view that filters out deleted IS
    NULL.
    """

    class Meta:
        managed = False
        db_table = 'main_deadfile'

    user = models.ForeignKey(User, related_name='dead_files',
                             on_delete=models.DO_NOTHING)
    parent = models.ForeignKey(Directory, null=True, related_name='dead_files',
                               on_delete=models.DO_NOTHING)
    version = models.ForeignKey('FileVersion', null=False, blank=False,
                                related_name='+')
    name = models.CharField(max_length=255)
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = models.ManyToManyField(Tag, through='DeadTag', related_name='+')
    attrs = JSONField(null=True, blank=True)
    search = SearchVectorField(null=True, blank=True, editable=False)
    deleted = models.DateTimeField(null=True)

    objects = FileManager()

    def __str__(self):
        return '<Dead: %s>' % self.name


class DeadTag(models.Model):
    class Meta:
        managed = False
        db_table = 'main_filetag'

    file = models.ForeignKey(DeadFile)
    tag = models.ForeignKey(Tag, related_name='+')


class FileTag(models.Model):
    class Meta:
        managed = False
        db_table = 'main_filetag'

    file = models.ForeignKey(File)
    tag = models.ForeignKey(Tag, related_name='files')


class AllFileTag(models.Model):
    class Meta:
        db_table = 'main_filetag'

    file = models.ForeignKey(AllFile)
    tag = models.ForeignKey(Tag, related_name='+')


class FileVersion(UidModelMixin, models.Model):
    file = models.ForeignKey(File, null=True, related_name='versions',
                             on_delete=models.CASCADE)
    size = models.IntegerField(default=0)
    md5 = models.CharField(max_length=32)
    sha1 = models.CharField(max_length=40)
    # TODO: Currently mime type is derived solely from file name. This means it
    # would be appropriate to store the mime attribute on File rather than
    # FileVersion. However, we should inspect the first chunk and use libmagic
    # to set the mime for each version. When we start that, mime truly would be
    # derived from the file body and thus belongs below.
    mime = models.CharField(max_length=64)
    raid_level = models.SmallIntegerField(null=False, default=1)
    created = models.DateTimeField(null=False, default=timezone.now)

    objects = UidManager()

    @transaction.atomic
    def add_chunk(self, chunk):
        "Adds a chunk to a file, taking care to set the serial number."
        fc = FileChunk(fileversion=self, chunk=chunk)
        fc.serial = (FileChunk.objects.filter(fileversion=self).select_for_update(
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
                             related_name='shared_with')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='shared_files')
    parent = models.ForeignKey(Directory, null=True,
                               related_name='shared_files',
                               on_delete=models.SET_NULL)
    name = models.CharField(max_length=255)


class Chunk(UidModelMixin, models.Model):
    """
    Chunk model.

    Represents a unique chunk of data. There is a many to many relationship
    between chunks and files. This may allow future de-dupe, as a chunk with
    the same content can be shared by many files.
    """

    fileversion = models.ManyToManyField(to=FileVersion, through='FileChunk',
                                         related_name='chunks')
    crc32 = models.IntegerField(null=False, blank=False, default=0)
    md5 = models.CharField(null=False, blank=False, max_length=32)
    size = models.IntegerField(null=False, blank=False)

    def __str__(self):
        return '<Chunk %s>' % self.uid


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
        unique_together = ('fileversion', 'serial')

    fileversion = models.ForeignKey(FileVersion, on_delete=models.CASCADE,
                                    related_name='filechunks')
    chunk = models.ForeignKey(Chunk, on_delete=models.PROTECT,
                              related_name='filechunks')
    serial = models.IntegerField(default=0)

    objects = FileChunkManager()

    def __str__(self):
        return '<FileChunk %s>' % self.serial


class ChunkStorage(models.Model):
    """
    ChunkStorage model.

    Represents a chunk stored in a provider. Each chunk may exist in multiple
    storage services (for redundancy).
    """

    class Meta:
        unique_together = ('chunk', 'storage')

    chunk = models.ForeignKey(Chunk, related_name='storage',
                              on_delete=models.CASCADE)
    storage = models.ForeignKey(BaseUserStorage, related_name='chunks',
                                on_delete=models.CASCADE)
    # Provider-specific attribute storage, such as the chunk's file ID.
    attrs = JSONField(null=True, blank=True)

    def __str__(self):
        return '<ChunkStorage %s@%s>' % (self.chunk,
                                         self.storage.storage.name)


from main.fs.clouds import get_client  # NOQA
from main.fs.array import ArrayClient  # NOQA
