# Generated by Django 4.2.5 on 2023-09-29 04:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0003_dicttype_alter_rolemenuid_role_route_dictdata'),
    ]

    operations = [
        migrations.DeleteModel(
            name='RoleOption',
        ),
    ]
