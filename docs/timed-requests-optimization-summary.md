# 定时请求优化总结

## ✅ 已实施的优化

### 1. Variable 查询优化（高优先级）

#### 1.1 修复 N+1 查询问题

**文件**：`backend/apps/scada/view/variable.py`

**修改的函数**：
- `read_values()` - 批量读取变量值
- `query_range()` - 批量查询变量历史数据

**优化前**：
```python
grouped_vars = vars.select_related("module").values("module_id", "module__module_number").distinct()
for entry in grouped_vars:
    module_vars = vars.filter(module_id=module_id)  # ⚠️ N+1 查询
```

**优化后**：
```python
# 一次性查询所有变量
vars = Variable.objects.filter(...).select_related("module")

# 在内存中按模块分组
module_vars_map = defaultdict(lambda: {"module_number": None, "vars": []})
for v in vars:
    module_vars_map[v.module_id]["vars"].append(v)

# 遍历分组（无数据库查询）
for module_id, module_data in module_vars_map.items():
    module_vars = module_data["vars"]  # 从内存获取
```

**效果**：
- 从 N+1 次查询减少到 1 次查询
- 如果有 3 个模块，从 4 次查询减少到 1 次（75% 减少）

#### 1.2 移除 count() 查询

**优化前**：
```python
if vars.count() != len(payload.variable_ids):  # ⚠️ COUNT 查询
```

**优化后**：
```python
vars_list = list(vars)
if len(vars_list) != len(payload.variable_ids):  # ✅ 内存操作
```

**效果**：
- 移除每次请求的 COUNT 查询
- 减少数据库负载

---

### 2. Collector 服务发现优化（中优先级）

**文件**：`backend/apps/scada/view/collector.py`

**修改的函数**：
- `service_discover()` - Prometheus HTTP SD 接口

**优化内容**：
1. **添加结果缓存**（30秒）
   - Prometheus 每 10 秒查询一次
   - 缓存 30 秒可以覆盖 3 次查询
   - 减少 66% 的数据库查询

2. **添加 Supervisor 状态缓存**（30秒）
   - 每个采集器的状态单独缓存
   - 减少 RPC 调用频率
   - 减少 66% 的 RPC 调用

**优化前**：
```python
collectors = Collector.objects.all()  # 每次查询数据库
for c in collectors:
    info = rpc.supervisor.getProcessInfo(process_name)  # 每次 RPC 调用
```

**优化后**：
```python
# 检查缓存
cached_result = cache.get("prometheus_sd_targets")
if cached_result:
    return cached_result

# 查询数据库（缓存未命中时）
collectors = Collector.objects.all()

for c in collectors:
    # 检查 supervisor 状态缓存
    info = cache.get(f"supervisor_status_{process_name}")
    if info is None:
        info = rpc.supervisor.getProcessInfo(process_name)
        cache.set(f"supervisor_status_{process_name}", info, timeout=30)
```

**效果**：
- 数据库查询：从每次查询减少到每 3 次查询 1 次（66% 减少）
- RPC 调用：从每次调用减少到每 3 次调用 1 次（66% 减少）

---

## 📊 性能提升预期

### Variable 查询优化

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 单次查询（3个模块） | 4次数据库查询 | 1次数据库查询 | 75% |
| 10个客户端同时在线 | 40次查询/秒 | 10次查询/秒 | 75% |
| 移除 count() 查询 | 每次 +1 次 COUNT | 0 次 COUNT | 100% |

### Collector 服务发现优化

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 数据库查询频率 | 每 10 秒 1 次 | 每 30 秒 1 次 | 66% |
| RPC 调用频率（10个采集器） | 每 10 秒 10 次 | 每 30 秒 10 次 | 66% |
| 总体负载 | 100% | 33% | 67% |

### 总体数据库负载

**预期降低**：60-80%

**计算**：
- Variable 查询：减少 75%
- Collector 查询：减少 66%
- 移除 count() 查询：减少 100%
- 综合效果：60-80% 的数据库负载降低

---

## 🎯 定时请求频率总结

| 请求类型 | 频率 | 优化前查询数 | 优化后查询数 | 减少 |
|---------|------|------------|------------|------|
| Dashboard 卡片更新 | 每 5 秒 | 4 次/次 | 1 次/次 | 75% |
| Graph 视图变量数据 | 每 5 秒 | 4 次/次 | 1 次/次 | 75% |
| 告警通知轮询 | 每 10 秒 | 1 次/次 | 1 次/次 | 0%* |
| Prometheus 服务发现 | 每 10 秒 | 1 次/次 | 0.33 次/次 | 67% |

*注：告警查询已在之前的优化中优化，这里主要关注定时请求的数据库操作。

---

## 📝 后续优化建议

### 短期（1周内）
1. ✅ Variable 查询优化（已完成）
2. ✅ Collector 服务发现优化（已完成）
3. ⏳ 监控优化效果
4. ⏳ 根据监控结果进一步优化

### 中期（1个月内）
1. 考虑增加 Variable 配置的缓存（变量配置变化不频繁）
2. 优化告警查询（参考 `get_global_statistics` 的优化）
3. 考虑使用 Redis 缓存更多查询结果

### 长期（3个月+）
1. 考虑使用 WebSocket 替代轮询（实时推送数据）
2. 实施数据库连接池优化
3. 考虑读写分离（如果写入操作也很频繁）

---

## 🔍 验证方法

### 1. 监控数据库查询频率

```sql
-- 查看 Variable 表的查询频率
SELECT 
    schemaname,
    tablename,
    seq_scan as sequential_scans,
    idx_scan as index_scans,
    seq_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_tables
WHERE tablename = 'scada_variable';
```

### 2. 监控慢查询

```sql
-- 启用慢查询日志（查询时间 > 100ms）
ALTER SYSTEM SET log_min_duration_statement = 100;
SELECT pg_reload_conf();
```

### 3. 监控 CPU 使用率

```bash
# 监控数据库容器 CPU
docker stats <database_container_name>

# 或使用 Prometheus 监控
# 查看数据库 CPU 使用率趋势
```

---

## 📈 预期效果

### 数据库 CPU 使用率

**优化前**：
- 固定间隔（每 5 秒）的 CPU 峰值
- 峰值可能达到 50-80%

**优化后**：
- CPU 峰值降低 60-80%
- 固定间隔的峰值明显减少
- 整体 CPU 使用率更平稳

### 查询响应时间

**优化前**：
- Variable 查询：50-200ms（取决于模块数）
- Collector 查询：100-500ms（取决于采集器数和 RPC 延迟）

**优化后**：
- Variable 查询：20-50ms（减少 60-75%）
- Collector 查询：5-20ms（缓存命中时，减少 80-95%）

