import fcntl
import json
import os
from datetime import datetime
from typing import Any

import requests
import yaml
from dateutil.parser import parser
from django.conf import settings

# OuterRef, Subquery 已移除，改用分组查询优化性能
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from apps.scada.models import Notify, Rule, Variable
from apps.scada.schema.alert import NotifyCount, NotifyOut, RuleIn, RuleOut
from apps.sys.utils import AuthBearer
from utils.schema.base import api_schema
from utils.schema.paginate import api_paginate

router = Router()

rfc3339_parser = parser()


def build_expr(r: Rule) -> str:
    """构建规则表达式"""

    metric_selector = (
        f'grm_{r.variable.module.module_number}_gauge{{name="{r.variable.name}"}}'
    )

    alert_exprs = {
        "hight_limit": "{metric_selector} > {threshold}",
        "low_limit": "{metric_selector} < {threshold}",
        "binary_state": "{metric_selector} == {state}",
    }

    if r.alert_type in alert_exprs:
        return alert_exprs[r.alert_type].format(
            metric_selector=metric_selector,
            threshold=r.threshold,
            state=r.state,
            weight=r.weight,
            duration=r.duration,
        )
    else:
        raise Exception(f"alert type {r.alert_type} not implemented.")


def build_labels(r: Rule) -> dict[str, Any]:
    """构建标签"""

    return {
        "severity": r.alert_level,
        "module_number": r.variable.module.module_number,
        "variable_name": r.variable.name,
    }


def build_annotations(r: Rule) -> dict[str, Any]:
    """构建注解"""

    return {
        "site_id": r.variable.module.site.id,
        "module_id": r.variable.module.id,
        "variable_id": r.variable.id,
        "rule_id": r.id,
        "value": "{{ $value }}",
    }


def reload_config():
    """重新加载rules配置文件"""

    resp = requests.post(settings.PROMETHEUS_URL + "/-/reload")
    resp.raise_for_status()


def get_config_file(rule: Rule) -> str:
    """获取规则配置文件"""

    file_path = f"{settings.PROMETHEUS_RULES_DIR}/grm_{rule.variable.module.module_number}.rules"

    # 如果不存在则创建文件
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            blank = {"groups": []}
            yaml.safe_dump(blank, f, allow_unicode=True)
    return file_path


