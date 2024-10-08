import fcntl
import json
import os
from datetime import datetime
from typing import Any
from django.db.models import Subquery, OuterRef
import requests
import yaml
from dateutil.parser import parser
from django.conf import settings
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from apps.scada.models import Notify, Rule, Variable
from apps.scada.schema.alert import RuleOut, RuleIn, NotifyOut
from apps.sys.utils import AuthBearer
from utils.schema.base import api_schema
from utils.schema.paginate import api_paginate

router = Router()

rfc3339_parser = parser()


def build_expr(r: Rule) -> str:
    """构建规则表达式"""

    metric_selector = 'grm_{module_number}_gauge{{name="{variable_name}"}}'.format(
        module_number=r.variable.module.module_number,
        variable_name=r.variable.name,
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
            raise HttpError(500, "写入配置失败: " + str(e))
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
def get_rule_list(request, site_id: int, variable_id: int = None, rule_name: str = None):
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
            raise HttpError(500, "删除配置文件: " + str(e))
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
            notified_at = rfc3339_parser.parse(timestr=alert["endsAt"])
            # 标题后缀
            suffix_title = "解除警告"
            # 强制等级为info级别
            level = "info"
            # pass

        # 重发的消息
        if last_one and notified_at <= last_one.notified_at:
            if not last_one.ack:
                # 已经确认了要重新激活
                continue

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

    return notifies.order_by(("-notified_at")).all()


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
    """获取站点里面所有激活状态的预警"""

    site_filter = str(site_id) + "::"
    notifies = Notify.objects.filter(title__startswith=site_filter)
    latest_record_ids = (
        notifies.filter(
            external_id=OuterRef("external_id")  # 外部引用，对应于内部查询中的 external_id
        )
        .order_by("-notified_at", "-id")
        .values("id")[:1]
    )
    result = Notify.objects.filter(
        id=Subquery(latest_record_ids), title__endswith="触发警告", ack=False
    )

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

    if ack != None:
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
    """标记已读"""

    filter_title = str(site_id) + "::"
    nofity = get_object_or_404(Notify, id=notify_id, title__startswith=filter_title)

    if not nofity.ack:
        nofity.ack = True
        nofity.ack_at = datetime.now(timezone.utc)
        nofity.save()

    return "Ok"
