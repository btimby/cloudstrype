# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-16 03:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_auto_20170315_0126'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='directorytag',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='directorytag',
            name='directory',
        ),
        migrations.RemoveField(
            model_name='directorytag',
            name='tag',
        ),
        migrations.AlterUniqueTogether(
            name='filetag',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='filetag',
            name='file',
        ),
        migrations.RemoveField(
            model_name='filetag',
            name='tag',
        ),
        migrations.RemoveField(
            model_name='tag',
            name='user',
        ),
        migrations.AddField(
            model_name='directory',
            name='tags',
            field=models.ManyToManyField(to='main.Tag'),
        ),
        migrations.AddField(
            model_name='file',
            name='tags',
            field=models.ManyToManyField(to='main.Tag'),
        ),
        migrations.DeleteModel(
            name='DirectoryTag',
        ),
        migrations.DeleteModel(
            name='FileTag',
        ),
    ]