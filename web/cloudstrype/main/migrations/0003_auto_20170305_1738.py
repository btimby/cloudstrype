# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-05 17:38
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20170305_0512'),
    ]

    operations = [
        migrations.RenameField(
            model_name='filechunk',
            old_name='raid_type',
            new_name='raid_level',
        ),
        migrations.RenameField(
            model_name='option',
            old_name='raid_type',
            new_name='raid_level',
        ),
    ]