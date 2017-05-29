"""
Data models.

This file contains the models that pertain to the whole application.
"""

from os.path import (
    dirname, splitext
)
from os.path import join as pathjoin
from os.path import split as pathsplit

from django.contrib.auth.base_user import (
    AbstractBaseUser, BaseUserManager
)
from django.contrib.postgres.fields import JSONField
# from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction, IntegrityError
from django.db.models import Max
from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _
from django.utils import timezone
from hashids import Hashids


def SET_FIELD(field_name, value):
    """
    Delete option.

    Like django.db.models.SET but sets a field OTHER than the fk.
    """
    if callable(value):
        def set_on_delete(collector, field, sub_objs, using):
            collector.add_field_update(field, None, sub_objs)
            field = field.model._meta.get_field(field_name)
            collector.add_field_update(field, value(), sub_objs)
    else:
        def set_on_delete(collector, field, sub_objs, using):
            collector.add_field_update(field, None, sub_objs)
            field = field.model._meta.get_field(field_name)
            collector.add_field_update(field, value, sub_objs)
    set_on_delete.deconstruct = lambda: ('main.models.SET_FIELD',
                                         (field_name, value,), {})
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
        for storage in Storage.objects.filter(user=self):
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


class Storage(UidModelMixin, models.Model):
    """
    Storage model.

    An external provider of storage.
    """

    TYPE_DROPBOX = 1
    TYPE_ONEDRIVE = 2
    TYPE_BOX = 3
    TYPE_GOOGLE = 4
    TYPE_ARRAY = 5
    TYPE_BASIC = 6

    TYPES = {
        TYPE_DROPBOX: "Dropbox",
        TYPE_ONEDRIVE: "Onedrive",
        TYPE_BOX: "Box",
        TYPE_GOOGLE: "Google Drive",
        TYPE_ARRAY: "Array",
        TYPE_BASIC: "Basic",
    }

    TYPE_SLUGS = {
        TYPE_DROPBOX: "dropbox",
        TYPE_ONEDRIVE: "onedrive",
        TYPE_BOX: "box",
        TYPE_GOOGLE: "google",
        TYPE_ARRAY: "array",
        TYPE_BASIC: "basic",
    }

    class Meta:
        verbose_name = 'Storage'
        verbose_name_plural = 'Storages'

    user = models.ForeignKey(User, null=False, blank=False,
                             on_delete=models.CASCADE, related_name='storages')
    type = models.SmallIntegerField(null=False, choices=TYPES.items())
    size = models.IntegerField(null=False, default=0)
    used = models.IntegerField(null=False, default=0)
    auth = JSONField(default={})
    attrs = JSONField(default={})

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.TYPES[self.type]

    @property
    def slug(self):
        return self.TYPE_SLUGS[self.type]

    def auth_update(self, auth):
        self.auth = self.auth or {}
        self.auth.update(auth)
        self.save(update_fields=['auth'])

    def get_client(self, *args, **kwargs):
        # Cache the client
        if getattr(self, '__client', None) is None:
            client = get_client(self.type, storage=self)
            setattr(self, '__client', client)
        return getattr(self, '__client')


class Tag(models.Model):
    """
    Tag model.

    Contains all possible tag values system-wide. Tags can be assigned to files
    and directories.
    """

    name = models.CharField(null=False, max_length=32)


class UserDirQuerySet(UidQuerySet):
    """
    QuerySet for Directories.

    Allow filtering by full path or uid.
    """

    @staticmethod
    def _args(model, kwargs):
        """Convert path pseudo argument actual fields."""
        # Convert path into the constituate parts that are stored. For example
        # when given a path, we split the path and recursively locate
        # directories using their user, parent and name.
        path = kwargs.pop('path', None)
        if path is not None:
            try:
                user = kwargs['user']
            except KeyError:
                raise ValueError('`user` argument required with `path`')
            parents = path.lstrip('/').split('/')
            kwargs['name'] = parents.pop()
            # This is the "root" for the user. We want to enforce uniqueness
            # for (user, name, parent), but if parent is NULL, we cannot do so.
            # Thus we use this "root" as the parent of everything at the
            # top-level.
            obj = UserDir.objects.get_root(user)
            if parents:
                for part in parents:
                    obj = obj.child_dirs.get(name=part)
                kwargs['parent'] = obj
            elif kwargs['name'] == '':
                # If name is also blank, they are looking for ROOT, thus parent
                # should be null.
                kwargs['parent'] = None
            else:
                kwargs['parent'] = obj

    def filter(self, *args, **kwargs):
        """Filter objects using full path."""
        try:
            UserDirQuerySet._args(self.model, kwargs)
        except UserDir.DoesNotExist:
            # We failed to find a parent for the given path, thus it cannot
            # exist. Rather than raising, return an empty queryset.
            return super().none()
        return super().filter(*args, **kwargs)


