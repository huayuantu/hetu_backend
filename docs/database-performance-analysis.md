# 数据库性能分析报告

## 🔍 问题概述

数据库容器 CPU 使用率非常高，需要分析所有数据库读写操作和索引情况，找出性能瓶颈。

## 📊 数据库模型索引分析

### 1. Site 表
```python
class Site(models.Model):
    name = models.CharField(max_length=255, unique=True)  # ✅ 有唯一索引
    status = models.IntegerField(default=1)  # ⚠️ 无索引
```

**问题**：
- `status` 字段无索引，但频繁用于过滤：`Site.objects.exclude(status=0)`
- 全局统计接口每次都要执行 `Site.objects.exclude(status=0).count()`

**建议**：添加 `status` 字段索引

### 2. Variable 表
```python
class Variable(models.Model):
    name = models.CharField(max_length=255)
    group = models.CharField(max_length=255, db_index=True)  # ✅ 有索引
    module = models.ForeignKey(Module, on_delete=models.PROTECT)  # ⚠️ 外键默认有索引，但需确认
```

**问题**：
- `Variable.objects.count()` 是全表扫描，如果表很大会很慢
- `module_id` 外键应该有索引（Django 默认），但需要确认
- 查询 `Variable.objects.filter(module__site_id=site_id)` 需要 join，可能慢

**建议**：
- 确认 `module_id` 有索引
- 考虑添加 `(module_id, name)` 复合索引（因为 unique_together）

### 3. Notify 表（⚠️ 严重问题）
```python
class Notify(models.Model):
    external_id = models.CharField(max_length=255, db_index=True)  # ✅ 有索引
    title = models.CharField(max_length=255, db_index=True)  # ✅ 有索引
    notified_at = models.DateTimeField(db_index=True)  # ✅ 有索引
    ack = models.BooleanField(default=False)  # ⚠️ 无索引
```

**严重问题**：
1. **全局统计查询** (`get_global_statistics`):
   ```python
   notifies = Notify.objects.all()  # 查询所有记录（可能数万条）
   stats = notifies.aggregate(...)
   latest_notify_ids = (
       notifies.values("external_id")
       .annotate(latest_id=Max("id"), latest_notified_at=Max("notified_at"))
       .values("latest_id")
   )
   activated = notifies.filter(
       id__in=latest_notify_ids, title__endswith="触发警告", ack=False
   ).count()
   ```
   - 查询所有 Notify 记录（无过滤）
   - 对每个 `external_id` 进行分组和聚合（GROUP BY）
   - 使用 `id__in` 子查询（可能包含大量 ID）
   - `ack=False` 过滤无索引

2. **缺少复合索引**：
   - `(external_id, notified_at)` - 用于查找最新记录
   - `(title, ack)` - 用于过滤激活的告警
   - `(external_id, title, ack)` - 用于复杂查询

**建议**：添加多个索引优化查询

### 4. SiteStatistic 表
```python
class SiteStatistic(models.Model):
    name = models.CharField(max_length=255)
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    
    class Meta:
        unique_together = [["name", "site"]]  # ✅ 有唯一约束（自动创建索引）
```

**问题**：
- 唯一约束会自动创建索引，但需要确认是复合索引 `(name, site_id)`
- 全局统计中对每个站点查询：`SiteStatistic.objects.filter(site_id=site_id, name="处理总量")`
- 如果索引顺序是 `(name, site_id)` 而不是 `(site_id, name)`，查询可能不是最优的

**建议**：确认索引顺序，必要时添加 `(site_id, name)` 索引

### 5. DashboardCard 表
```python
class DashboardCard(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    position = models.IntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=["site", "position"]),  # ✅ 有复合索引
        ]
```

**状态**：✅ 索引配置合理

## 🚨 关键性能问题

### 问题 1: Notify 表全表扫描（最严重）

**位置**：`backend/apps/scada/view/site.py:853-871`

**当前查询**：
```python
notifies = Notify.objects.all()  # ⚠️ 查询所有记录

# 1. 聚合查询（相对快）
stats = notifies.aggregate(
    total=Count("id"), 
    acknowledged=Count("id", filter=Q(ack=True))
)

# 2. 分组查询（慢）
latest_notify_ids = (
    notifies.values("external_id")
    .annotate(latest_id=Max("id"), latest_notified_at=Max("notified_at"))
    .values("latest_id")
)

# 3. 子查询过滤（非常慢）
activated = notifies.filter(
    id__in=latest_notify_ids, 
    title__endswith="触发警告", 
    ack=False
).count()
```

