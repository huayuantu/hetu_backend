# Generated migration for performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scada', '0012_updatelog_appupdate'),
    ]

    operations = [
        # 为 Notify 模型添加复合索引以优化查询性能
        migrations.RunSQL(
            # 添加复合索引用于激活数查询优化
            sql="""
            CREATE INDEX IF NOT EXISTS scada_notify_external_notified_id_idx 
            ON scada_notify(external_id, notified_at DESC, id DESC);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_notify_external_notified_id_idx;
            """
        ),
        # 添加复合索引用于已确认数查询优化
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS scada_notify_ack_title_idx 
            ON scada_notify(ack, title);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_notify_ack_title_idx;
            """
        ),
        # 添加复合索引用于标题过滤查询优化
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS scada_notify_title_endswith_idx 
            ON scada_notify(title) WHERE title LIKE '%触发警告';
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_notify_title_endswith_idx;
            """
        ),
    ]