class UserDirManager(models.Manager):
    """Manage UserDir model."""
    def get_queryset(self):
        """
        Override default QuerySet.

        Allow filtering with full path.
        """
        return UserDirQuerySet(self.model, using=self._db)

    def create(self, *args, **kwargs):
        # Preserve this arg (_args() pops it...)
        path = kwargs.get('path', None)
        try:
            UserDirQuerySet._args(self.model, kwargs)
        except UserDir.DoesNotExist:
            # Parent missing, create...
            parent = dirname(path.lstrip('/'))
            kwargs['parent'], _ = UserDir.objects.get_or_create(
                user=kwargs['user'], path=parent)
        return super().create(*args, **kwargs)

    def get_or_create(self, *args, **kwargs):  # noqa: D402
        """
        Override default get_or_create().
        """
        # It might be better to do this in save().
        UserDirQuerySet._args(self.model, kwargs)
        return super().get_or_create(*args, **kwargs)

    def get_root(self, user):
        """Get a UserDir that serves as the user's "root"."""
        return UserDir.objects.get_or_create(user=user, name='')[0]


class UserDir(UidModelMixin, models.Model):
    """
    File hierarchy for a User.

    This model represents the hierarchy containing files for a given user. Each
    user can locate files within any directory they please (even if the file is
    shared amongst multiple users).
    """

    class Meta:
        unique_together = ('user', 'name', 'parent')

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', null=True, related_name='child_dirs',
                               on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created = models.DateTimeField(null=False, default=timezone.now)
    tags = models.ManyToManyField(Tag)
    attrs = JSONField(null=True, blank=True)

    objects = UserDirManager()

    def __str__(self):
        return self.path

    @property
    def isdir(self):
        return True

    @property
    def isfile(self):
        return False

    @property
    def path(self):
        parent_path = self.parent.path if self.parent else ''
        return pathjoin('/', parent_path, self.name)

    def add_tag(self, tag):
        if isinstance(tag, str):
            tag, _ = Tag.objects.get_or_create(name=tag)
        self.tags.add(tag)

    def share(self, user, parent=None, name=None, recursive=False):
        """
        Share the directory with another user.
        """
        if parent is None:
            # Get the target user's "root".
            parent = UserDir.objects.get_root(user=user)
        assert parent.user == user, "Bug! Sharing a directory with a user " \
                                    "into another user's directory"
        if name is None:
            # We choose the name.
            # - If owner's name for this directory does not exist, use it.
            if parent.child_dirs.filter(name=self.name).count() == 0:
                name = self.name
            # - If it exists, append sharing user's email address.
            else:
                name = '%s (%s)' % (self.name, user.email)
        dir = UserDir.objects.create(parent=parent, name=name, user=user)
        for f in self.child_files.all():
            f.share(user, parent=dir)
        # Done if we only want to share the files in this directory.
        if recursive:
            # If recursive, share the child DIRECTORIES and their contents too.
            for d in self.child_dirs.all():
                d.share(user, parent=dir, name=d.name, recursive=recursive)
        return dir


class UserFileQuerySet(UidQuerySet):
    @staticmethod
    def _args(model, kwargs, create_parent=False):
        path = kwargs.pop('path', None)
        if path:
            try:
                user = kwargs['user']
            except KeyError:
                raise ValueError('`user` argument required with `path`')
            parent, name = pathsplit(path.lstrip('/'))
            parent = parent if parent else ''
            if name == '' and parent == '':
                # If both are empty, caller is asking for '/' or similar, which
                # cannot be a file.
                raise UserFile.DoesNotExist()
            elif parent == '':
                # If only parent is empty, caller wants a file within root.
                parent = UserDir.objects.get_root(user)
            else:
                # If neither are empty, caller wants a file with a directory.
                try:
                    parent = UserDir.objects.get(user=user, path=parent)
                except UserDir.DoesNotExist:
                    # Caller may want us to create parent dirs (-p). For
                    # example, during create().
                    if not create_parent:
                        # If not, raise.
                        raise UserFile.DoesNotExist()
                    parent = UserDir.objects.create(user=user, path=parent)
            # The caller provided a valid path consisting of a parent directory
            # and a name. Set kwargs for the query.
            kwargs['name'] = name
            kwargs['parent'] = parent

    def filter(self, *args, **kwargs):
        try:
            UserFileQuerySet._args(self.model, kwargs)
        except UserFile.DoesNotExist:
            return self.none()
        return super().filter(*args, **kwargs)

    def delete(self):
        for m in self:
            m.delete()
        self._result_cache = None

    delete.alters_data = True
    delete.queryset_only = True


