# 数据分析页面后端接口实现计划

## 需求分析

### 前端需求（来自 DataQueryForm.vue）
- **siteId**: 站点ID
- **moduleId**: 模块ID（可选）
- **variableIds**: 多个变量ID（数组，必填）
- **step**: 聚合频率（秒，如 15, 30, 60, 300, 900, 3600）
- **aggregation**: 聚合方式（'avg' | 'min' | 'max'）
- **startTime**: 开始时间（Unix时间戳，秒）
- **endTime**: 结束时间（Unix时间戳，秒）

### 现有接口分析

#### 1. `GET /api/scada/site/{site_id}/variable/{variable_id}/range`
- **功能**: 单个变量的历史数据查询
- **参数**: 
  - `offset` (可选): 结束时间戳
  - `duration` (默认 "1h"): 时间范围字符串（如 "1h", "1d"）
  - `step` (默认 15): 步长（秒）
- **返回**: `ReadValueOut`（单个变量）
- **问题**: 
  - 只支持单个变量
  - 使用 duration 而不是精确的 start_time/end_time
  - 不支持聚合函数

#### 2. `POST /api/scada/site/{site_id}/variable/values`
- **功能**: 批量读取变量实时值
- **参数**: `ReadValueIn` (包含 `variable_ids`)
- **返回**: `list[ReadValueOut]`
- **问题**: 
  - 只返回实时值，不支持历史范围查询

#### 3. `promql_query_range` 函数
- **功能**: 已实现 Prometheus range query
- **参数**: `query`, `start_time`, `end_time`, `step`
- **支持**: 完全支持精确时间范围查询

## 实现方案

### 方案 1：扩展现有接口（推荐）

#### 1.1 扩展 `read_range` 接口
**路径**: `GET /api/scada/site/{site_id}/variable/{variable_id}/range`

**变更**:
- 保留现有参数 `offset`, `duration`, `step`（向后兼容）
- 新增可选参数 `start_time`, `end_time`
- **参数优先级**: 如果提供了 `start_time`/`end_time`，使用它们；否则使用 `offset`/`duration`

**PromQL 聚合支持**:
- 新增可选参数 `aggregation` (可选值: `avg`, `min`, `max`)
- 如果提供了 `aggregation`，在 PromQL 中使用相应的 `*_over_time()` 函数

**示例**:
```python
# 旧方式（保持兼容）
GET /api/scada/site/1/variable/123/range?duration=1h&step=60

# 新方式（精确时间）
GET /api/scada/site/1/variable/123/range?start_time=1699123200&end_time=1699126800&step=60

# 新方式（带聚合）
GET /api/scada/site/1/variable/123/range?start_time=1699123200&end_time=1699126800&step=60&aggregation=avg
```

#### 1.2 新增批量查询接口
**路径**: `POST /api/scada/site/{site_id}/variable/range`

**请求 Schema**: `QueryRangeIn`
```python
class QueryRangeIn(Schema):
    variable_ids: list[int]  # 变量ID列表
    start_time: int  # 开始时间（Unix时间戳，秒）
    end_time: int  # 结束时间（Unix时间戳，秒）
    step: int = 60  # 步长（秒）
    aggregation: str = None  # 聚合方式：'avg' | 'min' | 'max' | None
```

**响应**: `list[ReadValueOut]`（每个变量的历史数据）

**实现逻辑**:
1. 验证变量属于指定站点
2. 按模块分组变量（因为 Prometheus 指标是按模块存储的）
3. 对每个模块构建 PromQL 查询：
   - 基础查询: `grm_{module_number}_gauge{name=~"var1|var2|..."}`
   - 如果指定了聚合: `{aggregation}_over_time(grm_{module_number}_gauge{name=~"var1|var2|..."}[{step}s])`
4. 调用 `promql_query_range` 获取数据
5. 解析结果并返回

**PromQL 聚合示例**:
```promql
# 平均值聚合
avg_over_time(grm_module1_gauge{name=~"var1|var2"}[60s])

# 最小值聚合
min_over_time(grm_module1_gauge{name=~"var1|var2"}[60s])

# 最大值聚合
max_over_time(grm_module1_gauge{name=~"var1|var2"}[60s])
```

### 方案 2：完全新接口（不推荐）
创建全新的接口，但会导致代码重复。

## 实施步骤

1. **创建 Schema** (`apps/scada/schema/variable.py`)
   - 添加 `QueryRangeIn` Schema

2. **扩展 `read_range` 函数** (`apps/scada/view/variable.py`)
   - 添加 `start_time`, `end_time`, `aggregation` 参数
   - 实现参数优先级逻辑
   - 实现聚合函数支持

3. **新增 `query_range` 函数** (`apps/scada/view/variable.py`)
   - 实现批量变量历史查询
   - 支持聚合函数
   - 按模块分组查询

4. **测试**
   - 测试向后兼容性（旧参数仍可用）
   - 测试新功能（批量查询、聚合）
   - 测试边界情况（空变量列表、时间范围错误等）

## 向后兼容性保证

- ✅ 保留所有现有参数和默认值
- ✅ 新参数为可选参数
- ✅ 旧调用方式仍然有效
- ✅ 不改变现有返回结构（`ReadValueOut`）

## 注意事项

1. **PromQL 聚合函数说明**:
   - `avg_over_time()`: 计算时间窗口内的平均值
   - `min_over_time()`: 计算时间窗口内的最小值
   - `max_over_time()`: 计算时间窗口内的最大值
   - 这些函数需要配合 `[step]` 时间窗口使用

2. **性能考虑**:
   - 批量查询时，按模块分组可以减少 Prometheus 查询次数
   - 大时间范围查询可能较慢，需要在文档中说明

3. **错误处理**:
   - 变量不存在或不属于指定站点 → 404
   - Prometheus 查询失败 → 500
   - 时间范围无效（start_time > end_time）→ 400