**问题分析**：
1. `Notify.objects.all()` 查询所有记录（可能数万条）
2. `GROUP BY external_id` 需要对所有记录分组
3. `id__in=latest_notify_ids` 子查询可能包含大量 ID
4. `title__endswith` 无法使用索引（LIKE '%xxx'）
5. `ack=False` 无索引

**影响**：
- 如果 Notify 表有 10,000 条记录，每次全局统计都要扫描全表
- GROUP BY 操作 CPU 密集
- `id__in` 子查询可能包含数千个 ID

### 问题 2: SiteStatistic 的 N+1 查询

**位置**：`backend/apps/scada/view/site.py:750-828`

**当前查询**：
```python
sites = Site.objects.exclude(status=0)
site_ids = list(sites.values_list('id', flat=True))

# 对每个站点单独查询
for site_id in site_ids:
    statistic = SiteStatistic.objects.filter(
        site_id=site_id, name="处理总量"
    ).first()  # ⚠️ N 次查询
```

**问题分析**：
- 如果有 10 个站点，就要执行 10 次数据库查询
- 虽然有缓存，但第一次查询时仍然有 N+1 问题

**影响**：
- 数据库连接开销
- 查询延迟累加

### 问题 3: Variable.objects.count() 全表扫描

**位置**：`backend/apps/scada/view/site.py:742`

**当前查询**：
```python
total_variables = Variable.objects.count()
```

**问题分析**：
- `count()` 需要扫描整个表
- 如果 Variable 表有大量数据，会很慢
- PostgreSQL 的 `count(*)` 在没有索引的情况下需要全表扫描

**影响**：
- 表越大，查询越慢
- CPU 使用率高

## 🔧 优化方案

### 优先级 1: 优化 Notify 表查询（立即实施）

#### 1.1 添加数据库索引

创建迁移文件添加索引：

```python
# apps/scada/migrations/0017_add_notify_indexes.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('scada', '0016_dashboardcard_title'),
    ]

    operations = [
        # 添加 ack 字段索引（用于过滤）
        migrations.AddIndex(
            model_name='notify',
            index=models.Index(fields=['ack'], name='scada_notify_ack_idx'),
        ),
        # 添加复合索引 (external_id, notified_at) - 用于查找最新记录
        migrations.AddIndex(
            model_name='notify',
            index=models.Index(fields=['external_id', 'notified_at'], name='scada_notify_external_notified_idx'),
        ),
        # 添加复合索引 (title, ack) - 用于过滤激活的告警
        migrations.AddIndex(
            model_name='notify',
            index=models.Index(fields=['title', 'ack'], name='scada_notify_title_ack_idx'),
        ),
    ]
```

#### 1.2 优化查询逻辑

**当前问题**：
- `title__endswith="触发警告"` 无法使用索引（LIKE '%触发警告'）

**优化方案**：
1. 如果可能，改为 `title__startswith` 或精确匹配
2. 或者添加全文搜索索引（PostgreSQL GIN 索引）
3. 或者使用 `title LIKE '%触发警告'` 但添加函数索引

**修改代码**：
```python
# 优化：先过滤再分组，减少数据量
notifies = Notify.objects.all()

# 方案1：如果 title 格式固定，可以使用 startswith
# 假设 title 格式是 "site_id::variable_name::触发警告"
# 可以改为：title__endswith="::触发警告" 或使用正则表达式

# 方案2：使用更高效的查询方式
# 先找到所有以"触发警告"结尾的记录，再分组
trigger_notifies = notifies.filter(title__endswith="触发警告", ack=False)
latest_trigger_ids = (
    trigger_notifies.values("external_id")
    .annotate(latest_id=Max("id"))
    .values("latest_id")
)
activated = trigger_notifies.filter(id__in=latest_trigger_ids).count()
```

### 优先级 2: 优化 Site 表查询

#### 2.1 添加 status 字段索引

```python
# apps/scada/migrations/0018_add_site_status_index.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('scada', '0017_add_notify_indexes'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='site',
            index=models.Index(fields=['status'], name='scada_site_status_idx'),
        ),
    ]
```

