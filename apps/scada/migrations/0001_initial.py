# Generated by Django 4.2.6 on 2023-10-14 15:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_created=True, auto_now=True)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('module_number', models.CharField(max_length=255, unique=True)),
                ('module_secret', models.CharField(max_length=255)),
                ('module_url', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Notify',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(db_index=True, max_length=255)),
                ('level', models.CharField(choices=[('default', '默认'), ('info', '信息'), ('warning', '警告'), ('error', '错误'), ('critical', '严重')], max_length=255)),
                ('title', models.CharField(db_index=True, max_length=255)),
                ('content', models.TextField()),
                ('source', models.CharField(max_length=255)),
                ('notified_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ack', models.BooleanField(default=False)),
                ('ack_at', models.DateTimeField(null=True)),
                ('meta', models.JSONField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('contact', models.CharField(max_length=255)),
                ('mobile', models.CharField(max_length=255)),
                ('status', models.IntegerField(default=1)),
                ('longitude', models.FloatField(default=114.305215)),
                ('latitude', models.FloatField(default=30.592849)),
                ('create_time', models.DateTimeField(auto_now_add=True)),
                ('remark', models.CharField(max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Variable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('type', models.CharField(max_length=255)),
                ('group', models.CharField(db_index=True, default='', max_length=255)),
                ('rw', models.BooleanField(default=False)),
                ('local', models.BooleanField(default=False)),
                ('details', models.CharField(default='', max_length=255)),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='scada.module')),
            ],
            options={
                'unique_together': {('name', 'module')},
            },
        ),
        migrations.CreateModel(
            name='Graph',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('status', models.IntegerField()),
                ('create_time', models.DateTimeField(auto_now_add=True)),
                ('data', models.TextField()),
                ('remark', models.CharField(max_length=255, null=True)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='scada.site')),
            ],
        ),
        migrations.CreateModel(
            name='Collector',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('interval', models.IntegerField(default=5)),
                ('timeout', models.IntegerField(default=3)),
                ('module', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='scada.module')),
            ],
        ),
        migrations.CreateModel(
            name='Rule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('alert_type', models.CharField(max_length=255)),
                ('alert_level', models.CharField(default='none', max_length=255)),
                ('threshold', models.FloatField(default=0.0)),
                ('state', models.IntegerField(default=0)),
                ('weight', models.FloatField(default=1.0)),
                ('duration', models.CharField(default='0s', max_length=20)),
                ('variable', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='scada.variable')),
            ],
            options={
                'unique_together': {('name', 'variable')},
            },
        ),
    ]