class BaseUserFileManager(models.Manager):
    def get_queryset(self):
        """
        Override default QuerySet

        Allow filtering wth full path.
        """
        return UserFileQuerySet(self.model, using=self._db)

    def delete(self):
        raise NotImplementedError()


class UserFileManager(BaseUserFileManager):
    def get_queryset(self):
        """
        Override default QuerySet

        Filter out soft deletions.
        """
        return super().get_queryset().filter(deleted__isnull=True)

    @transaction.atomic
    def create(self, *args, **kwargs):
        UserFileQuerySet._args(self.model, kwargs, create_parent=True)
        obj = super().create(*args, **kwargs)
        return obj

    def get_or_create(self, *args, **kwargs):  # noqa: D402
        """
        Override default get_or_create().
        """
        # It might be better to do this in save().
        UserFileQuerySet._args(self.model, kwargs, create_parent=True)
        try:
            return super().get(*args, **kwargs), False
        except ObjectDoesNotExist:
            try:
                return self.create(*args, **kwargs), True
            except IntegrityError:
                return super().get(*args, **kwargs), False

    def delete(self):
        return self.get_queryset().delete()


class DeadUserFileManager(BaseUserFileManager):
    def get_queryset(self):
        """
        Override default QuerySet

        Filter out soft deletions.
        """
        return super().get_queryset().filter(deleted__isnull=False)


class UserFile(UidModelMixin, models.Model):
    """
    File hierarchy for a User.

    This model represents the "namespace" or metadata for a given user. It is
    what records the name, path and attributes for files. Each user has their
    own specific namespace, even if they are working with the same files.
    """

    user = models.ForeignKey(User, related_name='files',
                             on_delete=models.DO_NOTHING)
    # If the parent directory is deleted, soft-delete this file.
    parent = models.ForeignKey(UserDir, null=True, related_name='child_files',
                               on_delete=SET_FIELD('deleted', timezone.now))
    file = models.ForeignKey('File', null=False, blank=False,
                             related_name='user_files')
    name = models.CharField(max_length=255)
    tags = models.ManyToManyField(Tag, through='FileTag')
    attrs = JSONField(null=True, blank=True)
    deleted = models.DateTimeField(null=True)

    all = BaseUserFileManager()
    objects = UserFileManager()
    dead = DeadUserFileManager()

    def __str__(self):
        return self.path

    @property
    def isdir(self):
        return False

    @property
    def isfile(self):
        return True

    def save(self, *args, **kwargs):
        try:
            self.file
        except File.DoesNotExist:
            self.file = File.objects.create(owner=self.user)
        return super().save(*args, **kwargs)

    @property
    def path(self):
        return pathjoin('/', self.parent.path, self.name)

    @property
    def extension(self):
        return splitext(self.name)[1]

    def add_tag(self, tag):
        if isinstance(tag, str):
            tag, _ = Tag.objects.get_or_create(name=tag)
        FileTag.objects.create(file=self, tag=tag)

    def share(self, user, parent=None, name=None):
        if parent is None:
            parent = UserDir.objects.get_root(user)
        if name is None:
            name = self.name
        return UserFile.objects.create(parent=dir, user=user, file=self.file,
                                       name=self.name)


class File(UidModelMixin, models.Model):
    """
    File model.

    Represents a file object. Files can be seen by many users, but the file
    properties may be different for each user. This model represents the
    properties that are shared amongst ALL users.
    """

    owner = models.ForeignKey(User, related_name='owned_files',
                              on_delete=models.CASCADE)
    version = models.ForeignKey('Version', null=False, blank=False,
                                related_name='current_of',
                                on_delete=models.PROTECT)
    created = models.DateTimeField(null=False, default=timezone.now)

    objects = models.Manager()

    def save(self, *args, **kwargs):
        new_version = False
        try:
            self.version
        except Version.DoesNotExist:
            new_version = True
            self.version = Version.objects.create()
        obj = super().save(*args, **kwargs)
        if new_version:
            FileVersion.objects.create(file=self, version=self.version)
        return obj

    def add_version(self, version=None):
        if version is None:
            version = Version.objects.create()
        self.version = version
        FileVersion.objects.create(file=self, version=version)
        self.save(update_fields=['version'])
        return version


class FileTag(models.Model):
    """
    UserFile<->Tag M2M model.

    Relates a user's files to tags. Each user can have different tags for a
    given file (thus we reference UserFile, not File).
    """

    class Meta:
        unique_together = ('file', 'tag')

    file = models.ForeignKey(UserFile)
    tag = models.ForeignKey(Tag, related_name='files')


