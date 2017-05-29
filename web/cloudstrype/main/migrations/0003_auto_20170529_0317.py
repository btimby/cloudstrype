# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-29 03:17
from __future__ import unicode_literals

from django.contrib.auth.hashers import make_password
from django.db import migrations


USER_EMAIL = 'admin@cloudstrype.localhost.com'
USER_PASS = 'password'


def forwards(apps, schema_editor):
    """
    Create user and cloud providers.
    """
    User = apps.get_model('main', 'User')

    u = User.objects.create(email=USER_EMAIL, is_admin=True, is_active=True)
    u.password = make_password(USER_PASS)
    u.save()


def reverse(apps, schema_editor):
    User = apps.get_model('main', 'User')

    User.objects.filter(email=USER_EMAIL, is_admin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20170521_0033'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
