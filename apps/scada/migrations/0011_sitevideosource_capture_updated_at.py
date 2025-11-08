# Generated manually for Phase 1 improvements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scada', '0010_sitevideosource_capture'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitevideosource',
            name='capture_updated_at',
            field=models.DateTimeField(null=True),
        ),
    ]

