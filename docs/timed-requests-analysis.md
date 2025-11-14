# 定时请求性能分析报告

## 🔍 问题概述

数据库 CPU 使用率有固定间隔的峰值，说明是定时任务导致的。需要分析所有定时请求的数据库操作并优化。

## 📊 定时请求清单

### 1. 客户端定时器 - Dashboard 卡片数据更新（每5秒）

**位置**：`hetu-scada-client/src/views/dashboard/index.vue:710-712`

**请求频率**：每 5 秒 (`UPDATE_INTERVAL = 5000`)

**调用的接口**：
1. `POST /api/scada/{site_id}/variable/values` - 获取实时值
2. `POST /api/scada/{site_id}/variable/range` - 获取历史数据（图表卡片）

**数据库操作**：
```python
# 1. read_values() - backend/apps/scada/view/variable.py:114
vars = Variable.objects.filter(id__in=payload.variable_ids, module__site_id=site_id)
grouped_vars = vars.select_related("module").values("module_id", "module__module_number").distinct()
# 对每个模块：
module_vars = vars.filter(module_id=module_id)  # ⚠️ N+1 查询问题

# 2. query_range() - backend/apps/scada/view/variable.py:178
vars = Variable.objects.filter(id__in=payload.variable_ids, module__site_id=site_id)
if vars.count() != len(payload.variable_ids):  # ⚠️ count() 查询
grouped_vars = vars.select_related("module").values("module_id", "module__module_number").distinct()
# 对每个模块：
module_vars = vars.filter(module_id=module_id)  # ⚠️ N+1 查询问题
```

**问题**：
- `vars.count()` 每次都要执行 COUNT 查询
- `vars.filter(module_id=module_id)` 在循环中执行，存在 N+1 查询问题
- 每 5 秒执行一次，频率很高

**影响**：
- 如果有 3 个模块，每次更新需要 3+ 次数据库查询
- 如果有 10 个客户端同时在线，每秒就有 20+ 次查询

---

### 2. 客户端定时器 - Graph 视图变量数据（每5秒）

**位置**：`hetu-scada-client/src/views/graph/composables/data.ts:154-156`

**请求频率**：每 5 秒（默认 `interval = 5000`）

**调用的接口**：
- `POST /api/scada/{site_id}/variable/values` - 获取实时值

**数据库操作**：同上面的 `read_values()`

**问题**：同上

---

### 3. 客户端定时器 - 告警通知轮询（每10秒）

**位置**：`hetu-scada-client/src/stores/notification.ts:148-150`

**请求频率**：每 10 秒 (`startGlobalPolling(interval = 10000)`)

**调用的接口**：
- `GET /api/scada/{site_id}/alert/notify/activated` - 获取激活的告警

**数据库操作**：
```python
# backend/apps/scada/view/alert.py:332-366
notifies = Notify.objects.filter(title__startswith=site_filter, external_id=external_id)
latest_record_ids = (
    notifies.filter(external_id=OuterRef("external_id"))
    .order_by("-notified_at", "-id")
    .values("id")[:1]
)
activated_notifies = Notify.objects.filter(
    id=Subquery(latest_record_ids), 
    title__endswith="触发警告", 
    ack=False
)
```

**问题**：
- 复杂的子查询（Subquery + OuterRef）
- `title__endswith` 无法使用索引
- 每 10 秒执行一次

**影响**：
- 如果 Notify 表有大量数据，查询会很慢
- 如果有多个客户端，查询频率会叠加

---

### 4. Prometheus 服务发现（每10秒）

**位置**：`backend/apps/scada/view/collector.py:165-193`

**请求频率**：每 10 秒 (`refresh_interval: 10s`)

**调用的接口**：
- `GET /api/scada/collector/sd` - Prometheus HTTP SD

**数据库操作**：
```python
collectors = Collector.objects.all()  # ⚠️ 查询所有采集器
for c in collectors:
    # 对每个采集器调用 supervisor RPC
    info = rpc.supervisor.getProcessInfo(process_name)
```

**问题**：
- `Collector.objects.all()` 查询所有采集器
- 对每个采集器调用 supervisor RPC（可能很慢）
- Prometheus 每 10 秒调用一次，频率很高

**影响**：
- 如果有 10 个采集器，每次需要 10 次 RPC 调用
- 如果 RPC 调用慢，会阻塞请求

---

### 5. Prometheus 抓取（每15秒）

**频率**：每 15 秒 (`scrape_interval: 15s`)

**操作**：Prometheus 抓取各个 exporter 的指标

**影响**：不直接涉及数据库，但会增加系统负载

---

## 🚨 关键性能问题

### 问题 1: Variable 查询的 N+1 问题（最严重）

**位置**：`backend/apps/scada/view/variable.py:114-153, 178-247`

