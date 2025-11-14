# Generated migration for database performance optimization

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scada', '0016_dashboardcard_title'),
    ]

    operations = [
        # 1. 添加 Site.status 索引（用于频繁的 exclude(status=0) 查询）
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS scada_site_status_idx 
            ON scada_site(status);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_site_status_idx;
            """
        ),
        
        # 2. 添加 Notify.ack 索引（用于过滤已确认/未确认的记录）
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS scada_notify_ack_idx 
            ON scada_notify(ack);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_notify_ack_idx;
            """
        ),
        
        # 3. 添加 SiteStatistic (site_id, name) 复合索引（优化查询顺序）
        # 注意：unique_together 已经创建了索引，但顺序可能是 (name, site_id)
        # 这里添加 (site_id, name) 索引以优化按 site_id 查询的场景
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS scada_sitestatistic_site_name_idx 
            ON scada_sitestatistic(site_id, name);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_sitestatistic_site_name_idx;
            """
        ),
        
        # 4. 确认 Variable.module_id 有索引（Django 默认会创建，但显式添加确保存在）
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS scada_variable_module_id_idx 
            ON scada_variable(module_id);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_variable_module_id_idx;
            """
        ),
        
        # 5. 添加 Module.site_id 索引（用于 join 查询优化）
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS scada_module_site_id_idx 
            ON scada_module(site_id);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS scada_module_site_id_idx;
            """
        ),
    ]

