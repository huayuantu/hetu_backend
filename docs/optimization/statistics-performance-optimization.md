# 统计数据性能优化方案

## 当前性能问题分析

根据前端日志，三个统计请求的耗时都在 5-6 秒：
- **处理预警统计**: 5392ms
- **处理总量统计**: 5461ms  
- **监控点数统计**: 5593ms

### 1. 处理总量统计（5461ms）性能瓶颈

**当前实现** (`backend/apps/scada/view/site.py:299-340`):
```python
def get_statistic_value(...):
    for v in statistic.variables.all():
        query_str = "grm_" + v.module.module_number + "_gauge"
        query_str += '{name="' + v.name + '"}'
        query_data = promql_query(query_str)  # 每个变量单独查询 Prometheus
```

**问题**:
- 每个变量都单独调用 `promql_query`，串行执行
- 如果统计量包含 N 个变量，需要 N 次 HTTP 请求到 Prometheus
- 每次请求都有网络延迟（3-5秒超时设置）

**优化方案**:
1. **批量 PromQL 查询**（优先级：高）
   - 参考 `read_values` 的实现（`variable.py:108-153`），使用正则表达式批量查询
   - 将同一模块的变量合并为一个 PromQL 查询：`grm_{module_number}_gauge{name=~"var1|var2|var3"}`
   - 预期提升：从 N 次查询减少到按模块分组查询（通常 1-3 次）

2. **并行查询多个站点**（优先级：中）
   - 后端新增批量统计接口：`POST /scada/site/statistics/batch`
   - 接收多个 `site_id` 和 `statistic_name`，并行查询
   - 预期提升：3 个站点从串行 15 秒减少到并行 5 秒

3. **缓存机制**（优先级：中）
   - 统计值缓存 30-60 秒（Redis 或内存缓存）
   - 使用 `@cache_page` 或 Django cache framework
   - 预期提升：缓存命中时从 5 秒减少到 <100ms

### 2. 监控点数统计（5593ms）性能瓶颈

**当前实现**（前端并行请求）:
- 对每个站点：`get_module_list` → 对每个模块：`get_variable_list`
- 3 个站点 × N 个模块 = 多次数据库查询

**问题**:
- 虽然前端并行请求，但每个请求都需要数据库查询
- 如果站点有多个模块，需要多次查询变量列表

**优化方案**:
1. **批量查询接口**（优先级：高）
   - 新增接口：`GET /scada/site/variables/count?site_ids=1,2,3`
   - 使用 Django ORM 的 `select_related` 和 `prefetch_related` 优化查询
   - 一次查询返回所有站点的变量总数
   - 预期提升：从多次查询减少到 1-2 次查询，总耗时 <500ms

2. **数据库索引优化**（优先级：中）
   - 确保 `Variable.module_id` 有索引
   - 确保 `Module.site_id` 有索引
   - 预期提升：查询速度提升 50-80%

### 3. 处理预警统计（5392ms）性能瓶颈

**当前实现** (`backend/apps/scada/view/alert.py:414-458`):
```python
def get_notify_count(request, site_id: int = None):
    # 1. 总数查询
    total = notifies.count()
    
    # 2. 已确认数查询
    acknowledged = notifies.filter(ack=True).count()
    
    # 3. 激活数查询（复杂子查询）
    latest_record_ids = (
        site_notifies.filter(external_id=OuterRef("external_id"))
        .order_by("-notified_at", "-id")
        .values("id")[:1]
    )
    activated_notifies = Notify.objects.filter(
        id=Subquery(latest_record_ids), 
        title__endswith="触发警告", 
        ack=False
    )
    activated = activated_notifies.count()
```

**问题**:
- 当 `site_id=None` 时，查询所有通知（35587 条）
- 3 次独立的数据库查询
- 激活数查询使用了复杂的子查询（Subquery + OuterRef），性能较差

**优化方案**:
1. **合并查询**（优先级：高）
   - 使用 `annotate` 和 `aggregate` 一次性计算所有统计值
   - 使用 `Case/When` 条件聚合，减少查询次数
   - 预期提升：从 3 次查询减少到 1 次，耗时减少 60-70%

2. **优化激活数查询**（优先级：高）
   - 使用窗口函数（Window functions）替代子查询
   - 或使用 `distinct` + `values` 优化
   - 预期提升：激活数查询从 2-3 秒减少到 <500ms

3. **数据库索引优化**（优先级：高）
   - 添加复合索引：`(title, notified_at, id)` 用于激活数查询
   - 添加索引：`(ack, title)` 用于已确认数查询
   - 添加索引：`(external_id, notified_at DESC, id DESC)` 用于子查询
   - 预期提升：查询速度提升 70-90%

4. **缓存机制**（优先级：中）
   - 通知计数缓存 10-30 秒
   - 预期提升：缓存命中时从 5 秒减少到 <100ms

## 实施优先级

### 第一阶段（立即实施，预期总耗时 <2 秒）
1. ✅ **处理总量统计**：批量 PromQL 查询
2. ✅ **处理预警统计**：合并查询 + 数据库索引
3. ✅ **监控点数统计**：批量查询接口

### 第二阶段（短期优化，预期总耗时 <1 秒）
4. ⏳ **处理总量统计**：批量站点查询接口
5. ⏳ **所有统计**：添加缓存机制（30-60 秒）

### 第三阶段（长期优化，预期总耗时 <500ms）
6. ⏳ **数据库查询优化**：添加所有必要的索引
7. ⏳ **Prometheus 查询优化**：连接池、请求合并

## 预期效果

| 统计项 | 当前耗时 | 第一阶段后 | 第二阶段后 | 第三阶段后 |
|--------|---------|-----------|-----------|-----------|
| 处理总量 | 5461ms | ~1500ms | ~200ms | ~100ms |
| 监控点数 | 5593ms | ~500ms | ~100ms | ~50ms |
| 处理预警 | 5392ms | ~800ms | ~100ms | ~50ms |
| **总计** | **~5600ms** | **~2800ms** | **~400ms** | **~200ms** |

## 实施建议

1. **先实施数据库索引优化**（风险低，收益高）
2. **然后优化查询逻辑**（合并查询、批量查询）
3. **最后添加缓存**（需要处理缓存失效策略）

## 注意事项

1. **缓存失效**：统计数据更新时需要清除缓存
2. **Prometheus 性能**：批量查询可能增加 Prometheus 负载，需要监控
3. **数据库连接**：批量查询可能增加数据库连接数，需要配置连接池
4. **向后兼容**：新增批量接口不影响现有接口

