# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-07 01:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0003_auto_20170305_1738'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='filechunk',
            name='raid_level',
        ),
        migrations.AddField(
            model_name='file',
            name='raid_level',
            field=models.SmallIntegerField(default=1),
        ),
    ]