### 优先级 3: 优化 SiteStatistic 批量查询

#### 3.1 批量查询所有站点的统计配置

**当前代码**：
```python
# 对每个站点单独查询
for site_id in site_ids:
    statistic = SiteStatistic.objects.filter(
        site_id=site_id, name="处理总量"
    ).first()
```

**优化后**：
```python
# 一次性查询所有站点的统计配置
statistics = SiteStatistic.objects.filter(
    site_id__in=site_ids, 
    name="处理总量"
).prefetch_related('variables__module')

# 创建 site_id -> statistic 的映射
statistic_map = {s.site_id: s for s in statistics}

# 然后使用映射
for site_id in site_ids:
    statistic = statistic_map.get(site_id)
    if statistic:
        # 处理统计
```

### 优先级 4: 优化 Variable count 查询

#### 4.1 使用估算值或缓存

**方案1**：使用 PostgreSQL 的统计信息（快速但可能不准确）
```python
from django.db import connection

def get_variable_count_estimate():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT reltuples::bigint AS estimate 
            FROM pg_class 
            WHERE relname = 'scada_variable'
        """)
        return cursor.fetchone()[0]
```

**方案2**：缓存 count 值
```python
from django.core.cache import cache

def get_total_variables():
    cache_key = "total_variables_count"
    count = cache.get(cache_key)
    if count is None:
        count = Variable.objects.count()
        cache.set(cache_key, count, timeout=300)  # 缓存5分钟
    return count
```

## 📈 预期性能提升

### Notify 表优化
- **当前**：全表扫描 + GROUP BY + 子查询 ≈ 2-5 秒
- **优化后**：使用索引过滤 + 优化查询 ≈ 200-500ms
- **提升**：80-90%

### Site 表优化
- **当前**：`exclude(status=0).count()` ≈ 50-100ms
- **优化后**：使用索引 ≈ 5-10ms
- **提升**：80-90%

### SiteStatistic 批量查询
- **当前**：N 次查询（N = 站点数）≈ N × 10ms
- **优化后**：1 次查询 ≈ 20-50ms
- **提升**：90%+（站点数越多提升越明显）

### Variable count 优化
- **当前**：全表扫描 ≈ 100-500ms（取决于表大小）
- **优化后**：缓存或估算 ≈ 1-5ms
- **提升**：95%+

## 🎯 实施建议

### 立即实施（高优先级）
1. ✅ 添加 Notify 表索引（`ack`, `(external_id, notified_at)`, `(title, ack)`）
2. ✅ 添加 Site 表 `status` 索引
3. ✅ 优化 `get_global_statistics` 中的 Notify 查询逻辑

### 短期实施（中优先级）
4. ✅ 优化 SiteStatistic 批量查询
5. ✅ Variable count 使用缓存

### 长期优化（低优先级）
6. ✅ 考虑使用 PostgreSQL 的物化视图（Materialized Views）
7. ✅ 定期清理旧的 Notify 记录（归档策略）

## 📝 索引创建 SQL（参考）

```sql
-- Notify 表索引
CREATE INDEX scada_notify_ack_idx ON scada_notify(ack);
CREATE INDEX scada_notify_external_notified_idx ON scada_notify(external_id, notified_at DESC);
CREATE INDEX scada_notify_title_ack_idx ON scada_notify(title, ack);

-- Site 表索引
CREATE INDEX scada_site_status_idx ON scada_site(status);

-- Variable 表索引（确认外键索引存在）
-- Django 默认会为 ForeignKey 创建索引，但可以显式添加
CREATE INDEX IF NOT EXISTS scada_variable_module_id_idx ON scada_variable(module_id);

-- SiteStatistic 表索引（确认唯一约束索引）
-- unique_together 会自动创建索引，但可以显式添加
CREATE INDEX IF NOT EXISTS scada_sitestatistic_site_name_idx ON scada_sitestatistic(site_id, name);
```

## 🔍 监控建议

1. **启用 PostgreSQL 慢查询日志**
2. **使用 `EXPLAIN ANALYZE` 分析查询计划**
3. **监控索引使用情况**：`pg_stat_user_indexes`
4. **定期分析表统计信息**：`ANALYZE`

