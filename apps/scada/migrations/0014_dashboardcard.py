# Generated manually for DashboardCard model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scada', '0013_add_notify_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('variable_id', models.IntegerField()),
                ('variable_name', models.CharField(max_length=255)),
                ('card_type', models.CharField(max_length=20)),
                ('config', models.JSONField(default=dict)),
                ('position', models.IntegerField(default=0)),
                ('layout', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dashboard_cards', to='scada.site')),
            ],
            options={
                'ordering': ['position', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='dashboardcard',
            index=models.Index(fields=['site', 'position'], name='scada_dash_site_id_123456_idx'),
        ),
    ]