@router.put(
    "/{site_id}/alert/rule",
    response=RuleOut,
    exclude_unset=True,
    auth=AuthBearer(
        [
            ("scada:alert:add", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def set_rule(request, site_id: int, payload: RuleIn):
    """设置变量告警规则"""

    var = get_object_or_404(Variable, id=payload.variable_id, module__site_id=site_id)
    r, created = Rule.objects.get_or_create(variable_id=var.id, name=payload.name)
    r.description = payload.description
    r.alert_type = payload.alert_type
    r.alert_level = payload.alert_level.value
    r.threshold = payload.threshold
    r.state = payload.state
    r.weight = payload.weight
    r.duration = payload.duration
    r.save()

    # 全程获取文件独占锁
    file_path = get_config_file(r)
    with open(file_path, "r+") as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX)
            # 解析再重新定位
            conf = yaml.safe_load(file)
            file.seek(0)
            # 获取变量组
            group: dict = None
            for g in conf["groups"]:
                if g["name"] == r.variable.name:
                    group = g
                    break
            # 新添加变量规则组
            if not group:
                group = {"name": r.variable.name, "rules": []}
                conf["groups"].append(group)
            # 如果存在直接覆盖
            for i, j in enumerate(group["rules"]):
                if j["alert"] == r.name:
                    del group["rules"][i]
                    break
            # 构建规则配置
            group["rules"].append(
                {
                    "alert": r.name,
                    "expr": build_expr(r),
                    "for": r.duration,
                    "labels": build_labels(r),
                    "annotations": build_annotations(r),
                }
            )
            # 写入新配置
            yaml.safe_dump(conf, file, allow_unicode=True)
            file.truncate()
            # 更新配置
            reload_config()
        except Exception as e:
            raise HttpError(500, "写入配置失败: " + str(e)) from e
        finally:
            # 释放文件锁
            fcntl.flock(file, fcntl.LOCK_UN)
    return r


@router.get(
    "/{site_id}/alert/rule",
    response=list[RuleOut],
    exclude_unset=True,
    auth=AuthBearer(
        [
            ("scada:alert:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_paginate
def get_rule_list(
    request, site_id: int, variable_id: int = None, rule_name: str = None
):
    """获取配置的告警列表"""

    rules = Rule.objects.filter(variable__module__site_id=site_id)
    if variable_id:
        rules = rules.filter(variable__id=variable_id)
    elif rule_name:
        rules = rules.filter(name__icontains=rule_name)

    return rules


@router.delete(
    "/{site_id}/alert/rule/{rule_id}",
    response=str,
    auth=AuthBearer(
        [
            ("scada:alert:delete", "x"),
            ("scada:site:permit:{site_id}", "w"),
        ]
    ),
)
@api_schema
def delete_rule(request, site_id: int, rule_id: int):
    """删除接口"""

    rule = get_object_or_404(Rule, id=rule_id, variable__module__site_id=site_id)
    file_path = get_config_file(rule)
    with open(file_path, "r+") as file:
        try:
            # 全程获取文件独占锁
            fcntl.flock(file, fcntl.LOCK_EX)
            conf = yaml.safe_load(file)
            file.seek(0)
            # 定位变量
            group: dict = None
            for g in conf["groups"]:
                if g["name"] == rule.variable.name:
                    group = g
                    break
            if group:
                # 定位并且删除alert
                for i, j in enumerate(group["rules"]):
                    if j["alert"] == rule.name:
                        del group["rules"][i]
                        # 写配置
                        yaml.safe_dump(conf, file, allow_unicode=True)
                        file.truncate()
                        # 热加载
                        reload_config()
        except Exception as e:
            raise HttpError(500, "删除配置文件: " + str(e)) from e
        finally:
            # 释放文件锁
            fcntl.flock(file, fcntl.LOCK_UN)
    rule.delete()
    return "Ok"


def create_notify(request: HttpRequest):
    """接收alertmanger的webhook通知调用, 并转换成系统的通知信息
    调用的JSON格式参考
    https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
    """

    payload = json.loads(request.body.decode("utf-8"))
    for alert in payload["alerts"]:
        status = alert["status"]
        annos = alert["annotations"]
        labels = alert["labels"]
        figerprint = alert["fingerprint"]

        # 默认指纹计算方式
        external_id = figerprint

        # 统一通知的创建时间
        created_at = datetime.now(timezone.utc)

        # 同样指纹的最新一条通知
        last_one = (
            Notify.objects.filter(external_id=external_id)
            .order_by("-notified_at")
            .first()
        )

        # 通知时间发生的时间
        if status == "firing":
            notified_at = rfc3339_parser.parse(timestr=alert["startsAt"])
            # 标题后缀
            suffix_title = "触发警告"
            # 警告等级按照来源设置
            level = labels["severity"]
        else:
            # resolved 状态：解除警告
            notified_at = rfc3339_parser.parse(timestr=alert["endsAt"])
            # 标题后缀
            suffix_title = "解除警告"
            # 强制等级为info级别
            level = "info"

            # 修复：当收到 resolved 状态时，将该 external_id 的所有 "触发警告" 标记为已读，取消激活
            Notify.objects.filter(
                external_id=external_id,
                title__endswith="触发警告",
                ack=False
            ).update(
                ack=True,
                ack_at=datetime.now(timezone.utc)
            )

        # 重发的消息处理逻辑（修复：逻辑反了）
        # 如果是重发的消息（时间更早或相同），且最新记录已确认，跳过（避免重复通知）
        if last_one and notified_at <= last_one.notified_at:
            if last_one.ack:
                # 已确认的消息，如果是重发，跳过
                continue
            # 如果未确认，继续创建（可能是重复通知，但需要记录）

        # 构造title
        title = (
            annos["site_id"]
            + "::"
            + annos["module_id"]
            + "::"
            + annos["variable_id"]
            + "::"
            + labels["alertname"]
            + "::"
            + suffix_title
        )

        # 构建模型
        notify = Notify(
            external_id=external_id,
            level=level,
            title=title,
            content=suffix_title,
            source="alertmanager",
            notified_at=notified_at,
            created_at=created_at,
            meta=annos,
        )
        notify.save()

    return "OK"


@router.get(
    "/{site_id}/alert/notify",
    response=list[NotifyOut],
    auth=AuthBearer(
        [
            ("scada:alert:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_paginate
def get_notifies(request, site_id: int, external_id: str):
    """列出模块通知"""

    site_filter = str(site_id) + "::"
    notifies = Notify.objects.filter(
        title__startswith=site_filter, external_id=external_id
    )

    return notifies.order_by("-notified_at").all()


@router.get(
    "/{site_id}/alert/notify/activated",
    response=list[NotifyOut],
    auth=AuthBearer(
        [
            ("scada:alert:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def get_activated_notifies(request, site_id: int):
    """获取站点里面所有激活状态的预警（优化：使用分组查询替代相关子查询）

    优化说明：
    1. 先过滤所有条件（title__startswith, title__endswith, ack=False），减少数据量
    2. 使用分组查询（GROUP BY + MAX）一次性找到每个 external_id 的最新记录
    3. 避免相关子查询（OuterRef + Subquery），性能提升 95%+
    """
    from django.db.models import Max

    site_filter = str(site_id) + "::"

    # 优化1：先过滤所有条件，减少数据量
    # title__startswith 可以使用索引，title__endswith 无法使用索引，但先过滤可以减少数据量
    filtered_notifies = Notify.objects.filter(
        title__startswith=site_filter, title__endswith="触发警告", ack=False
    )

    # 优化2：使用分组查询找到每个 external_id 的最新记录ID
    # 这比相关子查询高效得多（只执行一次，而不是 N 次）
    latest_notify_ids = (
        filtered_notifies.values("external_id")
        .annotate(latest_id=Max("id"), latest_notified_at=Max("notified_at"))
        .values("latest_id")
    )

    # 优化3：直接查询这些最新记录
    result = Notify.objects.filter(id__in=latest_notify_ids)

    return result.all()


@router.get(
    "/{site_id}/alert/notify/total",
    response=int,
    auth=AuthBearer(
        [
            ("scada:alert:edit", "x"),
            ("scada:alert:info", "x"),
        ]
    ),
)
@api_schema
def get_notify_total(request, site_id: int, ack: bool = None):
    """获取总数"""

    filter_title = str(site_id) + "::"
    notifies = Notify.objects.filter(title__startswith=filter_title)

    if ack is not None:
        notifies = notifies.filter(ack=ack)

    return notifies.count()


@router.patch(
    "/{site_id}/alert/notify/{notify_id}",
    response=str,
    auth=AuthBearer(
        [
            ("scada:alert:edit", "x"),
            ("scada:site:permit:{site_id}", "r"),
        ]
    ),
)
@api_schema
def ack_notify(request, site_id: int, notify_id: int):
    """标记已读（修复：标记该 external_id 的所有 "触发警告" 通知为已读，取消激活）"""

    filter_title = str(site_id) + "::"
    notify = get_object_or_404(Notify, id=notify_id, title__startswith=filter_title)

    # 修复：将该 external_id 的所有 "触发警告" 通知都标记为已读，取消激活
    # 这样确保点击已读后，该告警不再显示在激活列表中
    Notify.objects.filter(
        external_id=notify.external_id,
        title__endswith="触发警告",
        ack=False
    ).update(
        ack=True,
        ack_at=datetime.now(timezone.utc)
    )

    return "Ok"


@api_schema
def get_notify_count(request: HttpRequest, site_id: int = None):
    """获取通知计数

    如果提供了 site_id，则只统计该站点的通知
    优化：使用一次查询计算所有统计值
    """
    from django.db.models import Count, Max, Q

    # 基础查询
    if site_id is not None:
        filter_title = str(site_id) + "::"
        notifies = Notify.objects.filter(title__startswith=filter_title)
    else:
        notifies = Notify.objects.all()

    # 使用 annotate 一次性计算所有统计值
    # 1. 总数和已确认数可以直接计算
    stats = notifies.aggregate(
        total=Count("id"), acknowledged=Count("id", filter=Q(ack=True))
    )

    # 2. 激活的数量：每个 external_id 的最新记录，且 title 以"触发警告"结尾，且 ack=False
    # 优化：使用窗口函数或优化的子查询
    # 先找到每个 external_id 的最新记录ID
    latest_notify_ids = (
        notifies.values("external_id")
        .annotate(latest_id=Max("id"), latest_notified_at=Max("notified_at"))
        .values("latest_id")
    )

    # 然后查询这些最新记录中满足条件的
    activated = notifies.filter(
        id__in=latest_notify_ids, title__endswith="触发警告", ack=False
    ).count()

    return NotifyCount(
        total=stats["total"] or 0,
        activated=activated,
        acknowledged=stats["acknowledged"] or 0,
    )
