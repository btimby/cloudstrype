# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-05-21 00:33
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL([
            '    CREATE UNIQUE INDEX "unique_file_in_dir"'
            '    ON "main_userfile" ("user_id", "parent_id", "file_id")'
            '    WHERE "deleted" IS NULL'
        ,
            '    CREATE UNIQUE INDEX "unique_name_in_dir"'
            '    ON "main_userfile" ("user_id", "parent_id", "name")'
            '    WHERE "deleted" IS NULL'
        ]),
    ]
