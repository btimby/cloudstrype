# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-02 16:07
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='arrayuserstorage',
            name='name',
            field=models.UUIDField(default=uuid.uuid4),
        ),
        migrations.AlterField(
            model_name='filechunk',
            name='chunk',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='filechunks', to='main.Chunk'),
        ),
        migrations.AlterField(
            model_name='filechunk',
            name='file',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='filechunks', to='main.File'),
        ),
        migrations.RunSQL([
            "CREATE FUNCTION main_file_trigger() RETURNS trigger AS $$"
            "begin"
            "  new.search :="
            "     setweight(to_tsvector('pg_catalog.english', coalesce(new.name,'')), 'A');"
            "  return new;"
            "end"
            "$$ LANGUAGE plpgsql"
        ,
            "CREATE TRIGGER main_file_update BEFORE INSERT OR UPDATE"
            "    ON main_file FOR EACH ROW EXECUTE PROCEDURE main_file_trigger()"
        ,
            "CREATE FUNCTION main_directory_trigger() RETURNS trigger AS $$"
            "begin"
            "  new.search :="
            "     setweight(to_tsvector('pg_catalog.english', coalesce(new.name,'')), 'A');"
            "  return new;"
            "end"
            "$$ LANGUAGE plpgsql"
        ,
            "CREATE TRIGGER main_directory_update BEFORE INSERT OR UPDATE"
            "    ON main_directory FOR EACH ROW EXECUTE PROCEDURE main_directory_trigger()"
        ], [
            "DROP FUNCTION main_directory_trigger()",
            "DROP TRIGGER main_directory_update ON main_directory",
            "DROP FUNCTION main_file_trigger()",
            "DROP TRIGGER main_file_update ON main_file",
        ]),
    ]