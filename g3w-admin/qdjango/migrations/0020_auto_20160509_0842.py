# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-09 08:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qdjango', '0019_widget'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='layer',
            options={'ordering': ['order'], 'permissions': (('view_layer', 'Can view qdjango layer'),), 'verbose_name': 'Layer', 'verbose_name_plural': 'Layers'},
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'permissions': (('view_project', 'Can view qdjango project'),), 'verbose_name': 'Project', 'verbose_name_plural': 'Projects'},
        ),
        migrations.AlterField(
            model_name='widget',
            name='widget_type',
            field=models.CharField(choices=[(b'search', 'Search'), (b'law', 'Law'), (b'tooltip', 'Tooltip')], max_length=255, verbose_name='Type'),
        ),
    ]