**当前代码**：
```python
vars = Variable.objects.filter(id__in=payload.variable_ids, module__site_id=site_id)
grouped_vars = vars.select_related("module").values("module_id", "module__module_number").distinct()

# ⚠️ 问题：在循环中重复查询
for entry in grouped_vars:
    module_id = entry["module_id"]
    module_vars = vars.filter(module_id=module_id)  # 每次都是新的查询
```

**问题分析**：
- `vars.filter(module_id=module_id)` 在循环中执行，每次都是新的数据库查询
- 如果有 3 个模块，就需要 3 次额外的查询
- 每 5 秒执行一次，频率很高

**优化方案**：
```python
# 一次性查询所有变量，在内存中分组
vars = Variable.objects.filter(
    id__in=payload.variable_ids, 
    module__site_id=site_id
).select_related("module")

# 在内存中按模块分组
module_vars_map = {}
for v in vars:
    module_id = v.module_id
    if module_id not in module_vars_map:
        module_vars_map[module_id] = {
            'module_number': v.module.module_number,
            'vars': []
        }
    module_vars_map[module_id]['vars'].append(v)

# 然后遍历分组
for module_id, module_data in module_vars_map.items():
    module_number = module_data['module_number']
    module_vars = module_data['vars']
    # ... 处理逻辑
```

### 问题 2: vars.count() 查询

**位置**：`backend/apps/scada/view/variable.py:179`

**当前代码**：
```python
if vars.count() != len(payload.variable_ids):
    raise HttpError(404, "Some variables not found")
```

**问题**：
- `count()` 需要执行 COUNT 查询
- 可以改为检查查询结果数量

**优化方案**：
```python
# 优化：直接检查查询结果数量，避免 COUNT 查询
vars_list = list(vars)
if len(vars_list) != len(payload.variable_ids):
    raise HttpError(404, "Some variables not found")
```

### 问题 3: Collector.objects.all() 无缓存

**位置**：`backend/apps/scada/view/collector.py:169`

**当前代码**：
```python
collectors = Collector.objects.all()
```

**问题**：
- 每 10 秒查询一次，但采集器配置变化不频繁
- 可以添加缓存

**优化方案**：
```python
from django.core.cache import cache

def service_discover(request):
    cache_key = "collector_list"
    collectors = cache.get(cache_key)
    if collectors is None:
        collectors = list(Collector.objects.all())
        cache.set(cache_key, collectors, timeout=60)  # 缓存1分钟
```

### 问题 4: 告警查询的复杂子查询

**位置**：`backend/apps/scada/view/alert.py:332-366`

**问题**：
- 使用 Subquery + OuterRef，性能较差
- `title__endswith` 无法使用索引

**优化方案**：
- 已在之前的优化中添加索引
- 可以进一步优化查询逻辑（参考 `get_global_statistics` 的优化）

---

## 🔧 优化方案

### 优先级 1: 优化 Variable 查询（立即实施）

#### 1.1 修复 N+1 查询问题

**文件**：`backend/apps/scada/view/variable.py`

**修改**：
- `read_values()`: 在内存中分组，避免循环查询
- `query_range()`: 在内存中分组，避免循环查询
- 移除 `vars.count()`，改为检查列表长度

#### 1.2 添加查询结果缓存

**考虑**：
- Variable 配置变化不频繁
- 可以缓存变量到模块的映射关系
- 但变量值需要实时查询，不能缓存

### 优先级 2: 优化 Collector 服务发现

#### 2.1 添加缓存

**文件**：`backend/apps/scada/view/collector.py`

**修改**：
- 缓存 Collector 列表（1分钟）
- 缓存 supervisor 状态（30秒）

### 优先级 3: 优化告警查询

#### 3.1 使用已优化的查询逻辑

**文件**：`backend/apps/scada/view/alert.py`

**修改**：
- 参考 `get_global_statistics` 的优化逻辑
- 先过滤再分组，减少数据量

---

## 📈 预期性能提升

### Variable 查询优化

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 3个模块，每5秒查询 | 4次查询/次 | 1次查询/次 | 75% |
| 10个客户端同时在线 | 40次查询/秒 | 10次查询/秒 | 75% |

### Collector 服务发现优化

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 10个采集器，每10秒查询 | 10次RPC/次 | 0次RPC/次（缓存） | 100% |
| 数据库查询 | 1次查询/次 | 0.017次查询/次（缓存60秒） | 98% |

### 总体数据库负载

**预期降低**：60-80%

**原因**：
1. Variable 查询从 N+1 减少到 1 次
2. Collector 查询使用缓存，减少 98% 查询
3. 移除不必要的 `count()` 查询

---

## 🎯 实施步骤

### 步骤 1: 优化 Variable 查询（高优先级）

1. 修改 `read_values()` 函数
2. 修改 `query_range()` 函数
3. 移除 `vars.count()` 查询

### 步骤 2: 优化 Collector 服务发现（中优先级）

1. 添加 Collector 列表缓存
2. 添加 supervisor 状态缓存

### 步骤 3: 监控和验证

1. 部署优化后的代码
2. 监控数据库 CPU 使用率
3. 验证定时请求的响应时间

