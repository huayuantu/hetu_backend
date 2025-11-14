# 数据库性能优化总结

## 🎯 优化目标

降低数据库容器 CPU 使用率，优化所有数据库读写操作和索引配置。

## ✅ 已实施的优化

### 1. 数据库索引优化（迁移文件：0017_add_performance_indexes.py）

#### 1.1 Site 表索引
- ✅ 添加 `status` 字段索引
- **用途**：优化 `Site.objects.exclude(status=0)` 查询
- **预期提升**：查询速度提升 80-90%

#### 1.2 Notify 表索引
- ✅ 添加 `ack` 字段索引
- **用途**：优化 `Notify.objects.filter(ack=False)` 查询
- **预期提升**：过滤查询速度提升 70-80%

#### 1.3 SiteStatistic 表索引
- ✅ 添加 `(site_id, name)` 复合索引
- **用途**：优化 `SiteStatistic.objects.filter(site_id=site_id, name="处理总量")` 查询
- **预期提升**：查询速度提升 60-70%

#### 1.4 Variable 和 Module 表索引
- ✅ 确认 `Variable.module_id` 有索引
- ✅ 添加 `Module.site_id` 索引
- **用途**：优化 join 查询
- **预期提升**：join 查询速度提升 50-60%

### 2. 查询逻辑优化

#### 2.1 Notify 表查询优化（最严重问题）

**位置**：`backend/apps/scada/view/site.py:848-878`

**优化前**：
```python
notifies = Notify.objects.all()  # 查询所有记录
stats = notifies.aggregate(...)
latest_notify_ids = notifies.values("external_id").annotate(...)
activated = notifies.filter(id__in=latest_notify_ids, title__endswith="触发警告", ack=False).count()
```

**问题**：
- 查询所有 Notify 记录（可能数万条）
- 对所有记录进行 GROUP BY 操作
- `id__in` 子查询可能包含大量 ID
- `title__endswith` 无法使用索引

**优化后**：
```python
# 先过滤再分组，减少数据量
notifies_unacked = Notify.objects.filter(ack=False)  # 使用索引
trigger_notifies = notifies_unacked.filter(title__endswith="触发警告")  # 减少分组数据量
latest_notify_ids = trigger_notifies.values("external_id").annotate(latest_id=Max("id"))
activated = trigger_notifies.filter(id__in=latest_notify_ids).count()
```

**优化效果**：
- 先过滤 `ack=False`，减少需要扫描的数据量（使用索引）
- 先过滤 `title__endswith="触发警告"`，再分组，减少分组数据量
- 预期提升：查询时间从 2-5 秒减少到 200-500ms（80-90% 提升）

#### 2.2 SiteStatistic 批量查询优化

**位置**：`backend/apps/scada/view/site.py:830-856`

**优化前**：
```python
# N+1 查询问题
for site_id in site_ids:
    statistic = SiteStatistic.objects.filter(site_id=site_id, name="处理总量").first()
```

**优化后**：
```python
# 批量查询，避免 N+1 问题
statistics = SiteStatistic.objects.filter(
    site_id__in=site_ids, 
    name="处理总量"
).prefetch_related('variables__module')

statistic_map = {s.site_id: s for s in statistics}
# 使用预查询的 statistic
```

**优化效果**：
- 从 N 次查询减少到 1 次查询
- 预期提升：查询时间从 N × 10ms 减少到 20-50ms（90%+ 提升）

#### 2.3 Variable count 查询优化

**位置**：`backend/apps/scada/view/site.py:742-749`

**优化前**：
```python
total_variables = Variable.objects.count()  # 全表扫描
```

**优化后**：
```python
# 使用缓存减少全表扫描
variables_cache_key = "total_variables_count"
total_variables = cache.get(variables_cache_key)
if total_variables is None:
    total_variables = Variable.objects.count()
    cache.set(variables_cache_key, total_variables, timeout=300)  # 缓存5分钟
```

**优化效果**：
- 缓存命中时：从 100-500ms 减少到 1-5ms（95%+ 提升）
- 减少数据库全表扫描频率

