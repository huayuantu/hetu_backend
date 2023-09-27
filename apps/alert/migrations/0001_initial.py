# Generated by Django 4.2.5 on 2023-09-27 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='NotifyMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(choices=[('default', '默认'), ('info', '信息'), ('warning', '警告'), ('error', '错误')], max_length=100)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField()),
                ('source', models.CharField(max_length=255)),
                ('notified_at', models.DateTimeField()),
                ('created_at', models.DateTimeField()),
                ('ack', models.BooleanField(default=False)),
                ('ack_at', models.DateTimeField(null=True)),
                ('meta', models.JSONField()),
            ],
        ),
    ]
