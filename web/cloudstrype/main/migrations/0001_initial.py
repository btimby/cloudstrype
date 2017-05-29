# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-29 03:12
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager
import django.utils.timezone
import main.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('email', models.EmailField(max_length=255, unique=True, verbose_name='email address')),
                ('full_name', models.CharField(max_length=64)),
                ('first_name', models.CharField(editable=False, max_length=64)),
                ('last_name', models.CharField(editable=False, max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('is_admin', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
            bases=(main.models.UidModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Chunk',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('crc32', models.IntegerField(default=0)),
                ('md5', models.CharField(max_length=32)),
                ('size', models.IntegerField()),
            ],
            bases=(main.models.UidModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ChunkStorage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attrs', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('chunk', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storages', to='main.Chunk')),
            ],
        ),
        migrations.CreateModel(
            name='File',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owned_files', to=settings.AUTH_USER_MODEL)),
            ],
            bases=(main.models.UidModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='FileStat',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reads', models.IntegerField()),
                ('last', models.DateTimeField(auto_now=True)),
                ('file', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stats', to='main.File')),
            ],
        ),
        migrations.CreateModel(
            name='FileTag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='FileVersion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.File')),
            ],
        ),
        migrations.CreateModel(
            name='Option',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('raid_level', models.SmallIntegerField(default=1)),
                ('raid_replicas', models.SmallIntegerField(default=1)),
                ('attrs', django.contrib.postgres.fields.jsonb.JSONField(null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='options', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Storage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.SmallIntegerField(choices=[(1, 'Dropbox'), (2, 'Onedrive'), (3, 'Box'), (4, 'Google Drive'), (5, 'Array'), (6, 'Basic')])),
                ('size', models.BigIntegerField(default=0)),
                ('used', models.BigIntegerField(default=0)),
                ('auth', django.contrib.postgres.fields.jsonb.JSONField(default={})),
                ('attrs', django.contrib.postgres.fields.jsonb.JSONField(default={})),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Storage',
                'verbose_name_plural': 'Storages',
            },
            bases=(main.models.UidModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
            ],
        ),
        migrations.CreateModel(
            name='UserDir',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('attrs', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('parent', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='child_dirs', to='main.UserDir')),
                ('tags', models.ManyToManyField(to='main.Tag')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=(main.models.UidModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='UserFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('attrs', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('deleted', models.DateTimeField(null=True)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_files', to='main.File')),
                ('parent', models.ForeignKey(null=True, on_delete=main.models.SET_FIELD('deleted', django.utils.timezone.now), related_name='child_files', to='main.UserDir')),
                ('tags', models.ManyToManyField(through='main.FileTag', to='main.Tag')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='files', to=settings.AUTH_USER_MODEL)),
            ],
            bases=(main.models.UidModelMixin, models.Model),
            managers=[
                ('all', django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name='Version',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('size', models.IntegerField(default=0)),
                ('md5', models.CharField(max_length=32)),
                ('sha1', models.CharField(max_length=40)),
                ('mime', models.CharField(max_length=64)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('file', models.ManyToManyField(related_name='versions', through='main.FileVersion', to='main.File')),
            ],
            options={
                'base_manager_name': 'objects',
            },
            bases=(main.models.UidModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='VersionChunk',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('serial', models.IntegerField(default=0)),
                ('chunk', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='filechunks', to='main.Chunk')),
                ('version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='filechunks', to='main.Version')),
            ],
        ),
        migrations.AddField(
            model_name='fileversion',
            name='version',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.Version'),
        ),
        migrations.AddField(
            model_name='filetag',
            name='file',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.UserFile'),
        ),
        migrations.AddField(
            model_name='filetag',
            name='tag',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='main.Tag'),
        ),
        migrations.AddField(
            model_name='file',
            name='version',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='current_of', to='main.Version'),
        ),
        migrations.AddField(
            model_name='chunkstorage',
            name='storage',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='main.Storage'),
        ),
        migrations.AddField(
            model_name='chunk',
            name='version',
            field=models.ManyToManyField(related_name='chunks', through='main.VersionChunk', to='main.Version'),
        ),
        migrations.AlterUniqueTogether(
            name='versionchunk',
            unique_together=set([('version', 'serial')]),
        ),
        migrations.AlterUniqueTogether(
            name='userdir',
            unique_together=set([('user', 'name', 'parent')]),
        ),
        migrations.AlterUniqueTogether(
            name='fileversion',
            unique_together=set([('file', 'version')]),
        ),
        migrations.AlterUniqueTogether(
            name='filetag',
            unique_together=set([('file', 'tag')]),
        ),
        migrations.AlterUniqueTogether(
            name='chunkstorage',
            unique_together=set([('chunk', 'storage')]),
        ),
    ]
