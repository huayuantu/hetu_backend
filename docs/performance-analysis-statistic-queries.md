# 统计查询性能分析报告

## 📊 查询概览

**查询1**: `/api/scada/site/1/statistic?statistic_name=处理总量`
- 响应码: 200
- 响应大小: 182 字节
- 站点ID: 1

**查询2**: `/api/scada/site/10/statistic?statistic_name=处理总量`
- 响应码: 200
- 响应大小: 161 字节
- 站点ID: 10

## 🔍 代码路径分析

### 实现位置
`backend/apps/scada/view/site.py:341-402` - `get_statistic_value()`

### 执行流程

```python
def get_statistic_value(request, site_id: int, statistic_id: int = None, statistic_name: str = None):
    # 1. 数据库查询：查找统计量配置
    statistic = SiteStatistic.objects.filter(
        site_id=site_id, name=statistic_name
    ).first()  # ⚠️ 问题1: 没有使用 select_related/prefetch_related
    
    # 2. 数据库查询：获取关联的变量
    variables = statistic.variables.select_related("module").all()  
    # ⚠️ 问题2: ManyToMany关系应该用 prefetch_related，不是 select_related
    
    # 3. 按模块分组变量
    module_vars = defaultdict(list)
    for v in variables:
        module_vars[v.module.module_number].append(v)
    
    # 4. 串行查询 Prometheus（每个模块一个查询）
    for module_number, vars_list in module_vars.items():
        query_str = "grm_" + module_number + "_gauge"
        query_str += '{name=~"' + "|".join(var_names) + '"}'
        query_data = promql_query(query_str)  # ⚠️ 问题3: 串行执行
```

## ⚠️ 性能问题分析

### 问题1: ManyToMany关系查询优化不足

**当前代码** (第361行):
```python
variables = statistic.variables.select_related("module").all()
```

**问题**:
- `select_related()` 只适用于 ForeignKey 和 OneToOne 关系
- `variables` 是 ManyToMany 关系，应该使用 `prefetch_related()`
- 当前实现可能导致 N+1 查询问题

**影响**:
- 如果统计量包含 N 个变量，可能产生 N+1 次数据库查询
- 每次查询变量时都需要额外查询关联的 module

**优化方案**:
```python
# 使用 prefetch_related 预加载 ManyToMany 关系和相关对象
variables = statistic.variables.prefetch_related("module").all()
```

### 问题2: Prometheus查询串行执行

**当前代码** (第374-383行):
```python
for module_number, vars_list in module_vars.items():
    query_data = promql_query(query_str)  # 串行执行
```

**问题**:
- 如果站点有多个模块（例如3个模块），会串行执行3次 Prometheus 查询
- 每次查询都有网络延迟（timeout=(3, 5)秒）
- 总耗时 = 模块数 × 单次查询耗时

**影响**:
- 站点1: 假设有2个模块，总耗时 ≈ 2 × 2秒 = 4秒
- 站点10: 假设有1个模块，总耗时 ≈ 1 × 2秒 = 2秒
- 如果模块更多，耗时线性增长

**优化方案**:
```python
# 使用并发查询（asyncio 或 threading）
import concurrent.futures

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(promql_query, query_str): module_number
        for module_number, query_str in queries.items()
    }
    for future in concurrent.futures.as_completed(futures):
        query_data = future.result()
```

### 问题3: 缺少数据库索引

**当前查询**:
```python
SiteStatistic.objects.filter(site_id=site_id, name=statistic_name).first()
```

**问题**:
- 查询条件：`site_id` + `name`
- 需要检查是否有复合索引 `(site_id, name)`

**检查索引**:
```sql
-- 检查索引
SELECT 
    tablename, 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename = 'scada_sitestatistic';
```

**优化方案**:
```python
# 如果缺少索引，添加迁移
class Meta:
    unique_together = [["name", "site"]]  # 已有唯一约束，但需要确认索引
    indexes = [
        models.Index(fields=['site_id', 'name']),  # 确保有索引
    ]
```

### 问题4: 没有缓存机制

**问题**:
- 统计值可能不会频繁变化
- 每次请求都重新计算，浪费资源
- 相同查询重复执行

**优化方案**:
```python
from django.core.cache import cache

def get_statistic_value(...):
    cache_key = f"statistic:{site_id}:{statistic_name}"
    cached_value = cache.get(cache_key)
    if cached_value:
        return cached_value
    
    # 计算统计值
    result = calculate_statistic(...)
    
    # 缓存30秒
    cache.set(cache_key, result, timeout=30)
    return result
```

