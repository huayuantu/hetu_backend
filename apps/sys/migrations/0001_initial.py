# Generated by Django 4.2.5 on 2023-10-05 05:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(max_length=255)),
                ('create_time', models.DateTimeField()),
                ('status', models.IntegerField()),
                ('parent', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='sys.department')),
            ],
        ),
        migrations.CreateModel(
            name='DictType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(max_length=255, unique=True)),
                ('status', models.IntegerField()),
                ('remark', models.CharField(max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_time', models.DateTimeField(auto_created=True)),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('status', models.IntegerField(default=1)),
                ('sort', models.IntegerField()),
                ('update_time', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=255, unique=True)),
                ('password', models.CharField(max_length=100)),
                ('nickname', models.CharField(max_length=255)),
                ('mobile', models.CharField(max_length=20)),
                ('gender_label', models.CharField(max_length=10)),
                ('avatar', models.URLField(max_length=255, null=True)),
                ('email', models.EmailField(max_length=254, null=True)),
                ('status', models.IntegerField(default=1)),
                ('create_time', models.DateTimeField()),
                ('dept', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sys.department')),
                ('roles', models.ManyToManyField(to='sys.role')),
            ],
        ),
        migrations.CreateModel(
            name='Menu',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('menu_type', models.CharField(choices=[('CATALOG', '目录'), ('MENU', '菜单'), ('BUTTON', '按钮'), ('EXTLINK', '外部链接')], max_length=255)),
                ('path', models.CharField(max_length=255)),
                ('component', models.CharField(max_length=255, null=True)),
                ('sort', models.IntegerField(default=1)),
                ('visible', models.IntegerField(default=1)),
                ('icon', models.CharField(max_length=255, null=True)),
                ('redirect', models.CharField(max_length=255, null=True)),
                ('perm', models.CharField(max_length=255, null=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sys.menu')),
                ('roles', models.ManyToManyField(to='sys.role')),
            ],
        ),
        migrations.CreateModel(
            name='DictData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=255)),
                ('value', models.CharField(max_length=255)),
                ('status', models.IntegerField()),
                ('sort', models.IntegerField()),
                ('remark', models.CharField(max_length=255, null=True)),
                ('dict_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sys.dicttype')),
            ],
        ),
        migrations.CreateModel(
            name='Api',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('path', models.CharField(max_length=255)),
                ('version', models.CharField(default='v1', max_length=255)),
                ('perm', models.CharField(max_length=100)),
                ('action', models.CharField(max_length=100)),
                ('roles', models.ManyToManyField(to='sys.role')),
            ],
        ),
    ]
