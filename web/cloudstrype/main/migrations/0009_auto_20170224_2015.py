# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-24 20:15
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_auto_20170224_1934'),
    ]

    operations = [
        migrations.AlterField(
            model_name='oauth2storagetoken',
            name='token',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='main.OAuth2AccessToken'),
        ),
        migrations.AlterField(
            model_name='oauth2storagetoken',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storage', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='option',
            name='replicas',
            field=models.SmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='option',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='options', to=settings.AUTH_USER_MODEL),
        ),
    ]
