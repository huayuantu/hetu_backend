# Generated by Django 4.2.3 on 2023-09-18 11:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("grm", "0003_grmmodulevar"),
    ]

    operations = [
        migrations.RenameField(
            model_name="grmmodulevar",
            old_name="desc",
            new_name="details",
        ),
    ]
