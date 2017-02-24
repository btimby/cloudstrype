# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-24 07:00
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_auto_20170224_0638'),
    ]

    operations = [
        migrations.AddField(
            model_name='chunkstorage',
            name='attrs',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='oauth2storagetoken',
            name='attrs',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]