## 📈 性能瓶颈估算

### 当前性能（估算）

| 步骤 | 站点1（2模块） | 站点10（1模块） | 说明 |
|------|---------------|----------------|------|
| 数据库查询统计量 | ~10ms | ~10ms | 1次查询 |
| 数据库查询变量 | ~50ms | ~30ms | N+1查询问题 |
| Prometheus查询（串行） | ~4000ms | ~2000ms | 2×2秒 vs 1×2秒 |
| 数据处理 | ~10ms | ~10ms | 内存操作 |
| **总计** | **~4070ms** | **~2050ms** | 主要瓶颈在Prometheus |

### 优化后性能（预期）

| 步骤 | 站点1（2模块） | 站点10（1模块） | 说明 |
|------|---------------|----------------|------|
| 数据库查询统计量 | ~5ms | ~5ms | 使用索引 |
| 数据库查询变量 | ~20ms | ~15ms | prefetch_related |
| Prometheus查询（并行） | ~2000ms | ~2000ms | 并行执行 |
| 数据处理 | ~10ms | ~10ms | 内存操作 |
| **总计** | **~2035ms** | **~2020ms** | 提升约50% |

### 添加缓存后（预期）

| 场景 | 站点1 | 站点10 | 说明 |
|------|------|--------|------|
| 缓存命中 | ~35ms | ~30ms | 直接从缓存读取 |
| 缓存未命中 | ~2035ms | ~2020ms | 正常查询 |

## 🎯 优化建议（按优先级）

### 优先级1: 修复ManyToMany查询（立即实施）

**修改代码**:
```python
# 第361行
variables = statistic.variables.prefetch_related("module").all()
```

**预期提升**: 数据库查询从 ~50ms 减少到 ~20ms

### 优先级2: Prometheus并行查询（高优先级）

**修改代码**:
```python
import concurrent.futures
from apps.scada.utils.promql import promql_query

# 第373-383行替换为：
queries = {}
for module_number, vars_list in module_vars.items():
    var_names = [v.name for v in vars_list]
    query_str = f"grm_{module_number}_gauge{{name=~\"{'|'.join(var_names)}\"}}"
    queries[module_number] = query_str

# 并行查询
values = []
timestamp = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(promql_query, query_str): module_number
        for module_number, query_str in queries.items()
    }
    result_dicts = {}
    for future in concurrent.futures.as_completed(futures):
        module_number = futures[future]
        try:
            query_data = future.result()
            # 处理结果...
        except Exception:
            continue
```

**预期提升**: Prometheus查询从串行变为并行，总耗时减少50%

### 优先级3: 添加缓存（中优先级）

**修改代码**:
```python
from django.core.cache import cache

def get_statistic_value(...):
    cache_key = f"statistic:{site_id}:{statistic_name}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # 原有计算逻辑...
    result = calculate_statistic(...)
    
    # 缓存30秒
    cache.set(cache_key, result, timeout=30)
    return result
```

**预期提升**: 缓存命中时从 ~2000ms 减少到 ~30ms

### 优先级4: 数据库索引优化（低优先级）

**检查并添加索引**:
```python
# 在 SiteStatistic.Meta 中确保有索引
class Meta:
    unique_together = [["name", "site"]]
    indexes = [
        models.Index(fields=['site_id', 'name']),
    ]
```

**预期提升**: 数据库查询从 ~10ms 减少到 ~5ms

## 📊 预期总体效果

| 优化项 | 当前耗时 | 优化后耗时 | 提升 |
|--------|---------|-----------|------|
| 站点1（2模块） | ~4070ms | ~2035ms（无缓存）<br>~35ms（有缓存） | 50% / 99% |
| 站点10（1模块） | ~2050ms | ~2020ms（无缓存）<br>~30ms（有缓存） | 1% / 99% |

## 🔧 实施步骤

1. **立即修复**（5分钟）:
   - 修改第361行：`prefetch_related` 替代 `select_related`

2. **短期优化**（30分钟）:
   - 实现 Prometheus 并行查询
   - 添加缓存机制

3. **长期优化**（1小时）:
   - 检查并添加数据库索引
   - 性能测试和监控

## 📝 注意事项

1. **并发控制**: Prometheus 并行查询需要注意连接池大小
2. **缓存失效**: 统计数据更新时需要清除缓存
3. **错误处理**: 并行查询中某个模块失败不应影响其他模块
4. **监控**: 添加性能监控，跟踪优化效果

