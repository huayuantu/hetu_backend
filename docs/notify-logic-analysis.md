# Notify 逻辑分析报告

## 📋 当前逻辑分析

### 1. Alertmanager Webhook 接收逻辑 (`create_notify`)

**位置**：`backend/apps/scada/view/alert.py:242-315`

**当前逻辑**：

```python
def create_notify(request: HttpRequest):
    # 1. 解析 alertmanager webhook payload
    for alert in payload["alerts"]:
        status = alert["status"]  # "firing" 或 "resolved"
        external_id = alert["fingerprint"]
        
        # 2. 查找该 external_id 的最新记录
        last_one = Notify.objects.filter(external_id=external_id)
            .order_by("-notified_at").first()
        
        # 3. 根据 status 决定创建什么类型的通知
        if status == "firing":
            suffix_title = "触发警告"
            notified_at = alert["startsAt"]
        else:  # resolved
            suffix_title = "解除警告"
            notified_at = alert["endsAt"]
        
        # 4. 重发消息的处理逻辑（第 284-287 行）
        if last_one and notified_at <= last_one.notified_at:
            if not last_one.ack:
                # 已经确认了要重新激活
                continue  # ⚠️ 跳过创建
        
        # 5. 创建新通知
        notify = Notify(...)
        notify.save()
```

**问题分析**：

1. **第 284-287 行的逻辑有问题**：
   ```python
   if last_one and notified_at <= last_one.notified_at:
       if not last_one.ack:
           # 已经确认了要重新激活
           continue  # ⚠️ 跳过创建
   ```
   - 注释说"已经确认了要重新激活"，但逻辑是 `if not last_one.ack`（未确认）
   - 如果未确认且时间更早，就跳过创建，这不符合预期
   - 应该是：如果已确认（ack=True），才跳过重新激活

2. **resolved 状态的处理**：
   - 当 alertmanager 发送 resolved 状态时，会创建 "解除警告" 记录
   - 但这不应该影响激活状态，因为 `get_activated_notifies` 只查询 "触发警告"
   - 问题：如果最新记录是 "解除警告"，但之前有 "触发警告" 且 ack=False，应该如何处理？

3. **重新激活的逻辑**：
   - 如果用户点击已读（ack=True），然后 alertmanager 再次发送 firing 状态
   - 应该创建新的 "触发警告" 记录，重新激活
   - 但当前逻辑可能不会正确处理

### 2. 获取激活告警逻辑 (`get_activated_notifies`)

**位置**：`backend/apps/scada/view/alert.py:350-380`

**当前逻辑**：

```python
def get_activated_notifies(request, site_id: int):
    # 1. 过滤条件：title__startswith + title__endswith="触发警告" + ack=False
    filtered_notifies = Notify.objects.filter(
        title__startswith=site_filter,
        title__endswith="触发警告",
        ack=False
    )
    
    # 2. 找到每个 external_id 的最新记录
    latest_notify_ids = (
        filtered_notifies.values("external_id")
        .annotate(latest_id=Max("id"))
        .values("latest_id")
    )
    
    # 3. 返回这些最新记录
    return Notify.objects.filter(id__in=latest_notify_ids).all()
```

**问题分析**：

1. **只查询 "触发警告"**：
   - 正确：只返回 "触发警告" 类型的通知
   - 但如果最新记录是 "解除警告"，之前的 "触发警告" 仍然会被返回（如果 ack=False）

2. **ack=False 过滤**：
   - 正确：已读的通知不会显示
   - 但问题：如果用户点击已读，然后 alertmanager 发送 resolved，会创建 "解除警告"，但之前的 "触发警告" 仍然是 ack=False

### 3. 标记已读逻辑 (`ack_notify`)

**位置**：`backend/apps/scada/view/alert.py:417-428`

**当前逻辑**：

```python
def ack_notify(request, site_id: int, notify_id: int):
    notify = get_object_or_404(Notify, id=notify_id)
    
    if not notify.ack:
        notify.ack = True
        notify.ack_at = datetime.now(timezone.utc)
        notify.save()
    
    return "Ok"
```

**问题分析**：

1. **只标记单个通知**：
   - 只标记指定的 notify_id 为已读
   - 但同一个 external_id 可能有多个通知记录
   - 应该标记该 external_id 的所有相关通知为已读

2. **没有处理 "解除警告"**：
   - 如果用户点击已读，应该确保该告警不再激活
   - 但当前逻辑只是标记单个通知，如果还有其他未读的 "触发警告"，仍然会显示

## 🎯 预期行为

根据用户需求：
1. **Alertmanager 发送 firing** → 创建 "触发警告" 记录，显示在激活列表中
2. **用户点击已读** → 取消激活，不再显示在激活列表中
3. **Alertmanager 发送 resolved** → 创建 "解除警告" 记录，但不影响激活状态（因为激活列表只查 "触发警告"）
4. **Alertmanager 再次发送 firing** → 如果之前已读，应该重新激活，创建新的 "触发警告" 记录

## 🚨 发现的问题

### 问题 1: create_notify 的重发逻辑错误

