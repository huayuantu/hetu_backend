# Generated by Django 4.2.6 on 2023-10-15 03:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sys', '0002_alter_department_create_time_alter_dictdata_sort_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='department',
            name='status',
            field=models.IntegerField(default=1),
        ),
    ]
