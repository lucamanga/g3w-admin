# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-03-17 10:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qdjango', '0008_auto_20160317_1030'),
    ]

    operations = [
        migrations.AlterField(
            model_name='layer',
            name='max_scale',
            field=models.IntegerField(blank=True, null=True, verbose_name='Layer Max Scale visibility'),
        ),
        migrations.AlterField(
            model_name='layer',
            name='min_scale',
            field=models.IntegerField(blank=True, null=True, verbose_name='Layer Min Scale visibility'),
        ),
    ]