**当前代码**（第 284-287 行）：
```python
if last_one and notified_at <= last_one.notified_at:
    if not last_one.ack:
        # 已经确认了要重新激活
        continue  # ⚠️ 跳过创建
```

**问题**：
- 逻辑反了：应该是 `if last_one.ack`（已确认）才跳过
- 或者：如果已确认，应该允许重新激活（创建新记录）

**预期逻辑**：
```python
# 如果是重发的消息（时间更早或相同），且最新记录已确认，跳过
if last_one and notified_at <= last_one.notified_at:
    if last_one.ack:
        # 已确认的消息，如果是重发，跳过
        continue
    # 如果未确认，继续创建（可能是重复通知）
```

### 问题 2: resolved 状态应该取消激活

**当前逻辑**：
- resolved 状态创建 "解除警告" 记录
- 但 `get_activated_notifies` 只查询 "触发警告"
- 如果最新记录是 "解除警告"，之前的 "触发警告" 仍然会显示

**预期逻辑**：
- 当收到 resolved 状态时，应该：
  1. 创建 "解除警告" 记录
  2. 或者：将该 external_id 的所有 "触发警告" 标记为已读（ack=True）

### 问题 3: ack_notify 应该标记整个告警

**当前逻辑**：
- 只标记单个 notify_id 为已读
- 同一个 external_id 的其他通知仍然是未读状态

**预期逻辑**：
- 应该将该 external_id 的所有相关通知都标记为已读
- 或者：只标记最新的 "触发警告" 为已读，确保不再显示

## 🔧 修复方案

### 方案 1: 修复 create_notify 逻辑

```python
def create_notify(request: HttpRequest):
    payload = json.loads(request.body.decode("utf-8"))
    for alert in payload["alerts"]:
        status = alert["status"]
        external_id = alert["fingerprint"]
        
        # 查找该 external_id 的最新记录
        last_one = Notify.objects.filter(external_id=external_id)
            .order_by("-notified_at").first()
        
        if status == "firing":
            notified_at = rfc3339_parser.parse(alert["startsAt"])
            suffix_title = "触发警告"
            level = labels["severity"]
        else:  # resolved
            notified_at = rfc3339_parser.parse(alert["endsAt"])
            suffix_title = "解除警告"
            level = "info"
            
            # 修复：当收到 resolved 时，将该 external_id 的所有 "触发警告" 标记为已读
            Notify.objects.filter(
                external_id=external_id,
                title__endswith="触发警告",
                ack=False
            ).update(
                ack=True,
                ack_at=datetime.now(timezone.utc)
            )
        
        # 修复：重发消息的处理逻辑
        if last_one and notified_at <= last_one.notified_at:
            # 如果最新记录已确认，且是重发消息，跳过
            if last_one.ack:
                continue
        
        # 创建新通知
        title = f"{annos['site_id']}::{annos['module_id']}::{annos['variable_id']}::{labels['alertname']}::{suffix_title}"
        notify = Notify(
            external_id=external_id,
            level=level,
            title=title,
            content=suffix_title,
            source="alertmanager",
            notified_at=notified_at,
            created_at=datetime.now(timezone.utc),
            meta=annos,
        )
        notify.save()
    
    return "OK"
```

### 方案 2: 修复 ack_notify 逻辑

```python
def ack_notify(request, site_id: int, notify_id: int):
    """标记已读（修复：标记该 external_id 的所有相关通知为已读）"""
    filter_title = str(site_id) + "::"
    notify = get_object_or_404(Notify, id=notify_id, title__startswith=filter_title)
    
    if not notify.ack:
        # 修复：将该 external_id 的所有 "触发警告" 通知都标记为已读
        Notify.objects.filter(
            external_id=notify.external_id,
            title__endswith="触发警告",
            ack=False
        ).update(
            ack=True,
            ack_at=datetime.now(timezone.utc)
        )
    
    return "Ok"
```

### 方案 3: 修复 get_activated_notifies 逻辑

**当前逻辑已经基本正确**，但需要确保：
- 只返回最新的 "触发警告" 记录
- 如果最新记录是 "解除警告"，不应该返回之前的 "触发警告"

**优化后的逻辑**：
```python
def get_activated_notifies(request, site_id: int):
    site_filter = str(site_id) + "::"
    
    # 1. 找到每个 external_id 的最新记录（包括 "触发警告" 和 "解除警告"）
    latest_notify_ids = (
        Notify.objects.filter(title__startswith=site_filter)
        .values("external_id")
        .annotate(latest_id=Max("id"))
        .values("latest_id")
    )
    
    # 2. 只返回最新的 "触发警告" 且未确认的记录
    result = Notify.objects.filter(
        id__in=latest_notify_ids,
        title__endswith="触发警告",
        ack=False
    )
    
    return result.all()
```

## 📝 推荐修复方案

**优先级 1**：修复 `ack_notify` - 标记整个告警为已读
**优先级 2**：修复 `create_notify` - resolved 状态时取消激活
**优先级 3**：优化 `get_activated_notifies` - 确保逻辑正确

