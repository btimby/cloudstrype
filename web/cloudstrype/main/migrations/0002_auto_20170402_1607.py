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
        migrations.RunSQL([
            "CREATE FUNCTION main_file_search() RETURNS trigger AS $$"
            "begin"
            "  new.search :="
            "     setweight(to_tsvector('pg_catalog.english', coalesce(new.name,'')), 'A');"
            "  return new;"
            "end"
            "$$ LANGUAGE plpgsql"
        ,
            "CREATE TRIGGER main_file_search_trigger BEFORE INSERT OR UPDATE"
            "    ON main_file FOR EACH ROW EXECUTE PROCEDURE main_file_search()"
        ,
            "CREATE FUNCTION main_directory_search() RETURNS trigger AS $$"
            "begin"
            "  new.search :="
            "     setweight(to_tsvector('pg_catalog.english', coalesce(new.name,'')), 'A');"
            "  return new;"
            "end"
            "$$ LANGUAGE plpgsql"
        ,
            "CREATE TRIGGER main_directory_search_trigger BEFORE INSERT OR UPDATE"
            "    ON main_directory FOR EACH ROW EXECUTE PROCEDURE main_directory_search()"
        ], [
            "DROP FUNCTION main_directory_search()",
            "DROP TRIGGER main_directory_search_trigger ON main_directory",
            "DROP FUNCTION main_file_search()",
            "DROP TRIGGER main_file_search_trigger ON main_file",
        ]),
    ]