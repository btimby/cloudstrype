# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-05 05:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='filechunk',
            managers=[
            ],
        ),
        migrations.AddField(
            model_name='option',
            name='raid_replicas',
            field=models.SmallIntegerField(default=1),
        ),
    ]
