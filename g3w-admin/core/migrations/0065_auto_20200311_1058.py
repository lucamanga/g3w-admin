# Generated by Django 2.2.9 on 2020-03-11 10:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_auto_20200311_1052'),
    ]

    operations = [
        migrations.AddField(
            model_name='macrogroup',
            name='title_en',
            field=models.CharField(max_length=255, null=True, verbose_name='Title'),
        ),
        migrations.AddField(
            model_name='macrogroup',
            name='title_it',
            field=models.CharField(max_length=255, null=True, verbose_name='Title'),
        ),
    ]