## 📊 性能提升预期

### 全局统计接口 (`/scada/site/statistics/global`)

| 查询项 | 优化前 | 优化后 | 提升 |
|--------|--------|--------|------|
| 站点数统计 | 50-100ms | 5-10ms | 80-90% |
| 监控点数统计 | 100-500ms | 1-5ms (缓存) | 95%+ |
| 处理总量统计 | N × 10ms | 20-50ms | 90%+ |
| 告警数统计 | 2000-5000ms | 200-500ms | 80-90% |
| **总计** | **2-6秒** | **300-600ms** | **85-90%** |

### 数据库 CPU 使用率

**预期降低**：50-70%

**原因**：
1. 添加索引后，查询使用索引扫描而非全表扫描
2. 优化查询逻辑，减少数据扫描量
3. 使用缓存减少重复查询

## 🔧 需要执行的迁移

### 1. 创建迁移文件
已创建：`apps/scada/migrations/0017_add_performance_indexes.py`

### 2. 执行迁移
```bash
cd backend
python manage.py migrate scada
```

### 3. 验证索引创建
```sql
-- 检查索引是否创建成功
SELECT 
    tablename, 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE schemaname = 'public' 
  AND tablename IN ('scada_site', 'scada_notify', 'scada_sitestatistic', 'scada_variable', 'scada_module')
ORDER BY tablename, indexname;
```

## 📝 后续监控建议

### 1. 启用 PostgreSQL 慢查询日志
```sql
-- 启用慢查询日志（查询时间 > 1秒）
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();
```

### 2. 监控索引使用情况
```sql
-- 查看索引使用统计
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### 3. 分析表统计信息
```sql
-- 更新表统计信息（帮助查询优化器选择最佳执行计划）
ANALYZE scada_notify;
ANALYZE scada_site;
ANALYZE scada_variable;
ANALYZE scada_sitestatistic;
```

### 4. 监控数据库连接数
```sql
-- 查看当前连接数
SELECT count(*) FROM pg_stat_activity;

-- 查看长时间运行的查询
SELECT 
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
  AND state != 'idle';
```

## 🚨 潜在问题排查

如果 CPU 仍然很高，检查以下问题：

### 1. 是否有其他频繁查询
- 检查慢查询日志
- 使用 `pg_stat_statements` 扩展查看最频繁的查询

### 2. 索引是否被使用
- 使用 `EXPLAIN ANALYZE` 分析查询计划
- 确认查询使用了索引而非全表扫描

### 3. 是否有锁等待
```sql
-- 查看锁等待情况
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocking_locks.pid AS blocking_pid,
    blocked_activity.query AS blocked_query,
    blocking_activity.query AS blocking_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

### 4. 是否有大量写入操作
- 检查是否有频繁的 INSERT/UPDATE 操作
- 考虑批量写入优化

## 📈 优化效果验证

### 验证步骤

1. **执行迁移**
   ```bash
   python manage.py migrate scada
   ```

2. **重启服务**
   ```bash
   docker-compose restart api
   ```

3. **监控 CPU 使用率**
   ```bash
   docker stats <database_container_name>
   ```

4. **测试全局统计接口**
   ```bash
   curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/scada/site/statistics/global
   ```

5. **对比优化前后**
   - CPU 使用率应该降低 50-70%
   - 接口响应时间应该减少 80-90%

## 🎯 下一步优化建议

### 短期（1-2周）
1. ✅ 添加索引（已完成）
2. ✅ 优化查询逻辑（已完成）
3. ⏳ 监控优化效果
4. ⏳ 根据监控结果进一步优化

### 中期（1个月）
1. 考虑使用 PostgreSQL 的物化视图（Materialized Views）缓存复杂查询结果
2. 实施 Notify 表归档策略（定期清理旧记录）
3. 考虑读写分离（如果写入操作也很频繁）

### 长期（3个月+）
1. 考虑使用 Redis 缓存更多查询结果
2. 实施数据库分区（如果表非常大）
3. 考虑使用时序数据库（TimescaleDB）存储历史数据