class Version(UidModelMixin, models.Model):
    """
    File version model.

    Whenever an existing file is written to, a new version is created for that
    file. A File model has a foreign key to it's current version. There is an
    M2M table that keeps all historic versions of a file.

    More than one File can share a Version if the file data is identical
    (de-dupe).

    Chunks are attached to Version, since the Version represents the physical
    storage of a File.
    """

    class Meta:
        base_manager_name = 'objects'

    file = models.ManyToManyField(File, related_name='versions',
                                  through='FileVersion')
    size = models.IntegerField(default=0)
    md5 = models.CharField(max_length=32)
    sha1 = models.CharField(max_length=40)
    # TODO: Currently mime type is derived solely from file name. This means it
    # would be appropriate to store the mime attribute on File rather than
    # Version. However, we should inspect the first chunk and use libmagic
    # to set the mime for each version. When we start that, mime truly would be
    # derived from the file body and thus belongs below.
    mime = models.CharField(max_length=64)
    created = models.DateTimeField(null=False, default=timezone.now)

    objects = UidManager()

    @transaction.atomic
    def add_chunk(self, chunk):
        "Adds a chunk to a file, taking care to set the serial number."
        vc = VersionChunk(version=self, chunk=chunk)
        vc.serial = (
            VersionChunk.objects.filter(version=self).select_for_update()
            .aggregate(Max('serial'))['serial__max'] or 0
        ) + 1
        vc.save()
        return vc


class FileVersion(models.Model):
    """
    File<->Version M2M model.

    Maintains all historic versions of a file (including the current version).
    However, the current version is also referenced by the File.version FK.
    """

    class Meta:
        unique_together = ('file', 'version')

    file = models.ForeignKey(File, null=False, on_delete=models.CASCADE)
    version = models.ForeignKey(Version, null=False, on_delete=models.CASCADE)
    created = models.DateTimeField(null=False, default=timezone.now)

    objects = UidManager()


class FileStat(models.Model):
    """
    FileStat model.

    Represents stats about a file.
    """

    file = models.OneToOneField(File, on_delete=models.CASCADE,
                                related_name='stats')
    reads = models.IntegerField()
    last = models.DateTimeField(auto_now=True)


class Chunk(UidModelMixin, models.Model):
    """
    Chunk model.

    Represents a unique chunk of data. A chunk is assigned to a Version of a
    File via an M2M model. Any version of any file can reference any given
    chunk. So if two chunks of two unrelated files are identical, they will
    share the same chunk.
    """

    version = models.ManyToManyField(to=Version, through='VersionChunk',
                                     related_name='chunks')
    crc32 = models.IntegerField(null=False, blank=False, default=0)
    md5 = models.CharField(null=False, blank=False, max_length=32)
    size = models.IntegerField(null=False, blank=False)

    objects = UidManager()

    def __str__(self):
        return '%s' % self.uid


class FileChunkManager(models.Manager):
    """
    Manage FileChunks.
    """

    def get_queryset(self):
        """
        Return QuerySet with default ordering.
        """
        return QuerySet(self.model, using=self._db).order_by('serial')


class VersionChunk(models.Model):
    """
    Version<->Chunk M2M model.

    A file consists of a series of versions, each consisting of a series of
    chunks. This model ties chunks to a file version, ordering for a given
    version is provided by `serial`.
    """

    class Meta:
        unique_together = ('version', 'serial')

    version = models.ForeignKey(Version, on_delete=models.CASCADE,
                                related_name='filechunks')
    chunk = models.ForeignKey(Chunk, on_delete=models.PROTECT,
                              related_name='filechunks')
    serial = models.IntegerField(default=0)

    objects = FileChunkManager()

    def __str__(self):
        return '%s' % self.serial


class ChunkStorage(models.Model):
    """
    Chunk<->Storage M2M model.

    Each chunk is stored in multiple storage locations for redundancy. This
    model maps chunks to their respective storage locations.
    """

    class Meta:
        unique_together = ('chunk', 'storage')

    chunk = models.ForeignKey(Chunk, related_name='storages',
                              on_delete=models.CASCADE)
    storage = models.ForeignKey(Storage, related_name='chunks',
                                on_delete=models.CASCADE)
    # Provider-specific attribute storage, such as the chunk's file ID.
    attrs = JSONField(null=True, blank=True)

    def __str__(self):
        return '%s@%s' % (self.chunk, self.storage.name)


from main.fs.clouds import get_client  # NOQA
from main.fs.array import ArrayClient  # NOQA
